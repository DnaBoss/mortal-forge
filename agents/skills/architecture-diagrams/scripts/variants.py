#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

PX, PY, MX, MY, GX, GY = 310, 190, 40, 60, 130, 60
TITLE_H = 80
GROUP_PAD = 16
MIN_OVERLAP = 40
CJK = "'Noto Sans CJK TC','Noto Sans TC','Droid Sans Fallback',sans-serif"

THEMES = {
    "clean": dict(
        bg="#ffffff", node="#f3f6fb", focus="#dbe8f8", stroke="#3b5b8c",
        text="#1f2937", sub="#5b6472", line="#3b5b8c", group="#8aa0bf",
        rough=False, width=2,
    ),
    "sketch": dict(
        bg="#fffdf6", node="#fff4d6", focus="#ffe0a3", stroke="#7a5c1e",
        text="#2b2417", sub="#6b5b3a", line="#7a5c1e", group="#a58a4f",
        rough=True, width=2.4,
    ),
    "blueprint": dict(
        bg="#0f2744", node="#16365c", focus="#2a5b96", stroke="#9ec5f4",
        text="#eaf3ff", sub="#a9c4e6", line="#9ec5f4", group="#6f93c4",
        rough=False, width=2,
    ),
}


def text_width(s, size):
    return sum(size if ord(c) > 255 else size * 0.58 for c in s)


def rect_of(item, is_group):
    x = item["col"] * PX + MX
    y = item["row"] * PY + MY + TITLE_H
    w = item.get("w", 1) * PX - GX
    h = item.get("h", 1) * PY - GY
    if is_group:
        return (x - GROUP_PAD, y - GROUP_PAD, w + 2 * GROUP_PAD, h + 2 * GROUP_PAD)
    return (x, y, w, h)


def inter(a0, a1, b0, b1):
    return max(a0, b0), min(a1, b1)


def rects_touch(r, s, shrink=1):
    ax, ay, aw, ah = r
    bx, by, bw, bh = s
    return not (
        ax + aw <= bx + shrink or bx + bw <= ax + shrink
        or ay + ah <= by + shrink or by + bh <= ay + shrink
    )


def inside(inner, outer):
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


