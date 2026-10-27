#!/usr/bin/env python3
"""Run a verified drawing engine using project-owned runtime configuration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def configured_path(config, key, base):
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"运行配置缺少 {key}")
    path = Path(value).expanduser()
    return path.absolute() if path.is_absolute() else (base / path).absolute()


def inspect_runtime(config_path, job_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    check = config.get("preflight")
    if check is not None:
        if not isinstance(check, list) or not check or not all(isinstance(x, str) and x for x in check):
            raise ValueError("preflight 必须是非空命令参数数组")
        subprocess.run(check, check=True, capture_output=True, text=True)
    engine = configured_path(config, "engine", config_path.parent)
    python = configured_path(config, "python", config_path.parent)
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("配置的 Python 不存在或不可执行")
    job = Path(job_path).expanduser().resolve()
    if not (job / "job.json").is_file():
        raise ValueError("任务目录缺少 job.json")
    lock = json.loads((ROOT / "references/engine-lock.json").read_text())
    matches = []
    for profile in lock["profiles"]:
        valid = True
        for name, expected in profile["files"].items():
            path = engine / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                valid = False
                break
        if valid:
            matches.append(profile["id"])
    if not matches:
        raise ValueError("引擎文件与已验证版本不符；先审查代码变化，不自动更新锁")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if config.get("bin_dir"):
        binary_dir = configured_path(config, "bin_dir", config_path.parent)
        if not binary_dir.is_dir():
            raise ValueError("bin_dir 不存在")
        env["PATH"] = str(binary_dir) + os.pathsep + env.get("PATH", "")
    return engine, python, job, env, matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("command", choices=("doctor", "build", "render", "verify", "finalize"))
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--assets-only", action="store_true")
    parser.add_argument("--assembly", type=Path, help="finalize 使用实际最终合成记录")
    parser.add_argument("--video", type=Path, help="finalize 使用实际交付视频")
    parser.add_argument("--review", type=Path, help="finalize 使用匹配当前视频的审看记录")
    args = parser.parse_args()
    if (args.preview or args.duration is not None) and args.command != "render":
        parser.error("preview/duration 仅适用于 render")
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error("duration 必须是有限正数")
    if args.assets_only and args.command != "verify":
        parser.error("assets-only 仅适用于 verify")
    if any((args.assembly, args.video, args.review)) and args.command != "finalize":
        parser.error("assembly/video/review 仅适用于 finalize")
    try:
        engine, python, job, env, profile = inspect_runtime(args.config, args.job)
        if args.inspect:
            print(json.dumps({"status": "verified-runtime", "profile": profile,
                              "engine": str(engine), "job": str(job)}, ensure_ascii=False))
            return 0
        if args.command == "finalize":
            from production_checks import load_contract
            spec = json.loads((job / "job.json").read_text())
            _, _, contract_path = load_contract(job, spec.get("contract"))
            if not all((args.assembly, args.video, args.review)):
                raise ValueError("finalize 需要 --assembly、--video、--review；旧引擎的工程通过不能替代成片审查")
            command = [str(python), str(ROOT / "scripts/production_checks.py"),
                       "--contract", str(contract_path), "--assembly", str(args.assembly.resolve()),
                       "--video", str(args.video.resolve()), "--review", str(args.review.resolve())]
            return subprocess.run(command, env=env).returncode
        command = [str(python), str(engine / "scripts/handdraw_video.py"), args.command, str(job)]
        if args.preview:
            command.append("--preview")
        if args.duration is not None:
            command += ["--duration", str(args.duration)]
        if args.assets_only:
            command.append("--assets-only")
        return subprocess.run(command, env=env).returncode
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"run_video: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
