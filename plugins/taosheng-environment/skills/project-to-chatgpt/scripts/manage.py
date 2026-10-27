#!/usr/bin/env python3
"""Dispatch maintained helpers; all arguments remain structured subprocess arguments."""
import argparse
import subprocess
from pathlib import Path

service = Path.home() / 'Documents/Codex/tools/local-work-mcp'
runtime = Path.home() / 'Library/Application Support/LocalWorkMCP'
p = argparse.ArgumentParser(description='项目接入 ChatGPT 的本机操作入口')
p.add_argument('operation', choices=['registry', 'probe', 'connection'])
a, rest = p.parse_known_args()
script = {'registry':'project_registry.py', 'probe':'probe_project.py', 'connection':'manage_connection.py'}[a.operation]
python = runtime / 'venv/bin/python'
if not python.is_file() or not (service / script).is_file():
    raise SystemExit('未找到固定 MCP 服务或运行环境，请按当前项目接力恢复，勿另建重复隧道。')
raise SystemExit(subprocess.run([str(python),str(service / script),*rest]).returncode)
