#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import cairo

W, H = 1120, 630
COLORS = {
    "ink": (0.09, 0.17, 0.22), "muted": (0.37, 0.46, 0.51),
    "line": (0.82, 0.86, 0.88), "blue": (0.12, 0.42, 0.60),
    "green": (0.18, 0.55, 0.36), "amber": (0.82, 0.49, 0.12),
    "red": (0.76, 0.23, 0.22), "paper": (0.97, 0.98, 0.985),
}


def color(ctx, name):
    ctx.set_source_rgb(*COLORS[name])


def text(ctx, value, x, y, size=13, weight=cairo.FONT_WEIGHT_NORMAL, tone="ink"):
    color(ctx, tone)
    ctx.select_font_face("Noto Sans CJK TC", cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    ctx.move_to(x, y)
    ctx.show_text(str(value))


def rounded(ctx, x, y, w, h, radius=10, fill="paper", stroke="line"):
    r = min(radius, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    color(ctx, fill); ctx.fill_preserve()
    color(ctx, stroke); ctx.set_line_width(1); ctx.stroke()


def fit_text(ctx, value, x, y, max_width, size=12, tone="ink", weight=cairo.FONT_WEIGHT_NORMAL):
    value = str(value)
    while value:
        ctx.select_font_face("Noto Sans CJK TC", cairo.FONT_SLANT_NORMAL, weight)
        ctx.set_font_size(size)
        if ctx.text_extents(value).width <= max_width:
            text(ctx, value, x, y, size, weight, tone); return
        value = value[:-1]
    text(ctx, "…", x, y, size, weight, tone)


def render(data, output):
    if "sections" in data:
        render_handoff(data, output)
        return
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    surface = cairo.PDFSurface(str(output), W, H)
    ctx = cairo.Context(surface)
    color(ctx, "paper"); ctx.paint()
    text(ctx, data["title"], 42, 48, 24, cairo.FONT_WEIGHT_BOLD)
    text(ctx, data["timestamp"], 890, 45, 10, tone="muted")
    rounded(ctx, 42, 68, 1036, 52, 10, "ink", "ink")
    text(ctx, data["summary"], 62, 101, 17, cairo.FONT_WEIGHT_BOLD, "paper")

    metrics = data.get("metrics", [])[:4]
    card_w = (1036 - 36) / 4
    for i, item in enumerate(metrics):
        x = 42 + i * (card_w + 12)
        rounded(ctx, x, 140, card_w, 92)
        text(ctx, item["value"], x + 18, 187, 32, cairo.FONT_WEIGHT_BOLD, item.get("tone", "blue"))
        fit_text(ctx, item["label"], x + 18, 214, card_w - 36, 11, "muted")

    text(ctx, "目前進度狀態", 42, 270, 15, cairo.FONT_WEIGHT_BOLD)
    statuses = data.get("statuses", [])
    y = 286
    row_h = 32
    for i, item in enumerate(statuses[:5]):
        tone = item.get("tone", "muted")
        if i % 2 == 0:
            ctx.set_source_rgb(0.94, 0.96, 0.97); ctx.rectangle(42, y, 1036, row_h); ctx.fill()
        ctx.new_path(); ctx.arc(58, y + 16, 5, 0, 2 * math.pi); color(ctx, tone); ctx.fill()
        text(ctx, item["name"], 74, y + 21, 11, cairo.FONT_WEIGHT_BOLD)
        text(ctx, item["state"], 218, y + 21, 11, cairo.FONT_WEIGHT_BOLD, tone)
        fit_text(ctx, item.get("detail", ""), 342, y + 21, 720, 10, "muted")
        y += row_h

    text(ctx, "工作內容", 42, 478, 15, cairo.FONT_WEIGHT_BOLD)
    items = data.get("items", [])[:4]
    col_w = (1036 - 16) / 2
    for i, item in enumerate(items):
        x = 42 + (i % 2) * (col_w + 16); yy = 493 + (i // 2) * 52
        rounded(ctx, x, yy, col_w, 42, 7, "paper", "line")
        text(ctx, item["label"], x + 12, yy + 18, 10, cairo.FONT_WEIGHT_BOLD, item.get("tone", "blue"))
        fit_text(ctx, item["detail"], x + 12, yy + 34, col_w - 24, 9, "muted")

    text(ctx, data.get("scope", ""), 42, 612, 9, tone="muted")
    if data.get("work_summary"):
        surface.show_page()
        color(ctx, "paper"); ctx.paint()
        text(ctx, "工作成果與停點", 42, 50, 24, cairo.FONT_WEIGHT_BOLD)
        text(ctx, data["timestamp"], 890, 45, 10, tone="muted")
        sections = [
            ("已完成", "green", data["work_summary"].get("done", [])),
            ("尚未完成", "amber", data["work_summary"].get("todo", [])),
            ("為什麼停下", "red", data["work_summary"].get("stops", [])),
        ]
        y = 78
        for heading, tone, entries in sections:
            text(ctx, heading, 42, y, 16, cairo.FONT_WEIGHT_BOLD, tone)
            y += 10
            for entry in entries[:5]:
                rounded(ctx, 42, y, 1036, 40, 7, "paper", "line")
                text(ctx, entry["title"], 58, y + 16, 10, cairo.FONT_WEIGHT_BOLD, tone)
                fit_text(ctx, entry["detail"], 58, y + 33, 995, 9, "muted")
                y += 46
            y += 8
        text(ctx, data.get("evidence_note", ""), 42, 612, 9, tone="muted")
    surface.finish()


def render_handoff(data, output):
    for key in ("title", "timestamp", "summary"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"交接報告缺少文字：{key}")
    if not isinstance(data["sections"], list) or not data["sections"]:
        raise ValueError("交接報告必須包含成果、遺留與接手內容")
    blocks = [(data["title"], 24, "ink"), (data["timestamp"], 11, "muted"),
              (data["summary"], 17, "blue")]
    for section in data["sections"]:
        if not section.get("heading") or not section.get("entries"):
            raise ValueError("每個交接段落都要有標題與內容")
        blocks.append((section["heading"], 17, "blue"))
        for entry in section["entries"]:
            for key in ("title", "detail"):
                if not isinstance(entry.get(key), str) or not entry[key].strip():
                    raise ValueError(f"交接項目缺少文字：{key}")
            blocks.extend([(entry["title"], 14, "ink"), (entry["detail"], 13, "ink")])
    if data.get("scope"):
        blocks.extend([("範圍與交接原件", 17, "blue"), (data["scope"], 11, "muted")])
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    surface = cairo.PDFSurface(str(output), W, H)
    ctx = cairo.Context(surface)
    page = 1
    y = 46
    color(ctx, "paper")
    ctx.paint()
    for value, size, tone in blocks:
        weight = cairo.FONT_WEIGHT_BOLD if size >= 14 else cairo.FONT_WEIGHT_NORMAL
        ctx.select_font_face("Noto Sans CJK TC", cairo.FONT_SLANT_NORMAL, weight)
        ctx.set_font_size(size)
        lines = []
        for paragraph in value.split("\n"):
            line = ""
            for character in paragraph:
                if line and ctx.text_extents(line + character).width > W - 84:
                    lines.append(line)
                    line = ""
                line += character
            lines.append(line)
        for index, line in enumerate(lines):
            reserve = size * 3 if size >= 14 and index == 0 else size
            if y + reserve > H - 52:
                text(ctx, str(page), W - 60, H - 20, 10, tone="muted")
                surface.show_page()
                color(ctx, "paper")
                ctx.paint()
                page += 1
                y = 46
            text(ctx, line, 42, y, size, weight, tone)
            y += size * 1.4
        y += 7
    text(ctx, str(page), W - 60, H - 20, 10, tone="muted")
    surface.finish()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        render(json.load(handle), args.output)


if __name__ == "__main__":
    main()
