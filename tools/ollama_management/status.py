#!/usr/bin/env python3
"""Read local Ollama resource evidence without loading a model."""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

CGROUP = Path('/sys/fs/cgroup/system.slice/ollama.service')


def local_sample():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in {'MemAvailable', 'MemTotal', 'SwapFree', 'SwapTotal'}:
            memory[key] = int(value.split()[0]) * 1024
    groups = {}
    for name in ('memory.current', 'memory.peak', 'memory.high', 'memory.max',
                 'memory.swap.current', 'memory.swap.max', 'memory.events',
                 'memory.pressure', 'cpu.max', 'dmem.current', 'dmem.max'):
        path = CGROUP / name
        groups[name] = path.read_text().strip() if path.exists() else None
    gpu = {}
    for path in Path('/sys/class/drm').glob('card*/device/mem_info_*'):
        if path.is_file():
            try:
                gpu[str(path)] = int(path.read_text().strip())
            except (OSError, ValueError) as exc:
                gpu[str(path)] = {'error': str(exc)}
    return {'memory': memory, 'ollama_cgroup': groups, 'gpu': gpu,
            'host_memory_pressure': Path('/proc/pressure/memory').read_text().strip()}


def main():
    result = local_sample()
    service = subprocess.run(
        ['systemctl', 'show', 'ollama', '-p', 'ActiveState', '-p', 'MainPID',
         '-p', 'ControlGroup', '-p', 'MemoryHigh', '-p', 'MemoryMax',
         '-p', 'MemorySwapMax', '-p', 'CPUQuotaPerSecUSec', '-p', 'NRestarts'],
        capture_output=True, text=True, timeout=10, check=True)
    result['service'] = dict(line.split('=', 1) for line in service.stdout.splitlines())
    with urllib.request.urlopen('http://127.0.0.1:11434/api/ps', timeout=5) as response:
        result['loaded_models'] = json.load(response)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'ollama-status: {exc}', file=sys.stderr)
        sys.exit(1)
