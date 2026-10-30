#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import unittest

GUARD = Path(__file__).with_name('docker_expire_guard.py')


def hook(command):
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}}),
        capture_output=True, text=True, timeout=5,
    ).returncode


class DockerExpireGuardTests(unittest.TestCase):
    def test_unmarked_creation_is_rejected(self):
        for command in [
            'docker run -d postgres:16',
            'docker create --name t alpine',
            'docker container run alpine true',
            'docker volume create data',
            'sudo docker run alpine true',
            'cd /tmp && docker run -d -p 5432:5432 postgres:16',
            'docker volume create --label owner=me data',
            'docker run --label owner=me alpine',
        ]:
            with self.subTest(command=command):
                self.assertEqual(hook(command), 2)

    def test_marked_creation_is_accepted(self):
        for command in [
            'docker run --rm alpine true',
            'docker run -d --label expire=2026-11-02 postgres:16',
            'docker run --label=expire=2026-11-02T08:30 alpine',
            'docker run -l expire=never alpine',
            'docker volume create --label expire=2026-11-02 data',
            'docker create --rm alpine',
        ]:
            with self.subTest(command=command):
                self.assertEqual(hook(command), 0)

    def test_bad_value_and_volume_rm_are_rejected(self):
        for command in [
            'docker run --label expire=soon alpine',
            'docker run --label expire=2026-13-45 alpine',
            'docker volume create --rm data',
        ]:
            with self.subTest(command=command):
                self.assertEqual(hook(command), 2)

    def test_unrelated_commands_pass(self):
        for command in [
            'docker ps -a',
            'docker rm -v foo',
            'docker compose up -d',
            'echo "docker run alpine"',
            'docker exec foo run',
            'git commit -m "docker run x"',
            'rg "docker run" docs',
            'docker volume ls',
        ]:
            with self.subTest(command=command):
                self.assertEqual(hook(command), 0)


if __name__ == '__main__':
    unittest.main()
