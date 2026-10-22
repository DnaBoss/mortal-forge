#!/usr/bin/python3
import hashlib
import json
import os
from pathlib import Path
import subprocess

manifest = json.loads(Path(os.environ['CASH_DELIVERY_ARTIFACT']).read_text())
for entry in manifest['files']:
    if hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() != entry['sha256']:
        raise SystemExit('Verified source changed; deployment stopped')
subprocess.run(['/usr/bin/python3', manifest['installer']], check=True, timeout=30)
