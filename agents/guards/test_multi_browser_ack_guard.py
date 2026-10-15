import json
from pathlib import Path
import subprocess
import sys
import unittest

GUARD = Path(__file__).with_name('monitoring_comparison_guard.py')
DONE = 'tmp/homepage-live-20261004/docker-status-multi-homepage-v1.browser-done.json'


def hook(command, tool='Bash'):
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps({'tool_name':tool,'tool_input':{'command':command}}), capture_output=True, text=True, timeout=3)


def python(body):
    return "python3 - <<'PY'\n" + body + '\nPY'


class MultiAckTests(unittest.TestCase):
    def test_observed_failure_shapes_direct_ack_refused(self):
        # Parent-provided original excerpts composed as a replay, not a saved
        # complete original command. Guard parses them; assertions are not run.
        excerpts=[
            "assert len(b['rows'])>=3 and any('健康' in r for r in b['rows']) and sum('未知' in r for r in b['rows'])>=3",
            "cpu=format(s['cpu_percent'],'.6g').replace('e-0','e-').replace('e+0','e+'); mem=format(s['memory_percent'],'.2g'); assert cpu+'%' in source and mem+'%' in source",
        ]
        for assertion in excerpts:
            body="from pathlib import Path\nimport json\nroot=Path('tmp/homepage-live-20261004')\n"+assertion+"\np=root/'docker-status-multi-homepage-v1.browser-done.json';assert not p.exists();p.write_text(json.dumps(ack,ensure_ascii=False)+'\\n')"
            result=hook(python(body))
            self.assertEqual(result.returncode,2)
            self.assertIn('--ack-browser',result.stderr)

    def test_basic_path_propagation_and_write_sinks_refused(self):
        cases=[
            'p=Path('+repr(DONE)+'); alias=p; alias.write_bytes(b"{}")',
            'root=Path("tmp/homepage-live-20261004"); p=root / "docker-status-multi-homepage-v2.browser-done.json"; p.write_text("{}")',
            'p=Path("tmp/docker-status-multi-homepage-v2.json"); p=p.with_suffix(".browser-done.json"); p.write_text("{}")',
            'p='+repr(DONE)+'; open(p,"w").write("{}")',
            'p=Path('+repr(DONE)+'); p.open(mode="wb")',
        ]
        for body in cases:self.assertEqual(hook(python('from pathlib import Path\n'+body)).returncode,2)

    def test_readonly_and_quoted_documentation_allowed(self):
        for command in [python('from pathlib import Path\nPath('+repr(DONE)+').read_text()'),python('open('+repr(DONE)+',"rb").read()'),python('text="Path('+DONE+').write_text"\nprint(text)'),"cat <<'DOC'\nPath('"+DONE+"').write_text('{}')\nDOC"]:
            self.assertEqual(hook(command).returncode,0)

    def test_fixed_cli_and_old_modes_allowed(self):
        self.assertEqual(hook('python3 scripts/monitoring/verify_docker_source.py --ack-browser --output tmp/docker-status-multi-homepage-v2.json').returncode,0)
        self.assertEqual(hook(python('from pathlib import Path\nPath("docker-status-homepage-v1.browser-done.json").write_text("{}")')).returncode,0)

    def test_pure_definition_and_non_shell_edit_allowed(self):
        body='from pathlib import Path\ndef helper():\n    Path('+repr(DONE)+').write_text("{}")'
        self.assertEqual(hook(python(body)).returncode,0)
        self.assertEqual(hook(body,'apply_patch').returncode,0)


if __name__=='__main__':unittest.main()
