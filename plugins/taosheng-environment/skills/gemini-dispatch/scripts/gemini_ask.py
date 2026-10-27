#!/usr/bin/env python3
"""用 Antigravity CLI（agy）无头模式向 Gemini 发一次请求，只把结果打到 stdout。

用法：
  gemini_ask.py "问题"                       # 纯问答，默认 gemini-3.8-flash-high
  gemini_ask.py "总结 report.pdf" -d ~/某目录   # 允许读该目录
  gemini_ask.py "列出…" --schema schema.json  # 结构化输出，stdout 为 JSON
  cat prompt.txt | gemini_ask.py             # 提示词从 stdin 读

退出码：0 成功｜2 调用失败或返回异常｜3 权限被自动拒绝（结果为空）｜4 未登录
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MODEL = "gemini-3.8-flash-high"

DENIED_HINTS = {
    "read_file": "Gemini 要读的文件不在授权目录里，用 -d/--add-dir 放开所在目录",
    "write_file": "Gemini 想写文件；本 skill 不放开写权限，结果由调用方自己落盘",
    "command": "Gemini 想执行命令（扫描版 PDF 读不出文字时常见）；本 skill 不放开命令，"
               "先把页面渲染成图片（PyMuPDF），再用 -d 让它读图片",
}


def find_agy():
    agy = os.environ.get("AGY_BIN") or shutil.which("agy")
    if not agy and (Path.home() / ".local/bin/agy").exists():
        agy = str(Path.home() / ".local/bin/agy")
    if not agy:
        sys.exit("[gemini] 找不到 agy。安装：curl -fsSL https://antigravity.google/cli/install.sh | bash")
    return agy


def fail(code, msg, agy_stderr=""):
    tail = "\n".join(agy_stderr.strip().splitlines()[-5:])
    print(f"[gemini] {msg}" + (f"\n[agy stderr] {tail}" if tail else ""), file=sys.stderr)
    sys.exit(code)


def main():
    p = argparse.ArgumentParser(description="向 Gemini（agy 无头模式）发一次请求")
    p.add_argument("prompt", nargs="?", help="提示词；省略则从 stdin 读")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"模型 slug，默认 {DEFAULT_MODEL}；列表见 agy models")
    p.add_argument("-e", "--effort", choices=["low", "medium", "high", "max"])
    p.add_argument("-d", "--add-dir", action="append", default=[], help="允许 Gemini 读取的目录，可重复")
    p.add_argument("-s", "--schema", help="JSON schema 字符串或文件路径；给了就输出 structured_output")
    p.add_argument("-t", "--timeout", default="8m", help="单次超时，默认 8m")
    p.add_argument("--raw", help="把 agy 返回的完整 JSON 存到此路径")
    a = p.parse_args()

    prompt = a.prompt if a.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        fail(2, "提示词为空")

    dirs = []
    for d in a.add_dir:
        path = Path(d).expanduser().resolve()
        if not path.is_dir():
            fail(2, f"目录不存在：{path}")
        dirs.append(str(path))

    cmd = [find_agy(), "-p", prompt, "--model", a.model, "--output-format", "json",
           "--disable-slash-commands", "--print-timeout", a.timeout]
    if a.effort:
        cmd += ["--effort", a.effort]
    for d in dirs:
        cmd += ["--add-dir", d]
    if a.schema:
        cmd += ["--json-schema", a.schema]

    # 在空的临时目录里跑：Gemini 默认只能读这里，避免读到调用方项目里的文件或 AGENTS.md
    with tempfile.TemporaryDirectory(prefix="gemini-ask-") as ws:
        r = subprocess.run(cmd, cwd=ws, stdin=subprocess.DEVNULL, capture_output=True, text=True)

    if "sign in" in (r.stderr + r.stdout).lower():
        fail(4, "agy 未登录或登录已失效：请用户在终端运行 agy 完成 Google 登录", r.stderr)

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        fail(2, f"agy 返回的不是 JSON（exit={r.returncode}）：{r.stdout.strip()[:300]}", r.stderr)

    if a.raw:
        Path(a.raw).expanduser().write_text(json.dumps(data, ensure_ascii=False, indent=2))

    if data.get("status") != "SUCCESS":
        fail(2, f"调用失败 status={data.get('status')} error={data.get('error')}", r.stderr)

    structured = data.get("structured_output")
    response = (data.get("response") or "").strip()
    if a.schema and structured is not None:
        out = json.dumps(structured, ensure_ascii=False)
    elif response:
        out = response
    elif "auto-denied" in r.stderr:
        m = re.search(r'required the "([\w-]+)" permission', r.stderr)
        perm = m.group(1) if m else "?"
        hint = DENIED_HINTS.get(perm, f"工具权限 {perm} 被自动拒绝")
        fail(3, f"结果为空：{hint}", r.stderr)
    else:
        fail(2, "返回为空", r.stderr)

    u = data.get("usage") or {}
    print(f"[gemini] model={a.model} {data.get('duration_seconds', 0):.1f}s "
          f"in={u.get('input_tokens', '?')} out={u.get('output_tokens', '?')} "
          f"conv={data.get('conversation_id')}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
