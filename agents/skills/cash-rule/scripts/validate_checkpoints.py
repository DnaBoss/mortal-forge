#!/usr/bin/env python3
"""Read-only cash-rule 1.2 JSONL validation. Requires jsonschema==4.26.0.

Errors report locations/rules only, never record contents (which may be secret).
"""
import argparse
import json
import math
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = Path(__file__).resolve().parents[1] / 'schemas/checkpoint.schema.json'
TERMINAL = {'COMPLETE', 'CANCELLED', 'SUPERSEDED', 'FAILED'}


def validate_records(records, schema_path=SCHEMA):
    schema = json.loads(Path(schema_path).read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    tasks, steps, errors = {}, {}, []
    count = 0
    for count, record in enumerate(records, 1):
        if not finite_values(record):
            errors.append(f'第 {count} 筆：數值必須有限')
            continue
        invalid = list(validator.iter_errors(record))
        if invalid:
            errors.extend(f'第 {count} 筆：格式不符（{e.validator}）欄位 {"/".join(map(str, e.absolute_path)) or "(整筆)"} 值 {e.instance!r:.80}，規則 {e.validator_value!r:.160}' for e in invalid)
            continue
        task = record['task_id']
        previous = tasks.get(task)
        if previous is None:
            if record['previous_task_state'] is not None or record['iteration'] != 1:
                errors.append(f'第 {count} 筆：任務起點或輪次錯誤')
        else:
            if previous['task_state'] in TERMINAL:
                errors.append(f'第 {count} 筆：終止任務不得追加')
            if record['previous_task_state'] != previous['task_state']:
                errors.append(f'第 {count} 筆：任務狀態未接續')
            if record['iteration'] != previous['iteration'] + 1:
                errors.append(f'第 {count} 筆：輪次未接續')
        if record['step_id'] is not None:
            key = task, record['step_id']
            if record['previous_step_state'] != steps.get(key):
                errors.append(f'第 {count} 筆：步驟狀態未接續')
            steps[key] = record['step_state']
        if record['task_state'] == 'COMPLETE':
            if any(state not in {'DONE', 'SKIPPED', 'CANCELLED', 'SUPERSEDED'}
                   for (task_id, _), state in steps.items() if task_id == task):
                errors.append(f'第 {count} 筆：仍有未結束步驟')
        tasks[task] = record
    if not count:
        errors.append('檢查點檔案不得為空')
    return errors


def finite_values(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite_values(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_values(item) for item in value)
    return True


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON 欄位不可重複')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('非標準 JSON 數字')


def read_records(path):
    with Path(path).open() as stream:
        for line in stream:
            # Blank lines and NaN/Infinity are not valid checkpoint records.
            yield json.loads(line, parse_constant=_reject_constant, object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    args = parser.parse_args()
    try:
        errors = validate_records(read_records(args.jsonl))
    except (OSError, ValueError):
        print('無法讀取檢查點或 JSON 格式錯誤', file=sys.stderr)
        return 1
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('檢查點格式與狀態接續通過')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
