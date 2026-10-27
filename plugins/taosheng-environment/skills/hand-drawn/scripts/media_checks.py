#!/usr/bin/env python3
"""Check caption timing, audio coverage and actual delivery streams.

Adapted from sweety-handdraw-video subtitle_contract.py / audio-and-ending.md
at 5206ec0d17f9b353e400b64b9c51ad69e721e02a (MIT; see ../LICENSE).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def validate_captions(captions, duration):
    previous_end = 0.
    for caption in captions:
        start, end = float(caption["start"]), float(caption["end"])
        text = caption["text"]
        if (not math.isfinite(start + end) or not 0 <= start < end <= duration
                or not isinstance(text, str) or not text.strip()):
            raise ValueError("字幕必须是视频内的有限正时段和非空文字")
        if start < previous_end - 1e-7:
            raise ValueError("字幕顺序错误或同时显示多条字幕；先修正时间线")
        previous_end = end


def probe_media(source):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                             "-of", "json", str(source)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def audio_input(root, options, duration, fps):
    if not options.get("source"):
        return None
    source = (Path(root) / options["source"]).expanduser().resolve()
    start = float(options.get("start", 0))
    if not source.is_file() or not math.isfinite(start) or not 0 <= start < duration:
        raise ValueError("声音需要存在的文件和视频内的有限开始时间")
    metadata = probe_media(source)
    streams = [stream for stream in metadata["streams"] if stream.get("codec_type") == "audio"]
    if not streams:
        raise ValueError("声音文件没有音轨")
    length = float(streams[0].get("duration", metadata["format"].get("duration", "nan")))
    if not math.isfinite(length) or length <= 0:
        raise ValueError("无法测量声音时长")
    if start + length > duration + 1 / fps:
        raise ValueError("声音超出视频结束时间，会截断尾音；先调整画面时长或核对声音")
    return {"source": str(source), "start": start, "duration": length}


def check_delivery(source, *, burned_captions=False, decode=False):
    source = Path(source).resolve()
    metadata = probe_media(source)
    streams = metadata["streams"]
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not videos:
        raise ValueError("交付文件没有视频流")
    subtitles = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
    if burned_captions and subtitles:
        raise ValueError("已声明硬字幕，却另含字幕轨；核对重复显示来源")
    suffixes = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
    sidecars = [path.name for path in source.parent.iterdir()
                if path.is_file() and path.suffix.lower() in suffixes
                and (path.stem.casefold() == source.stem.casefold()
                     or path.stem.casefold().startswith(source.stem.casefold() + "."))]
    if decode:
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(source),
                        "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"],
                       check=True, capture_output=True, text=True)
    return {"status": "technical-pass", "video": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "width": videos[0]["width"], "height": videos[0]["height"],
            "duration": float(metadata["format"]["duration"]),
            "fps": videos[0].get("avg_frame_rate"),
            "audio_streams": sum(stream.get("codec_type") == "audio" for stream in streams),
            "subtitle_streams": len(subtitles), "matching_sidecars": sidecars,
            "decoded": decode,
            "warnings": ["同名外挂字幕可能被播放器自动加载；检查实际播放或将其放入制作资料目录"]
                        if burned_captions and sidecars else [],
            "visual_review": "not_checked", "listening_review": "not_checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--burned-captions", action="store_true")
    parser.add_argument("--decode", action="store_true")
    parser.add_argument("--bin-dir", type=Path, help="项目已有 FFmpeg/ffprobe 目录，不修改全局 PATH")
    args = parser.parse_args()
    try:
        if args.bin_dir:
            directory = args.bin_dir.expanduser().resolve()
            if not directory.is_dir():
                raise ValueError("bin-dir 不存在")
            os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
        report = check_delivery(args.video, burned_captions=args.burned_captions, decode=args.decode)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"media_checks: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
