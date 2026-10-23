#!/usr/bin/env python3
"""Require persistent services for private projects to run through containers."""
import re

PRIVATE_ROOT = "/home/cash/work_space/private/"
CONTAINER_COMMAND = re.compile(r"\b(?:docker|podman)(?:\s+compose|\s+(?:run|create|start|restart))\b")
PERSISTENT_LAUNCH = re.compile(r"(?:^|[;&|]\s*)(?:nohup|pm2\s+start|systemd-run)\b", re.MULTILINE)


def problem(text: str, cwd: str = "") -> str | None:
    if PRIVATE_ROOT not in text and not cwd.startswith(PRIVATE_ROOT):
        return None
    unit_text = "[Service]" in text or "ExecStart=" in text or "WorkingDirectory=" in text
    manages_service = re.search(r"\bsystemctl(?:\s+--user)?\s+(?:enable|start|restart|try-restart|reenable)\b", text)
    persistent_shell = cwd.startswith(PRIVATE_ROOT) and PERSISTENT_LAUNCH.search(text)
    container_command = CONTAINER_COMMAND.search(text)
    if manages_service or ((unit_text or persistent_shell) and not container_command):
        return (
            "private 專案的常駐服務必須由 Docker 或 Podman 容器執行；"
            "主機 systemd 只能啟動容器編排，不可直接啟動專案程式。"
        )
    return None
