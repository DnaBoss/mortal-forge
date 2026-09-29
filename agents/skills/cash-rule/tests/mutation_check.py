#!/usr/bin/env python3
"""Bounded semantic mutations of six requested gates; never edit live sources.
This score covers these named mutations, not all possible code mutations.
"""
import copy
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_checkpoints import SCHEMA, validate_records

ROOT = Path(__file__).resolve().parents[1]

def run():
    base = json.loads(SCHEMA.read_text())
    fixtures = {p.stem: [json.loads(x) for x in p.read_text().splitlines()]
                for p in (ROOT / 'tests/fixtures').glob('*.jsonl')}
    if any(bool(validate_records(rows)) == name.startswith('valid-')
           for name, rows in fixtures.items()):
        raise SystemExit('基準測試失敗，停止變異測試')
    mutations = []
    s = copy.deepcopy(base)
    s['allOf'] = [r for r in s['allOf'] if 'previous_step_state' not in r.get('if', {}).get('properties', {})]
    mutations.append(('remove-step-transition', s, 'invalid-step-skip'))
    s = copy.deepcopy(base)
    s['properties']['benchmark']['properties']['executors']['items']['required'].remove('input_tokens')
    mutations.append(('remove-executor-metric', s, 'invalid-benchmark-missing-metric'))
    s = copy.deepcopy(base)
    s['$defs']['avoidedMeasurement']['properties']['status']['enum'].append('exact')
    mutations.append(('allow-exact-savings', s, 'invalid-avoided-exact'))
    s = copy.deepcopy(base)
    for r in s['allOf']:
        if r.get('if', {}).get('properties', {}).get('decision') == {'const': 'continue'}:
            r['then']['properties']['task_state']['enum'].append('WAITING')
    mutations.append(('allow-continue-waiting', s, 'invalid-continue-waiting'))
    s = copy.deepcopy(base)
    s['properties']['actions']['items']['properties']['command'] = {'type': 'string'}
    mutations.append(('restore-raw-command', s, 'invalid-raw-command'))
    s = copy.deepcopy(base)
    for r in s['allOf']:
        if r.get('if', {}).get('properties', {}).get('previous_task_state') == {'const': None}:
            r['then']['properties']['task_state'] = {'const': 'DISCOVERING'}
    mutations.append(('reject-first-planned', s, 'valid-lifecycle'))
    killed = 0
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'schema.json'
        for name, schema, fixture in mutations:
            path.write_text(json.dumps(schema))
            accepted = not validate_records(fixtures[fixture], path)
            detected = accepted != fixture.startswith('valid-')
            killed += detected
            print(name, 'DETECTED' if detected else 'SURVIVED')
    print(f'{killed}/{len(mutations)} named mutations detected')
    return 0 if killed == len(mutations) else 1

if __name__ == '__main__':
    raise SystemExit(run())