def build(spec):
    errors = []
    nodes = {n["id"]: dict(n, rect=rect_of(n, False), group=False) for n in spec["nodes"]}
    groups = {g["id"]: dict(g, rect=rect_of(g, True), group=True) for g in spec.get("groups", [])}
    allitems = {**nodes, **groups}

    for a in nodes.values():
        for b in nodes.values():
            if a["id"] < b["id"] and rects_touch(a["rect"], b["rect"]):
                errors.append(f"方塊重疊：{a['id']} 與 {b['id']}")
    for g in groups.values():
        for n in nodes.values():
            if rects_touch(g["rect"], n["rect"]) and not inside(n["rect"], g["rect"]):
                errors.append(f"方塊 {n['id']} 只有一部分在群組 {g['id']} 內")
        for h in groups.values():
            if g["id"] < h["id"] and rects_touch(g["rect"], h["rect"]):
                errors.append(f"群組重疊：{g['id']} 與 {h['id']}")

    for n in nodes.values():
        size = n.get("size", 18)
        lines = n["text"].split("\n")
        sub = n.get("sub", "").split("\n") if n.get("sub") else []
        widest = max([text_width(s, size) for s in lines] + [text_width(s, 13) for s in sub])
        if widest > n["rect"][2] - 20:
            errors.append(f"方塊 {n['id']} 文字太長放不下（需要 {int(widest)}，可用 {int(n['rect'][2] - 20)}）")

    segs = []
    for i, e in enumerate(spec.get("edges", [])):
        a, b = allitems[e["from"]], allitems[e["to"]]
        ax, ay, aw, ah = a["rect"]
        bx, by, bw, bh = b["rect"]
        y0, y1 = inter(ay, ay + ah, by, by + bh)
        x0, x1 = inter(ax, ax + aw, bx, bx + bw)
        if y1 - y0 >= MIN_OVERLAP and (ax + aw <= bx or bx + bw <= ax):
            y = (y0 + y1) / 2
            left, right = (a, b) if ax < bx else (b, a)
            lx = left["rect"][0] + left["rect"][2]
            rx = right["rect"][0]
            p, q = ((lx, y), (rx, y)) if a is left else ((rx, y), (lx, y))
            kind = "h"
        elif x1 - x0 >= MIN_OVERLAP and (ay + ah <= by or by + bh <= ay):
            x = (x0 + x1) / 2
            top, bottom = (a, b) if ay < by else (b, a)
            ty = top["rect"][1] + top["rect"][3]
            by_ = bottom["rect"][1]
            p, q = ((x, ty), (x, by_)) if a is top else ((x, by_), (x, ty))
            kind = "v"
        else:
            errors.append(f"線 {e['from']}→{e['to']} 沒有對齊的直線路徑（兩塊要在同一排或同一欄）")
            continue
        seg = dict(e=e, p=p, q=q, kind=kind, ends={e["from"], e["to"]})
        lo = (min(p[0], q[0]), min(p[1], q[1]))
        hi = (max(p[0], q[0]), max(p[1], q[1]))
        seg["lo"], seg["hi"] = lo, hi
        segs.append(seg)

    for s in segs:
        e = s["e"]
        for item in allitems.values():
            if item["id"] in s["ends"]:
                continue
            contains_end = item["group"] and any(
                inside(allitems[x]["rect"], item["rect"]) for x in s["ends"]
            )
            if contains_end:
                continue
            ix, iy, iw, ih = item["rect"]
            if s["kind"] == "h":
                hit = iy + 1 < s["lo"][1] < iy + ih - 1 and s["lo"][0] < ix + iw - 1 and s["hi"][0] > ix + 1
            else:
                hit = ix + 1 < s["lo"][0] < ix + iw - 1 and s["lo"][1] < iy + ih - 1 and s["hi"][1] > iy + 1
            if hit:
                errors.append(f"線 {e['from']}→{e['to']} 穿過 {item['id']}")
        length = (s["hi"][0] - s["lo"][0]) if s["kind"] == "h" else (s["hi"][1] - s["lo"][1])
        label = e.get("label", "")
        if label and s["kind"] == "h" and text_width(label, 14) > length - 24:
            errors.append(f"線 {e['from']}→{e['to']} 的標籤太長（{int(text_width(label, 14))} > {int(length - 24)}）")
        s["label_rect"] = None
        if label:
            tw = text_width(label, 14)
            mx, my = (s["lo"][0] + s["hi"][0]) / 2, (s["lo"][1] + s["hi"][1]) / 2
            s["label_rect"] = (mx - tw / 2, my - 24, tw, 18) if s["kind"] == "h" else (mx + 10, my - 9, tw, 18)
            for item in allitems.values():
                if item["group"] and any(inside(allitems[x]["rect"], item["rect"]) for x in s["ends"]):
                    continue
                if rects_touch(s["label_rect"], item["rect"]):
                    errors.append(f"線 {e['from']}→{e['to']} 的標籤壓到 {item['id']}")

    for i, s in enumerate(segs):
        for t in segs[i + 1:]:
            if s["kind"] != t["kind"]:
                h, v = (s, t) if s["kind"] == "h" else (t, s)
                if h["lo"][0] <= v["lo"][0] <= h["hi"][0] and v["lo"][1] <= h["lo"][1] <= v["hi"][1]:
                    errors.append(f"線交叉：{s['e']['from']}→{s['e']['to']} 與 {t['e']['from']}→{t['e']['to']}")
            else:
                axis = 1 if s["kind"] == "h" else 0
                span = 0 if s["kind"] == "h" else 1
                if abs(s["lo"][axis] - t["lo"][axis]) < 1 and s["lo"][span] < t["hi"][span] and t["lo"][span] < s["hi"][span]:
                    errors.append(f"線重疊：{s['e']['from']}→{s['e']['to']} 與 {t['e']['from']}→{t['e']['to']}")
    return nodes, groups, segs, errors


