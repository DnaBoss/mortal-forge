#!/usr/bin/python3
import hashlib
import json
import os
from pathlib import Path
import subprocess

manifest = json.loads(Path(os.environ['CASH_DELIVERY_ARTIFACT']).read_text())
for entry in manifest['files']:
    if entry.get('installed') and hashlib.sha256(Path(entry['installed']).read_bytes()).hexdigest() != entry['sha256']:
        raise SystemExit('Installed version differs')
result = subprocess.run(['/home/cash/work_space/private/mortal-mcp/.venv/bin/python', manifest['smoke']], check=True, capture_output=True, timeout=30, text=True)
if not json.loads(result.stdout)['ok']:
    raise SystemExit('MCP check failed')
print(json.dumps({'version_sha256':os.environ['CASH_DELIVERY_SHA256'],'result':'pass','checks':[{'name':'installed_hashes','result':'pass'},{'name':'real_mcp_positive_and_negative','result':'pass'}]}))
