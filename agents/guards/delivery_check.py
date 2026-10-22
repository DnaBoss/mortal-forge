#!/usr/bin/env python3
"""Bounded, read-only delivery evidence check used by the existing Stop hook.

No commands, URLs or source services are executed. Artifact consistency is
checked; authenticity, authorization interpretation and runtime availability
still require the supervisor. Missing hidden completion cannot be inferred.
"""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

LIMIT = 1024 * 1024
MARKER = re.compile(r'^交付收據[：:]\s*`?([^`\r\n]+?)`?\s*$', re.M)


def read(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('收據或原件不存在／超過1MiB')
    data = path.read_bytes()
    if len(data) > LIMIT:
        raise ValueError('原件超過1MiB')
    return data


def artifact(ref, cwd):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ValueError('原件須有path與sha256')
    p = Path(ref['path'])
    p = p if p.is_absolute() else cwd / p
    data = read(p)
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError('原件指紋與收據不符')
    return data, p


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_receipt(receipt, cwd, session):
    if receipt.get('schema_version') != 1 or receipt.get('cwd') != str(cwd):
        raise ValueError('交付收據版本或工作區不符')
    if not nonempty(receipt.get('session_id')) or (session and receipt['session_id'] != session):
        raise ValueError('交付收據不是本工作階段')
    units = receipt.get('units')
    if not isinstance(units, list) or not units or len(units) > 32:
        raise ValueError('須列1至32個已驗完成單位')
    seen = set()
    for unit in units:
        identity = unit.get('id')
        if not nonempty(identity) or identity in seen:
            raise ValueError('完成單位識別碼缺失或重複')
        seen.add(identity)
        version = unit.get('version')
        # Version may be a small manifest binding large builds by their digests.
        _, version_path = artifact(version, cwd)
        validated = json.loads(artifact(unit.get('validation'), cwd)[0])
        checks = validated.get('checks')
        if validated.get('unit') != identity or validated.get('version_sha256') != version['sha256']:
            raise ValueError('必要驗證不是同單位／同版本')
        if not isinstance(checks, list) or not checks or any(
                not isinstance(c, dict) or not nonempty(c.get('name')) or c.get('result') != 'pass'
                for c in checks):
            raise ValueError('必要驗證缺失／失敗／略過／未跑')
        delivery = unit.get('delivery', {})
        status = delivery.get('status')
        if status in ('available', 'deployed'):
            if not nonempty(delivery.get('entrypoint')):
                raise ValueError('交付沒有可用入口')
            evidence = json.loads(artifact(delivery.get('readback'), cwd)[0])
            if evidence.get('unit') != identity or evidence.get('version_sha256') != version['sha256']:
                raise ValueError('交付讀回不是同單位／同版本')
            if evidence.get('entrypoint') != delivery['entrypoint'] or evidence.get('result') != 'pass':
                raise ValueError('可用入口或交付讀回未通過')
            if status == 'available':
                # Local usable entrypoints are checked without running them.
                entry = Path(delivery['entrypoint'])
                entry = entry if entry.is_absolute() else cwd / entry
                if not entry.is_file():
                    raise ValueError('可用入口檔不存在')
                artifact(delivery.get('entrypoint_artifact'), cwd)
                if (cwd / delivery['entrypoint_artifact']['path']).resolve() != entry.resolve():
                    raise ValueError('入口指紋不是交付入口')
            elif evidence.get('kind') != 'deployment_readback':
                raise ValueError('部署須有實際部署讀回，不能只用建置成功')
            if status == 'deployed' and (delivery.get('surface') == 'browser' or
                    urlparse(delivery['entrypoint']).hostname == 'fluke.exactlyone.dev'):
                upgrade = evidence.get('browser_upgrade', {})
                required = {'current_entry', 'previous_entry', 'missing_asset_negative', 'cache_revalidation'}
                if not isinstance(upgrade, dict) or set(upgrade) != required:
                    raise ValueError('瀏覽器交付缺新版、舊入口、缺包反例或快取重新驗證')
                for name in required:
                    proof = json.loads(artifact(upgrade[name], cwd)[0])
                    if (proof.get('check') != name or proof.get('result') != 'pass'
                            or proof.get('version_sha256') != version['sha256']):
                        raise ValueError('瀏覽器跨版驗證不是同版成功原件')

        elif status in ('unauthorized', 'paused', 'read_only', 'failed'):
            if not nonempty(delivery.get('reason')) or not nonempty(delivery.get('next_action')):
                raise ValueError('未交付須有具體理由與下一步')
            evidence = json.loads(artifact(delivery.get('evidence'), cwd)[0])
            if (evidence.get('unit') != identity or evidence.get('status') != status
                    or evidence.get('reason') != delivery['reason']):
                raise ValueError('未交付理由沒有相符的授權／暫停／唯讀／失敗原件')
            source, _ = artifact(evidence.get('source'), cwd)
            if not source.strip():
                raise ValueError('例外原指令／失敗輸出為空')
        else:
            raise ValueError('已驗完成單位未交付；不能只寫完成或稍後部署')


def problems(payload):
    text = payload.get('last_assistant_message', '')
    if not isinstance(text, str):
        return ['交付檢查沒有合法回答文字']
    # Ignore quoted documentation and code examples rather than treating them
    # as claims. Only explicit tested implementation completion activates this
    # fallback; progress, audits and tests alone do not force delivery.
    prose = re.sub(r'```[\s\S]*?```|^\s*>.*$', '', text, flags=re.M)
    markers = MARKER.findall(prose)
    completed = bool(re.search(r'(?:實作|修正|功能|版本|程式|產物).{0,16}(?:完成|做好)', prose))
    passed = bool(re.search(r'(?:測試|必要驗證|驗證).{0,32}(?:通過|全綠)', prose))
    if not markers and not (completed and passed):
        return []
    if len(markers) != 1:
        return ['已驗完成單位須列唯一「交付收據：<JSON路徑>」，核同版本入口或具體未交付理由']
    try:
        cwd = Path(payload.get('cwd') or '.').resolve()
        p = Path(markers[0])
        receipt = json.loads(read(p if p.is_absolute() else cwd / p))
        check_receipt(receipt, cwd, payload.get('session_id'))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # Do not echo artifact content, paths or reasons which may contain secrets.
        return ['交付收據未通過：核同版本指紋、必要驗證、實際入口／部署讀回或具體例外原件；不能僅靠完成文字']
    return []