def svg_of(spec, nodes, groups, segs, theme):
    t = THEMES[theme]
    right = max(r[0] + r[2] for r in [i["rect"] for i in list(nodes.values()) + list(groups.values())])
    bottom = max(r[1] + r[3] for r in [i["rect"] for i in list(nodes.values()) + list(groups.values())])
    W, H = int(right + MX), int(bottom + MY)
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{CJK}">',
        f'<defs><marker id="e" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["line"]}"/></marker>',
    ]
    if t["rough"]:
        o.append('<filter id="r" x="-2%" y="-2%" width="104%" height="104%"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="3.5"/></filter>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>')
    o.append(f'<text x="{MX}" y="{MY + 18}" font-size="28" font-weight="700" fill="{t["text"]}">{escape(spec["title"])}</text>')
    if spec.get("subtitle"):
        o.append(f'<text x="{MX}" y="{MY + 48}" font-size="15" fill="{t["sub"]}">{escape(spec["subtitle"])}</text>')
    flt = ' filter="url(#r)"' if t["rough"] else ""
    o.append(f"<g{flt}>")
    for g in groups.values():
        x, y, w, h = g["rect"]
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="none" stroke="{t["group"]}" stroke-width="{t["width"]}" stroke-dasharray="9 7"/>')
    for n in nodes.values():
        x, y, w, h = n["rect"]
        fill = t["focus"] if n.get("focus") else t["node"]
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{t["stroke"]}" stroke-width="{t["width"]}"/>')
    for s in segs:
        e = s["e"]
        start = ' marker-start="url(#e)"' if e.get("both") else ""
        dash = ' stroke-dasharray="7 6"' if e.get("dashed") else ""
        o.append(f'<line x1="{s["p"][0]}" y1="{s["p"][1]}" x2="{s["q"][0]}" y2="{s["q"][1]}" stroke="{t["line"]}" stroke-width="{t["width"]}"{dash}{start} marker-end="url(#e)"/>')
    o.append("</g>")
    for g in groups.values():
        x, y, w, h = g["rect"]
        o.append(f'<text x="{x + 6}" y="{y - 8}" font-size="15" font-weight="700" fill="{t["sub"]}">{escape(g["text"])}</text>')
    for n in nodes.values():
        x, y, w, h = n["rect"]
        lines = n["text"].split("\n")
        sub = n.get("sub", "").split("\n") if n.get("sub") else []
        size = n.get("size", 18)
        total = len(lines) * (size + 6) + len(sub) * 19
        cy = y + h / 2 - total / 2 + size
        for ln in lines:
            o.append(f'<text x="{x + w / 2}" y="{cy}" font-size="{size}" font-weight="700" text-anchor="middle" fill="{t["text"]}">{escape(ln)}</text>')
            cy += size + 6
        cy += 2
        for ln in sub:
            o.append(f'<text x="{x + w / 2}" y="{cy}" font-size="13" text-anchor="middle" fill="{t["sub"]}">{escape(ln)}</text>')
            cy += 19
    for s in segs:
        if s["label_rect"]:
            lx, ly, lw, lh = s["label_rect"]
            anchor = "middle" if s["kind"] == "h" else "start"
            tx = lx + lw / 2 if s["kind"] == "h" else lx
            o.append(f'<text x="{tx}" y="{ly + 14}" font-size="14" text-anchor="{anchor}" fill="{t["sub"]}">{escape(s["e"]["label"])}</text>')
    o.append("</svg>")
    return "\n".join(o), W, H


def drawio_of(spec, nodes, groups, segs):
    t = THEMES["clean"]
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for g in groups.values():
        x, y, w, h = g["rect"]
        cells.append(
            f'<mxCell id="{g["id"]}" value="{escape(g["text"])}" style="rounded=1;dashed=1;fillColor=none;strokeColor={t["group"]};verticalAlign=top;align=left;fontStyle=1;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
    for n in nodes.values():
        x, y, w, h = n["rect"]
        value = escape(n["text"]).replace("\n", "&lt;br&gt;")
        if n.get("sub"):
            value += "&lt;br&gt;" + escape(n["sub"]).replace("\n", "&lt;br&gt;")
        fill = t["focus"] if n.get("focus") else t["node"]
        cells.append(
            f'<mxCell id="{n["id"]}" value="{value}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={t["stroke"]};" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
    for i, s in enumerate(segs):
        e = s["e"]
        start = "startArrow=classic;" if e.get("both") else ""
        dash = "dashed=1;" if e.get("dashed") else ""
        cells.append(
            f'<mxCell id="edge{i}" value="{escape(e.get("label", ""))}" style="endArrow=classic;{start}{dash}html=1;edgeStyle=none;strokeColor={t["line"]};" edge="1" parent="1" source="{e["from"]}" target="{e["to"]}">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    return (
        '<mxfile><diagram name="1"><mxGraphModel><root>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )


def chrome(args):
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(argv) != 2:
        print("用法：variants.py spec.json 輸出資料夾 [--pdf] [--drawio] [--themes=clean,sketch,blueprint]", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    themes = ["clean", "sketch", "blueprint"]
    for f in flags:
        if f.startswith("--themes="):
            themes = f.split("=", 1)[1].split(",")
    nodes, groups, segs, errors = build(spec)
    if errors:
        print("版面檢查沒過，未輸出：", file=sys.stderr)
        for m in errors:
            print(" -", m, file=sys.stderr)
        return 1
    name = spec.get("name", "diagram")
    for theme in themes:
        svg, W, H = svg_of(spec, nodes, groups, segs, theme)
        svg_path = out / f"{name}-{theme}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        chrome([f"--screenshot={out / f'{name}-{theme}.png'}", f"--window-size={W},{H}", "--force-device-scale-factor=2", svg_path.resolve().as_uri()])
        if "--pdf" in flags:
            with tempfile.TemporaryDirectory() as d:
                page = Path(d) / "p.html"
                page.write_text(
                    f'<!doctype html><meta charset="utf-8"><style>@page{{size:{W}px {H}px;margin:0}}html,body{{margin:0;background:#fff}}img{{display:block}}</style><img src="{svg_path.resolve().as_uri()}" width="{W}" height="{H}">',
                    encoding="utf-8",
                )
                chrome([f"--print-to-pdf={out / f'{name}-{theme}.pdf'}", "--no-pdf-header-footer", page.as_uri()])
    if "--drawio" in flags:
        (out / f"{name}.drawio").write_text(drawio_of(spec, nodes, groups, segs), encoding="utf-8")
    print(f"已輸出 {len(themes)} 種版本到 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
