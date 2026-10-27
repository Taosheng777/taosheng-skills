#!/usr/bin/env python3
"""Inspect drawing schedules without rendering or generating media."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def part_review_sha256(action, source_sha256):
    return canonical_sha256({"source_sha256": source_sha256, "crop": action.get("crop"),
                             "parts": action.get("parts"), "white_key": action.get("white_key", 253)})


def validate_part_review(action, source_sha256):
    """Bind per-part observations to this image, crop and geometry, not a generic note."""
    parts = action.get("parts", [])
    ids = [part.get("id") for part in parts]
    if not ids or any(not isinstance(name, str) or not name.strip() for name in ids) or len(set(ids)) != len(ids):
        raise ValueError("分区需要非空且唯一的 id")
    review = action.get("part_review", {})
    if review.get("geometry_sha256") != part_review_sha256(action, source_sha256):
        raise ValueError("分区审查缺失或已过期：须绑定当前图片、裁切、分区与去底阈值")
    observations = review.get("observations", {})
    if review.get("status") != "pass" or set(observations) != set(ids):
        raise ValueError("每个分区须有实际审看结论，不能用一段整图通用评语代替")
    if any(not isinstance(value, str) or not value.strip() for value in observations.values()):
        raise ValueError("分区观察不能为空：说明边界、接触或遮挡，以及剩余区究竟包含什么")


def inspect_drawing(timeline, mode="traceable"):
    """One sampled pen position per frame is a lower bound, not an aesthetic score.

    An ink/color segment is one independent stroke or brush pass. Control points
    within that stroke stay in its points array; do not count each control point
    as a stroke. Timelapse keeps the same diagnostics but makes density a warning.
    """
    if mode not in {"traceable", "timelapse", "illustration_motion"}:
        raise ValueError("未知绘制方式")
    fps = float(timeline["canvas"]["fps"])
    duration = float(timeline["duration"])
    if not math.isfinite(fps + duration) or fps <= 0 or duration <= 0:
        raise ValueError("帧率和总时长必须为有限正数")
    errors, warnings, rows = [], [], []
    intervals = []
    previous_page_end = 0.
    for page in timeline.get("pages", []):
        page_start, page_end = float(page["start"]), float(page["end"])
        if (not math.isfinite(page_start + page_end) or not 0 <= page_start < page_end <= duration + 1e-6
                or page_start < previous_page_end - 1e-6):
            errors.append("最终页面时间无效、重叠或超出视频")
            continue
        previous_page_end = page_end
        for event in page.get("events", []):
            if event.get("caption") or event.get("role") in {"caption", "static"}:
                continue
            start, end = float(event["start"]), float(event["end"])
            hide = float(event.get("hide", page_end))
            if (not math.isfinite(start + end + hide)
                    or not page_start <= start < end <= min(hide, page_end) + 1e-6):
                errors.append("落笔事件超出最终视频或时间无效")
                continue
            asset = timeline["assets"][event["asset"]]
            segments = asset.get("segments", [])
            if not segments:
                if mode != "illustration_motion":
                    errors.append(f"{event['asset']}: 声称逐笔的事件缺少独立笔迹")
                continue
            if mode != "illustration_motion":
                intervals.append((start, end))
            frames = max(0, math.ceil(end * fps - 1e-9) - math.ceil(start * fps - 1e-9))
            active, missed, subframe, travel = 0, 0, 0, 0
            previous_end = 0.
            for segment in segments:
                a, b = float(segment["start"]), float(segment["end"])
                kind = segment.get("kind")
                if (not math.isfinite(a + b) or not 0 <= a <= b <= 1 + 1e-6
                        or a < previous_end - 1e-6 or kind not in {"ink", "color", "travel"}):
                    errors.append(f"{event['asset']}: 轨迹须有序、不重叠，且位于归一化 0..1")
                    break
                previous_end = b
                if kind == "travel":
                    travel += 1
                    continue
                active += 1
                absolute_a = start + a * (end - start)
                absolute_b = start + b * (end - start)
                subframe += absolute_b - absolute_a < 1 / fps - 1e-9
                missed += math.ceil(absolute_b * fps - 1e-9) <= math.ceil(absolute_a * fps - 1e-9)
            row = {"asset": event["asset"], "start": start, "end": end,
                   "drawing_seconds": end - start, "available_frames": frames,
                   "stroke_count": active, "travel_count": travel,
                   "subframe_strokes": subframe, "unsampled_strokes": missed,
                   "minimum_seconds_at_one_sample_per_stroke": active / fps}
            rows.append(row)
            if not active and mode != "illustration_motion":
                errors.append(f"{event['asset']}: 只有移笔，没有实际落笔；不能声称逐笔绘制")
            if active > frames:
                message = (f"{event['asset']}: {active} 笔只能分到 {frames} 帧；"
                           "无法逐笔显示。先减少碎路径/非必要纹理、调整笔顺或重排画面，不加速旁白凑时长")
                (errors if mode == "traceable" else warnings).append(message)
            elif missed:
                warnings.append(f"{event['asset']}: {missed} 笔没有落入采样时刻，代表段需检查突然补线与跳笔")
    intervals.sort()
    if any(left[1] > right[0] + 1e-6 for left, right in zip(intervals, intervals[1:])):
        errors.append("同一主笔的最终落笔事件重叠")
    if mode != "illustration_motion" and not rows:
        errors.append("最终时间线没有可核对的绘制事件")
    return {"status": "blocked" if errors else "engineering-pass", "mode": mode,
            "events": rows, "errors": errors, "warnings": warnings,
            "visual_quality": "not_checked", "part_semantics": "not_checked"}


def preview_parts(timeline_path, directory):
    """Export diagnostic masks from already-built assets; never redraw the source."""
    import numpy as np
    from PIL import Image
    timeline_path, directory = Path(timeline_path).resolve(), Path(directory).resolve()
    assets_dir = timeline_path.parent / "assets"
    if directory == assets_dir or assets_dir in directory.parents:
        raise ValueError("分区预览不能写进输入资产目录")
    timeline = json.loads(timeline_path.read_text())
    records = []
    for name, asset in timeline["assets"].items():
        if asset.get("type") != "illustration":
            continue
        if Path(name).name != name:
            raise ValueError("资产 id 必须是普通文件名")
        for suffix in (".png", ".npz"):
            source = assets_dir / (name + suffix)
            expected = timeline.get("input_hashes", {}).get(str(source))
            if expected and hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError("资产已变化，不能用旧分区审查：" + name)
        original = Image.open(assets_dir / (name + ".png")).convert("RGBA")
        white = Image.new("RGBA", original.size, "white")
        white.alpha_composite(original)
        pixels = np.asarray(white.convert("RGB"))
        with np.load(assets_dir / (name + ".npz"), allow_pickle=False) as archive:
            if "owners" not in archive:
                raise ValueError("插画资产缺少 owners 分区图：" + name)
            owners = archive["owners"]
        if owners.shape != pixels.shape[:2]:
            raise ValueError("分区图与原画尺寸不一致")
        directory.mkdir(parents=True, exist_ok=True)
        for part in asset["parts"]:
            selected = owners == part["index"]
            preview = np.rint(pixels.astype(float) * .18 + 255 * .82).astype("uint8")
            preview[selected] = pixels[selected]
            target = directory / f"{name}-part-{part['index']:02d}.png"
            Image.fromarray(preview).save(target)
            records.append({"asset": name, "part": part["id"], "path": str(target),
                            "visible_pixels": int(selected.sum()), "status": "not_checked"})
    return {"status": "not_checked", "parts": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("timeline", type=Path)
    audit.add_argument("--mode", choices=("traceable", "timelapse", "illustration_motion"), default="traceable")
    hashes = commands.add_parser("parts-hashes")
    hashes.add_argument("job", type=Path, help="job.json；只输出待审几何哈希，不填通过")
    previews = commands.add_parser("preview-parts")
    previews.add_argument("timeline", type=Path)
    previews.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            report = inspect_drawing(json.loads(args.timeline.read_text()), args.mode)
        elif args.command == "preview-parts":
            report = preview_parts(args.timeline, args.output)
        else:
            root = args.job.resolve().parent
            job = json.loads(args.job.read_text())
            rows = []
            for pi, page in enumerate(job["pages"]):
                for ai, action in enumerate(page.get("actions", [])):
                    if action["type"] == "illustration":
                        source = (root / action["source"]).resolve()
                        digest = hashlib.sha256(source.read_bytes()).hexdigest()
                        rows.append({"page": pi, "action": ai,
                                     "geometry_sha256": part_review_sha256(action, digest),
                                     "part_ids": [p["id"] for p in action["parts"]], "status": "not_checked"})
            report = {"status": "not_checked", "illustrations": rows}
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if report.get("errors") else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"drawing_checks: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
