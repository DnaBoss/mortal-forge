import json
import os
import sys
import tempfile
from pathlib import Path

home = tempfile.mkdtemp()
os.environ["HOME"] = home
os.environ["USERPROFILE"] = home
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import install

claude = Path(home) / ".claude"
codex = Path(home) / ".codex"
claude.mkdir()
codex.mkdir()
other = {"hooks": [{"type": "command", "command": "echo mine", "timeout": 5}]}
(claude / "settings.json").write_text(json.dumps({"theme": "dark", "hooks": {"SessionStart": [other]}}))
(codex / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [other]}}))

install.HOOK_FILES = (claude / "settings.json", codex / "hooks.json")
install.register_hooks(True)
install.register_hooks(True)


def groups(path):
    return json.loads(path.read_text(encoding="utf-8"))["hooks"]["SessionStart"]


c, x = groups(claude / "settings.json"), groups(codex / "hooks.json")
assert len(c) == 2 and c[0] == other, c
assert json.loads((claude / "settings.json").read_text())["theme"] == "dark"
assert len(x) == 1 and x[0]["hooks"][0]["command"].endswith(" hint"), x
assert "PreToolUse" in json.loads((codex / "hooks.json").read_text())["hooks"]
assert (claude / "settings.json.bak-memory-tidy").exists()

install.register_hooks(False)
assert groups(claude / "settings.json") == [other]
assert "SessionStart" not in json.loads((codex / "hooks.json").read_text())["hooks"]

bad = claude / "settings.json"
bad.write_text("{oops")
assert "not valid JSON" in install.edit_hook_file(bad, True)
assert bad.read_text() == "{oops"
import re

scripts_dir = Path(install.__file__).resolve().parent
for name in install.SCRIPTS:
    for dep in re.findall(r"^import (\w+)$", (scripts_dir / name).read_text(encoding="utf-8"), re.M):
        assert not (scripts_dir / f"{dep}.py").exists() or f"{dep}.py" in install.SCRIPTS, f"{name} needs {dep}.py which is not copied"
print("hook merge ok")
