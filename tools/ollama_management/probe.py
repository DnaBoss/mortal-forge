#!/usr/bin/env python3
"""Send one bounded synthetic request and record host pressure; never retry."""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from status import local_sample


def pressure_stop_reason(sample):
    full = next(line for line in sample['host_memory_pressure'].splitlines()
                if line.startswith('full '))
    avg10 = float(full.split('avg10=')[1].split()[0])
    if sample['memory']['MemAvailable'] < 20 * 1024**3:
        return 'host available memory below 20 GiB'
    if avg10 > 10:
        return 'host memory full avg10 above 10 percent'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must not exist')
    before = local_sample()
    refusal = pressure_stop_reason(before)
    if refusal:
        result = {'model': args.model, 'success': False, 'request_sent': False,
                  'stop_reason': refusal, 'before': before}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 1
    payload = {'model': args.model, 'messages': [
        {'role': 'user', 'content': 'Reply with the single word OK.'}],
        'think': False, 'stream': True,
        'options': {'num_ctx': 32768, 'num_predict': 16, 'temperature': 0}}
    samples = []
    stop_reason = None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='ollama-probe-') as tmp:
        directory = Path(tmp)
        request = directory / 'request.json'
        response = directory / 'response.jsonl'
        errors = directory / 'stderr.txt'
        request.write_text(json.dumps(payload))
        with response.open('w') as stdout, errors.open('w') as stderr:
            process = subprocess.Popen([
                'curl', '--silent', '--show-error', '--fail-with-body',
                '--connect-timeout', '5', '--max-time', '120', '--no-buffer',
                '-H', 'Content-Type: application/json', '--data-binary',
                '@' + str(request), 'http://127.0.0.1:11434/api/chat'],
                stdout=stdout, stderr=stderr)
            try:
                while process.poll() is None:
                    sample = local_sample()
                    sample['elapsed_seconds'] = round(time.monotonic() - started, 3)
                    samples.append(sample)
                    stop_reason = pressure_stop_reason(sample)
                    if not stop_reason and time.monotonic() - started > 125:
                        stop_reason = 'probe wall-clock deadline exceeded'
                    if stop_reason:
                        process.terminate()
                        break
                    time.sleep(1)
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        raw = response.read_text()
        chunks = []
        for line in raw.splitlines():
            try:
                chunks.append(json.loads(line))
            except ValueError:
                chunks.append({'error': 'invalid JSON response'})
        final = chunks[-1] if chunks else {}
        answer = ''.join(chunk.get('message', {}).get('content', '') for chunk in chunks)
        success = (stop_reason is None and process.returncode == 0
                   and final.get('done') is True and bool(answer.strip())
                   and not any('error' in chunk for chunk in chunks))
        result = {'model': args.model, 'success': success, 'exit_code': process.returncode,
                  'stop_reason': stop_reason, 'elapsed_seconds': time.monotonic() - started,
                  'answer': answer, 'final_response': final, 'stderr': errors.read_text(),
                  'before': before, 'after': local_sample(), 'samples': samples}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({key: result[key] for key in
                          ('model', 'success', 'exit_code', 'stop_reason', 'elapsed_seconds', 'answer')}))
        return 0 if success else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'ollama-probe: {exc}', file=sys.stderr)
        sys.exit(1)
