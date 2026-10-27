#!/usr/bin/env python3
"""Draw explicit timed scenes with the verified stroke engine; audio is optional."""
import argparse
import bisect
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "frames", "render"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--times", type=float, nargs="*")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--assets-only", action="store_true", help="仅构建可复用绘图资产，不代表完整视频已检查")
    args = parser.parse_args()
    if args.assets_only and args.command != "build":
        parser.error("--assets-only 仅用于 build")
    from run_video import inspect_runtime
    engine, python, root, env, profile = inspect_runtime(args.config, args.job)
    if Path(sys.executable).absolute() != python.absolute() and os.environ.get("HAND_DRAWN_REEXEC") != "1":
        env["HAND_DRAWN_REEXEC"] = "1"
        return subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]], env=env).returncode
    os.environ["PATH"] = env["PATH"]
    sys.path.insert(0, str(engine / "scripts"))
    from PIL import Image, ImageColor, ImageDraw
    import numpy as np
    from caption_layout import CaptionLayer
    from media_checks import audio_input
    from drawing_checks import inspect_drawing, validate_part_review
    from production_checks import load_contract, validate_choices, inspect_composition, verify_final
    import stroke_assets
    from hand_assets import prepare_hand
    from video_renderer import Renderer
    spec_bytes = (root / "job.json").read_bytes()
    spec_digest = hashlib.sha256(spec_bytes).hexdigest()
    spec = json.loads(spec_bytes)
    if spec.get("mode") != "timed" or spec.get("version") != 1:
        raise ValueError("job.json must declare version=1 and mode=timed")
    canvas = spec["canvas"]
    width, height, fps = (int(canvas[k]) for k in ("width", "height", "fps"))
    if width < 320 or height < 240 or width % 2 or height % 2 or not 1 <= fps <= 60:
        raise ValueError("Invalid output canvas")
    work, out = root / "work", root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    font_path, font_index = spec["font"]["path"], spec["font"].get("index", 0)
    path = lambda p: Path(p) if Path(p).is_absolute() else root / p
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if not spec.get("pages"):
        raise ValueError("At least one page is required")
    planned_duration = float(spec["pages"][-1]["end"])
    captions = CaptionLayer(spec, root, planned_duration)
    audio = audio_input(root, spec.get("audio", {}), planned_duration, fps)
    preview = args.command == "render" and (args.duration is not None or args.start != 0)
    contract = contract_digest = contract_path = None
    if spec.get("contract") or (args.command == "build" and not args.assets_only) or (args.command == "render" and not preview):
        contract, contract_digest, contract_path = load_contract(root, spec.get("contract"))
    final_settings = {"duration": planned_duration, "canvas": canvas,
                      "hand_visible": spec.get("hand", {}).get("enabled", True),
                      "captions": spec.get("captions", []), "audio": audio,
                      "action_windows": spec.get("action_windows", {})}
    if contract and ((args.command == "build" and not args.assets_only) or (args.command == "render" and not preview)):
        validate_choices(contract, final_settings)
        if contract["captions"] == "soft":
            raise ValueError("当前定时入口只支持硬字幕；软字幕须用支持它的合成器并经过共同最终检查，不能静默改为硬字幕")
    if args.command == "build":
        stroke_assets.configure_assets(work / "assets", font_path, font_index)
        reviews = {str(path(r["source"]).resolve()): r for r in spec.get("image_reviews", [])}
        assets, pages, ends, input_hashes = {}, [], [], {}
        prior_end = float(spec.get("cover_seconds", 0))
        if prior_end < 0 or not math.isfinite(prior_end):
            raise ValueError("Invalid cover duration")
        for index, page in enumerate(spec["pages"]):
            start, end = float(page["start"]), float(page["end"])
            if not math.isfinite(start + end) or start < prior_end - 1e-6 or end <= start:
                raise ValueError("Pages must be ordered, nonoverlapping and positive")
            prior_end = end
            events = []
            previous_draw_end = start
            for action in sorted(page.get("actions", []), key=lambda a: a["start"]):
                a, b = float(action["start"]), float(action["end"])
                if not math.isfinite(a + b) or not start <= a < b <= end or a < previous_draw_end - 1e-6:
                    raise ValueError("Drawing actions must fit the page and one pen")
                previous_draw_end = b
                name = f"element-{len(assets):04d}"
                kind = action["type"]
                if kind == "illustration":
                    source = path(action["source"])
                    input_hashes[str(source.resolve())] = sha(source)
                    review = reviews.get(str(source.resolve()), {})
                    if review.get("sha256") != sha(source) or not review.get("evidence"):
                        raise ValueError("Image requires a current, evidenced review: " + str(source))
                    crop = action.get("crop")
                    if crop is not None and crop not in review.get("approved_crops", []):
                        raise ValueError("Illustration crop has not been inspected")
                    if not args.assets_only:
                        validate_part_review(action, sha(source))
                    metadata = stroke_assets.build_illustration(name, source, action["width"], action["height"],
                        crop, action.get("parts"), action.get("white_key", 253))
                    metadata["drawing_input"] = {"source_sha256": sha(source), "crop": crop,
                        "parts": action.get("parts"), "white_key": action.get("white_key", 253),
                        "part_review": action.get("part_review", {})}
                elif kind == "text":
                    if not action["text"].strip() or "\n" in action["text"]:
                        raise ValueError("Text actions require a nonempty single line")
                    metadata = stroke_assets.build_text(name, action["text"], action["size"], action.get("color", "#302C26"))
                elif kind == "marker":
                    metadata = stroke_assets.build_brush(name, action["width"], action["height"],
                        action.get("color", "#EAC958"), action.get("style", "underline"), action.get("line_width"))
                elif kind == "path":
                    pw, ph = int(action["width"]), int(action["height"])
                    strokes = [np.asarray(points, dtype=float) for points in action["strokes"]]
                    if pw < 2 or ph < 2 or not strokes or any(points.ndim != 2 or points.shape[1] != 2 or len(points) < 2
                        or not np.isfinite(points).all() or (points < 0).any() or (points >= [pw, ph]).any() for points in strokes):
                        raise ValueError("Invalid native path geometry")
                    layer = Image.new("RGBA", (pw, ph))
                    draw = ImageDraw.Draw(layer)
                    line_width = int(action.get("line_width", 5))
                    if line_width < 1:
                        raise ValueError("Path line_width must be positive")
                    for points in strokes:
                        draw.line([tuple(p) for p in points], fill=action.get("color", "#386894"), width=line_width, joint="curve")
                    reveal, segments = stroke_assets.time_paths(strokes, (ph, pw))
                    metadata = stroke_assets.save_asset(name, np.asarray(layer), reveal, segments)
                else:
                    raise ValueError("Unknown drawing action: " + kind)
                x, y = int(action["x"]), int(action["y"])
                display_scale = float(action.get("display_scale", 1))
                if not math.isfinite(display_scale) or not .1 <= display_scale <= 4:
                    raise ValueError("display_scale must be within 0.1..4")
                if x < 0 or y < 0 or x + math.ceil(metadata["width"] * display_scale) > width or y + math.ceil(metadata["height"] * display_scale) > height:
                    raise ValueError("Drawing is outside the canvas: " + name)
                assets[name] = metadata
                hide = float(action.get("hide", end))
                if not math.isfinite(hide) or not b <= hide <= end:
                    raise ValueError("Drawing hide must follow its completion and remain within its page")
                events.append({"asset": name, "x": x, "y": y, "start": a, "end": b,
                    "hide": hide, "caption": False, "z": action.get("z", 30), "role": kind, "display_scale": display_scale})
            pages.append({"index": index, "start": start, "end": end, "events": events})
            ends.append(end)
        if not pages:
            raise ValueError("At least one page is required")
        hand = prepare_hand(spec.get("hand", {}), root, work, height, font_path, font_index)
        timeline = {"title": spec["title"], "canvas": canvas, "paper": spec.get("paper", "#FFFFFF"),
            "cover_seconds": spec.get("cover_seconds", 0), "duration": ends[-1], "pages": pages,
            "assets": assets, "hand": hand, "manifest_sha256": spec_digest, "profile": profile}
        timeline.update(final_settings)
        timeline.update(scope="assets_only" if args.assets_only else "final_video", contract_sha256=contract_digest)
        drawing_report = inspect_drawing(timeline, contract["drawing_mode"] if contract else "traceable")
        (work / "drawing-check.json").write_text(json.dumps(drawing_report, ensure_ascii=False, indent=2))
        if not args.assets_only:
            drawing_report = inspect_composition(contract, timeline)
            if drawing_report["errors"]:
                raise ValueError("绘制密度检查未通过；见 work/drawing-check.json：" + "; ".join(drawing_report["errors"]))
        for value in (spec.get("cover"), spec.get("audio", {}).get("source")):
            if value:
                input_hashes[str(path(value).resolve())] = sha(path(value))
        for source in [Path(font_path), Path(hand["source"]), *list((work / "assets").glob("*"))]:
            if source.is_file():
                input_hashes[str(source.resolve())] = sha(source)
        if captions.layers:
            input_hashes[str(captions.font_path)] = sha(captions.font_path)
        for name in ("render_timeline.py", "caption_layout.py", "media_checks.py", "drawing_checks.py", "production_checks.py"):
            source = Path(__file__).resolve().with_name(name)
            input_hashes[str(source)] = sha(source)
        lock = json.loads((Path(__file__).resolve().parents[1] / "references/engine-lock.json").read_text())
        locked_profile = next(item for item in lock["profiles"] if item["id"] == profile)
        for name, expected in locked_profile["files"].items():
            input_hashes[str(engine / name)] = expected
        if contract_path:
            input_hashes[str(contract_path)] = contract_digest
        timeline["input_hashes"] = input_hashes
        if spec.get("cover"):
            image = Image.open(path(spec["cover"])).convert("RGB")
            if image.size != (width, height):
                raise ValueError("Cover must match output canvas")
        else:
            image = Image.new("RGB", (width, height), timeline["paper"])
        if sha(root / "job.json") != spec_digest:
            raise ValueError("Job changed during build; no new timeline is committed")
        for source, expected in input_hashes.items():
            if sha(source) != expected:
                raise ValueError("Input changed during build; no new timeline is committed")
        image.save(out / "cover.building.png")
        input_hashes[str((out / "cover.png").resolve())] = sha(out / "cover.building.png")
        (work / "timeline.building.json").write_text(json.dumps(timeline, ensure_ascii=False))
        (out / "cover.building.png").replace(out / "cover.png")
        (work / "timeline.building.json").replace(work / "timeline.json")
        print(json.dumps({"scope": timeline["scope"], "pages": len(pages), "assets": len(assets),
                          "duration": ends[-1], "drawing_status": drawing_report["status"]}, ensure_ascii=False))
        return 0

    class TimedRenderer(Renderer):
        def __init__(self, directory):
            super().__init__(directory)
            # Decompress each reveal map once, rather than once per video frame.
            arrays = {}
            for name, archive in self.maps.items():
                arrays[name] = {key: archive[key] for key in archive.files}
                archive.close()
            self.maps = arrays
            self.scaled_artwork = {}

        def layer(self, event, t):
            scale = event.get("display_scale", 1)
            if scale == 1:
                return super().layer(event, t)
            key = (event["asset"], scale)
            if t >= event["end"] and key in self.scaled_artwork:
                return self.scaled_artwork[key]
            layer = super().layer(event, t)
            layer = layer.resize((round(layer.width * scale), round(layer.height * scale)), Image.Resampling.LANCZOS)
            if t >= event["end"]:
                self.scaled_artwork[key] = layer
            return layer

        def event_tip(self, event, progress):
            origin = np.array([event["x"], event["y"]])
            return origin + (super().event_tip(event, progress) - origin) * event.get("display_scale", 1)

        def frame(self, t):
            if t < self.timeline["cover_seconds"]:
                frame = self.cover.copy()
            else:
                index = max(0, bisect.bisect_right(self.starts, t) - 1)
                page = self.timeline["pages"][index]
                frame = self.page_frame(index, t, include_hand=spec.get("hand", {}).get("enabled", True)) if t < page["end"] else Image.new("RGBA", (width, height), self.paper)
            return captions.draw(frame, t).convert("RGB")

    renderer = TimedRenderer(root)
    if renderer.timeline["manifest_sha256"] != sha(root / "job.json"):
        raise ValueError("job.json changed; rebuild before render")
    for source, expected in renderer.timeline.get("input_hashes", {}).items():
        if sha(source) != expected:
            raise ValueError("An input changed after build; rebuild and review the affected output")
    if args.command == "render" and not preview:
        if renderer.timeline.get("contract_sha256") != contract_digest:
            raise ValueError("制作约定已变化或旧任务尚未绑定；重新构建")
        drawing_report = inspect_composition(contract, renderer.timeline)
        if drawing_report["errors"]:
            raise ValueError("最终绘制检查失败：" + "; ".join(drawing_report["errors"]))
    if args.command == "frames":
        for t in args.times or [p["end"] - .1 for p in renderer.timeline["pages"]]:
            if not 0 <= t < renderer.timeline["duration"]:
                raise ValueError("Frame time outside timeline")
            renderer.frame(t).save(out / f"frame-{t:07.2f}.png")
        return 0
    start = args.start
    duration = args.duration if args.duration is not None else renderer.timeline["duration"] - start
    if not math.isfinite(start + duration) or start < 0 or duration <= 0 or start + duration > renderer.timeline["duration"] + .001:
        raise ValueError("Render interval outside timeline")
    target = out / ("preview.mp4" if args.duration is not None or start else "film.mp4")
    temporary = target.with_name(target.stem + ".rendering.mp4")
    command = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
               "-r", str(fps), "-i", "-"]
    if audio:
        seek = max(0., start - audio["start"])
        delay = max(0., audio["start"] - start)
        filters = (f"adelay={round(delay * 1000)}:all=1," if delay else "") + "apad"
        command += ["-ss", str(seek), "-i", audio["source"], "-map", "0:v:0", "-map", "1:a:0", "-af", filters,
                    "-c:a", "aac", "-b:a", "192k"]
    else:
        command += ["-an"]
    command += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-t", str(duration),
                "-movflags", "+faststart", "-map_metadata", "-1", str(temporary)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration * fps)):
            process.stdin.write(renderer.frame(start + i / fps).tobytes())
            if i % (fps * 10) == 0:
                print(f"RENDER {i / fps:.1f} / {duration:.2f}", flush=True)
        process.stdin.close()
        if process.wait(timeout=60) != 0:
            raise RuntimeError("FFmpeg encoding failed")
    except BaseException:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        with contextlib.suppress(OSError):
            process.stdin.close()
        raise
    if renderer.timeline["manifest_sha256"] != sha(root / "job.json"):
        raise ValueError("Job changed during rendering; temporary video is not a verified output")
    for source, expected in renderer.timeline.get("input_hashes", {}).items():
        if sha(source) != expected:
            raise ValueError("Input changed during rendering; temporary video is not a verified output")
    temporary.replace(target)
    composition = dict(renderer.timeline)
    if preview:
        composition["scope"] = "preview"
    assembly = {"version": 1, "video_sha256": sha(target), "contract_sha256": contract_digest,
                "composition": composition, "input_hashes": renderer.timeline["input_hashes"],
                "renderer_files": [str(Path(__file__).resolve()), str(engine / "scripts/video_renderer.py")]}
    assembly_path = out / ("preview-composition.json" if preview else "composition.json")
    assembly_path.write_text(json.dumps(assembly, ensure_ascii=False, indent=2))
    (out / "render-record.json").write_text(json.dumps({"video_sha256": sha(target), "manifest_sha256": renderer.timeline["manifest_sha256"],
        "duration": duration, "start": start, "audio": bool(audio), "audio_input": audio,
        "status": "preview" if preview else "rendered-unreviewed", "assembly": str(assembly_path)}, indent=2))
    if not preview:
        result = verify_final(contract_path, assembly_path, target)
        (out / "production-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] == "blocked":
            raise ValueError("最终视频检查失败；见 outputs/production-check.json")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
