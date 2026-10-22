#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


START = "<!-- stage-reporting:start -->"
END = "<!-- stage-reporting:end -->"

AGENTS_SECTION = """<!-- stage-reporting:start -->
## 项目级严格阶段汇报兜底

- 只有当一个明确阶段、里程碑或最终交付真正完成时才触发；普通问答和中间进度不触发。
- 本项目在全局主动汇报规则之外显式启用 Stop hook；在 Codex 中，漏报被拦后会产生一次新的 continuation。
- 阶段完成后的最终回复必须先用人话汇报，顺序固定为：
  1. 一句话说明这一阶段做成了什么。
  2. 用一个日常类比说明现在处于什么状态。
  3. 说明还有什么没做，以及不处理会发生什么。
  4. 只列用户现在真正需要决定的事项，并把选项写成选择后的后果；没有决策时明确写“你现在不用做任何事”。
- 不用路径、commit、测试数量或英文术语代替结论；这些证据放在汇报最后作为附注。
- 汇报必须基于当前文件和本轮验收证据，不按记忆复述。
- 上面第 4 步要单独成节，小标题里出现「要你拍板」或「你要决定」；确实没有决策时，原样写一句「你现在不用做任何事」。Stop hook 靠这一节判断汇报有没有落地。
- 不要在回复里加任何隐藏标记。早期版本用 HTML 注释做标记，实测会在终端里原样显示给用户，已废弃。
<!-- stage-reporting:end -->"""

HOOK_SOURCE = Path(__file__).with_name("plain_stage_report.py")


def hook_source():
    """判据只有一份：本 Skill 的 scripts/plain_stage_report.py。
    项目里那份是它的副本，改判据请改这里再重装，不要就地改项目副本。"""
    return HOOK_SOURCE.read_text(encoding="utf-8")


def resolve_root(value):
    candidate = Path(value or os.getcwd()).expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else candidate


def update_agents(path):
    text = path.read_text(encoding="utf-8") if path.exists() else "# 项目执行规则\n"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if pattern.search(text):
        updated = pattern.sub(AGENTS_SECTION, text)
    else:
        updated = text.rstrip() + "\n\n" + AGENTS_SECTION + "\n"
    path.write_text(updated, encoding="utf-8")


def hook_command(root):
    if (root / ".git").exists():
        return '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/plain_stage_report.py"'
    return "/usr/bin/python3 " + shlex.quote(str(root / ".codex/hooks/plain_stage_report.py"))


def update_hooks(path, command):
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    config.setdefault("description", "Project lifecycle hooks.")
    stop_groups = config.setdefault("hooks", {}).setdefault("Stop", [])
    handler = {
        "type": "command",
        "command": command,
        "timeout": 10,
        "statusMessage": "Checking stage report",
    }
    replaced = False
    for group in stop_groups:
        handlers = group.setdefault("hooks", [])
        for index, current in enumerate(handlers):
            if "plain_stage_report.py" in current.get("command", ""):
                handlers[index] = handler
                replaced = True
    if not replaced:
        stop_groups.append({"hooks": [handler]})
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    root = resolve_root(sys.argv[1] if len(sys.argv) > 1 else None)
    if not root.is_dir():
        raise SystemExit(f"项目目录不存在：{root}")
    hooks_dir = root / ".codex/hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    update_agents(root / "AGENTS.md")
    script = hooks_dir / "plain_stage_report.py"
    script.write_text(hook_source(), encoding="utf-8")
    script.chmod(0o755)
    update_hooks(root / ".codex/hooks.json", hook_command(root))
    print(f"STAGE_REPORTING_INSTALLED {root}")


if __name__ == "__main__":
    main()
