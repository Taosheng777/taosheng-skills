#!/usr/bin/env python3
"""Check the actual final composition against the project's video requirements.

The manifest must come from the final compositor, after all drawing, captions,
audio and overlays are connected. These checks do not infer visual truth from
metadata and never write a passing human/model review.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess

from drawing_checks import inspect_drawing, validate_part_review
from media_checks import audio_input, check_delivery, probe_media, validate_captions


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bound_json(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def validate_contract(contract):
    if contract.get("version") != 1:
        raise ValueError("制作约定需要 version=1")
    choices = {"drawing_mode": {"traceable", "timelapse", "illustration_motion"},
               "hand": {"visible", "hidden"}, "audio": {"narration", "music", "none"},
               "captions": {"burned", "soft", "none"}}
    for key, values in choices.items():
        if contract.get(key) not in values:
            raise ValueError(f"制作约定须明确 {key}，可选 {sorted(values)}")
    if not isinstance(contract.get("decision_basis"), str) or not contract["decision_basis"].strip():
        raise ValueError("制作约定须记录本次选择的依据；不能把默认选择写成用户确认")
    maximum = contract.get("max_duration_seconds")
    if maximum is not None and (isinstance(maximum, bool) or not math.isfinite(float(maximum)) or float(maximum) <= 0):
        raise ValueError("片长上限须为有限正数")
    actions = contract.get("required_actions")
    if not isinstance(actions, list):
        raise ValueError("制作约定须列 required_actions；确无情节动作时可为空数组")
    ids = []
    for action in actions:
        if (not isinstance(action, dict) or not isinstance(action.get("id"), str)
                or not action["id"].strip() or not isinstance(action.get("observable"), str)
                or not action["observable"].strip()):
            raise ValueError("每个必需动作要有 id 和能在画面中观察的条件 observable")
        ids.append(action["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("必需动作的 id 不能重复")
    return contract


def load_contract(root, reference):
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("完整视频任务缺少 contract；先记录本次制作约定，资产构建可用 --assets-only")
    path = (Path(root) / reference).expanduser().resolve()
    contract, digest = read_bound_json(path)
    return validate_contract(contract), digest, path


def validate_choices(contract, composition):
    """Check the final settings, never the defaults of an upstream asset job."""
    validate_contract(contract)
    duration = float(composition["duration"])
    canvas = composition["canvas"]
    fps = float(canvas["fps"])
    if (not math.isfinite(duration + fps) or duration <= 0 or fps <= 0
            or int(canvas["width"]) <= 0 or int(canvas["height"]) <= 0):
        raise ValueError("最终画幅、帧率与时长无效")
    if contract.get("max_duration_seconds") is not None and duration > float(contract["max_duration_seconds"]) + 1e-6:
        raise ValueError("包含片尾的最终时长超过本次上限")
    if type(composition.get("hand_visible")) is not bool:
        raise ValueError("最终合成须记录实际 hand_visible，而不是只读取素材的手部开关")
    if composition["hand_visible"] != (contract["hand"] == "visible"):
        raise ValueError("最终手部显示与制作约定不符")
    captions = composition.get("captions")
    if not isinstance(captions, list):
        raise ValueError("最终合成须提供实际字幕事件数组")
    validate_captions(captions, duration)
    if bool(captions) != (contract["captions"] != "none"):
        raise ValueError("最终字幕与制作约定不符；不能拿空字幕的资产检查代替成片检查")
    audio = composition.get("audio")
    if (audio is not None) != (contract["audio"] != "none"):
        raise ValueError("最终音频与制作约定不符；不能拿无声资产代替有声成片")
    if audio is not None and (not isinstance(audio, dict) or not audio.get("source")):
        raise ValueError("最终音频须记录实际母带/混音输入")
    windows = composition.get("action_windows", {})
    if not isinstance(windows, dict) or set(windows) != {a["id"] for a in contract["required_actions"]}:
        raise ValueError("最终合成须用 action_windows 对应每个必需动作的真实呈现时间")
    for window in windows.values():
        if len(window) != 2:
            raise ValueError("动作时间应为 [start, end]")
        start, end = map(float, window)
        if not math.isfinite(start + end) or not 0 <= start < end <= duration + 1e-6:
            raise ValueError("必需动作时间无效或超出成片")


def inspect_composition(contract, composition):
    validate_choices(contract, composition)
    if composition.get("scope") != "final_video":
        raise ValueError("检查对象不是最终视频时间线；资产、样片不能替代最终合成")
    report = inspect_drawing(composition, contract["drawing_mode"])
    for name, asset in composition.get("assets", {}).items():
        if asset.get("type") == "illustration":
            drawing_input = asset.get("drawing_input", {})
            if not drawing_input.get("source_sha256"):
                report["errors"].append(name + ": 最终插画缺少已绑定的分区审查；须保留 drawing_input")
                continue
            try:
                validate_part_review(drawing_input, drawing_input["source_sha256"])
            except (ValueError, TypeError, KeyError) as error:
                report["errors"].append(name + ": " + str(error))
    report["status"] = "blocked" if report["errors"] else "engineering-pass"
    return report


def required_reviews(contract, composition):
    checks = ["visual"]
    if contract["drawing_mode"] in {"traceable", "timelapse"}:
        checks.append("drawing")
    if contract["hand"] == "visible":
        checks.append("hand")
    if any(a.get("type") == "illustration" for a in composition.get("assets", {}).values()):
        checks.append("part_semantics")
    if contract["audio"] == "narration":
        checks.extend(["speech_content", "listening"])
    elif contract["audio"] == "music":
        checks.append("listening")
    checks.extend("action:" + a["id"] for a in contract["required_actions"])
    return checks


def review_targets(contract, composition):
    pages = composition.get("pages", [])
    scenes = [(float(p["start"]), float(p["end"])) for p in pages] or [(0., composition["duration"])]
    draws, illustrations = [], []
    for page in pages:
        for event in page.get("events", []):
            if event.get("caption") or event.get("role") in {"caption", "static"}:
                continue
            asset = composition["assets"][event["asset"]]
            if asset.get("segments"):
                draws.append((float(event["start"]), float(event["end"])))
            if asset.get("type") == "illustration":
                illustrations.append((float(event["start"]), float(event.get("hide", page["end"]))))
    targets = {"visual": {"coverage": "overlap", "intervals": scenes},
               "drawing": {"coverage": "cover", "intervals": draws},
               "hand": {"coverage": "cover", "intervals": draws or scenes},
               "part_semantics": {"coverage": "overlap", "intervals": illustrations},
               "speech_content": {"coverage": "cover", "intervals": [(0., composition["duration"])]},
               "listening": {"coverage": "cover", "intervals": [(0., composition["duration"])]}}
    for action in contract["required_actions"]:
        targets["action:" + action["id"]] = {"coverage": "cover", "intervals": [composition["action_windows"][action["id"]]]}
    return targets


def covers_windows(observed, expected, coverage):
    for begin, finish in expected:
        if coverage == "overlap":
            if not any(a < finish and b >= begin for a, b in observed):
                return False
            continue
        covered = begin
        for start, end in sorted(observed):
            if end < covered:
                continue
            if start > covered + 1e-6:
                break
            covered = max(covered, end)
            if covered >= finish - 1e-6:
                break
        if covered < finish - 1e-6:
            return False
    return True


def inspect_reviews(review, required, video_sha, assembly_sha, contract_sha, duration, targets=None):
    if review is None:
        return {"status": "needs-review", "pending": required, "failed": []}
    for key, expected in (("video_sha256", video_sha), ("assembly_sha256", assembly_sha), ("contract_sha256", contract_sha)):
        if review.get(key) != expected:
            raise ValueError("审看记录已过期或指向别的产物：" + key)
    checks = review.get("checks", {})
    pending, failed = [], []
    for name in required:
        item = checks.get(name, {})
        if item.get("status") == "fail":
            failed.append(name)
            continue
        evidence = item.get("evidence", "")
        if item.get("status") != "pass" or not isinstance(evidence, str) or not evidence.strip():
            pending.append(name)
            continue
        intervals = item.get("intervals", [])
        if not intervals:
            pending.append(name)
            continue
        parsed_intervals = []
        for interval in intervals:
            if len(interval) != 2:
                raise ValueError("审看片段应为 [start, end]")
            start, end = map(float, interval)
            if not math.isfinite(start + end) or not 0 <= start <= end <= duration + 1e-6:
                raise ValueError("审看片段超出当前成片")
            parsed_intervals.append((start, end))
        motion = name in {"drawing", "hand"} or name.startswith("action:")
        if motion:
            if item.get("method") != "continuous" or not any(b > a for a, b in parsed_intervals):
                pending.append(name)
                continue
        if name == "listening" and item.get("method") != "listened":
            pending.append(name)
            continue
        target = (targets or {}).get(name, {"coverage": "cover", "intervals": [(0., duration)]})
        if not covers_windows(parsed_intervals, target["intervals"], target["coverage"]):
            pending.append(name)
    return {"status": "review-failed" if failed else "needs-review" if pending else "reviewed",
            "pending": pending, "failed": failed}


def verify_final(contract_path, assembly_path, video_path, review_path=None):
    contract_path, assembly_path, video_path = map(lambda p: Path(p).resolve(), (contract_path, assembly_path, video_path))
    contract, contract_sha = read_bound_json(contract_path)
    validate_contract(contract)
    assembly, assembly_sha = read_bound_json(assembly_path)
    video_sha = sha256(video_path)
    if assembly.get("version") != 1 or assembly.get("contract_sha256") != contract_sha:
        raise ValueError("最终合成记录未绑定当前制作约定")
    if assembly.get("video_sha256") != video_sha:
        raise ValueError("最终合成记录与实际视频不匹配")
    composition = assembly["composition"]
    drawing = inspect_composition(contract, composition)
    if drawing["errors"]:
        return {"status": "blocked", "drawing": drawing, "video_sha256": video_sha}
    inputs = assembly.get("input_hashes")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("最终合成记录缺少实际素材、声音和渲染代码的 input_hashes")
    resolved_inputs = {}
    for name, expected in inputs.items():
        path = (assembly_path.parent / name).resolve()
        if sha256(path) != expected:
            raise ValueError("最终合成后的输入已变化：" + name)
        resolved_inputs[str(path)] = expected
    renderer_files = assembly.get("renderer_files")
    if not isinstance(renderer_files, list) or not renderer_files:
        raise ValueError("最终合成记录须列 renderer_files，绑定实际最终合成代码")
    if any(str((assembly_path.parent / name).resolve()) not in resolved_inputs for name in renderer_files):
        raise ValueError("最终合成代码未纳入输入哈希")
    audio = composition.get("audio")
    measured_audio = None
    if audio:
        source = (assembly_path.parent / audio["source"]).resolve()
        if str(source) not in resolved_inputs:
            raise ValueError("实际音频输入没有绑定哈希")
        measured_audio = audio_input(assembly_path.parent, audio, composition["duration"], composition["canvas"]["fps"])
    for asset in composition.get("assets", {}).values():
        if asset.get("type") == "illustration":
            source = str((assembly_path.parent / asset["source"]).resolve())
            if resolved_inputs.get(source) != asset["drawing_input"]["source_sha256"]:
                raise ValueError("分区审查没有绑定最终插画输入")
    technical = check_delivery(video_path, burned_captions=contract["captions"] == "burned", decode=True)
    actual = probe_media(video_path)
    canvas = composition["canvas"]
    if (technical["width"], technical["height"]) != (canvas["width"], canvas["height"]):
        raise ValueError("实际成片尺寸与最终合成记录不符")
    if abs(float(Fraction(technical["fps"])) - float(canvas["fps"])) > 1e-6:
        raise ValueError("实际成片帧率与最终合成记录不符")
    if abs(technical["duration"] - composition["duration"]) > max(.08, 1 / float(canvas["fps"])):
        raise ValueError("实际成片时长与最终合成记录不符")
    if contract.get("max_duration_seconds") is not None and technical["duration"] > float(contract["max_duration_seconds"]) + .001:
        raise ValueError("实际成片（包含编码后片尾）超过本次时长上限")
    if bool(technical["audio_streams"]) != (contract["audio"] != "none"):
        raise ValueError("实际成片音轨与制作约定不符")
    if measured_audio:
        audio_stream = next(stream for stream in actual["streams"] if stream.get("codec_type") == "audio")
        audio_end = float(audio_stream.get("start_time", 0)) + float(audio_stream.get("duration", actual["format"]["duration"]))
        if audio_end + 1 / float(canvas["fps"]) < measured_audio["start"] + measured_audio["duration"]:
            raise ValueError("最终编码音轨没有覆盖完整声音输入，须核对末句/截音")
    expected_subtitles = 1 if contract["captions"] == "soft" else 0
    if technical["subtitle_streams"] != expected_subtitles:
        raise ValueError("实际成片字幕轨与制作约定不符")
    review, review_sha = read_bound_json(review_path) if review_path else (None, None)
    reviewed = inspect_reviews(review, required_reviews(contract, composition), video_sha,
                               assembly_sha, contract_sha, composition["duration"], review_targets(contract, composition))
    if (sha256(contract_path) != contract_sha or sha256(assembly_path) != assembly_sha
            or sha256(video_path) != video_sha
            or any(sha256(name) != digest for name, digest in resolved_inputs.items())):
        raise ValueError("检查过程中输入或成片变化，检查结果不能用于当前版")
    if review_path and sha256(review_path) != review_sha:
        raise ValueError("检查过程中审看记录变化，须重新检查")
    return {"status": reviewed["status"], "technical": technical, "drawing": drawing,
            "review": reviewed, "contract_sha256": contract_sha,
            "assembly_sha256": assembly_sha, "video_sha256": video_sha,
            "review_sha256": review_sha,
            "limitation": "根据实际合成记录和提交的审看证据检查；不能自动理解画面或证明审听真实发生"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--assembly", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.bin_dir:
            if not args.bin_dir.is_dir():
                raise ValueError("bin-dir 不存在")
            os.environ["PATH"] = str(args.bin_dir.resolve()) + os.pathsep + os.environ.get("PATH", "")
        result = verify_final(args.contract, args.assembly, args.video, args.review)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result["status"] == "reviewed" else 3 if result["status"] == "needs-review" else 2
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        print(f"production_checks: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
