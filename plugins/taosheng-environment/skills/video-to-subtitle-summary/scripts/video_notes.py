#!/usr/bin/env python3
"""Run a cached video-to-reading-note preparation workflow."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from download_video_candidates import download_first_working_candidate, extract_candidates
from qwen_asr import QwenAsrError, normalize_api_base, parse_bool, transcribe
from tencent_flash_asr import TencentFlashAsrError, transcribe as transcribe_tencent


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ASR_BACKEND = "tencent"
DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "video-to-subtitle-summary" / "jobs"
TEMP_VIDEO_ROOT = Path("/tmp/video_analysis")
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_ID_QUERY_KEYS = ("modal_id", "aweme_id", "item_id")
ADOPT_FILES = (
    "video.mp4",
    "audio.mp3",
    "qwen-raw.txt",
    "qwen-corrected.txt",
    "qwen-raw.srt",
    "qwen-sentences.tsv",
    "qwen-result.json",
    "tencent-raw.txt",
    "tencent-corrected.txt",
    "tencent-raw.srt",
    "tencent-sentences.tsv",
    "tencent-result.json",
)


class WorkflowError(RuntimeError):
    pass


@contextmanager
def job_lock(job_dir: Path):
    # Keep the lock inode: unlinking it would let waiters lock different files.
    # flock is released by the OS even after a crash or SIGKILL.
    with (job_dir / ".job.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError(f"Job already running: {job_dir.name}; retry after it finishes") from exc
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    # Same-filesystem rename keeps readers on either the old or the new JSON.
    partial = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".manifest-", suffix=".tmp", delete=False) as stream:
            partial = Path(stream.name)
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, path)
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def is_url(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}


def safe_job_id(source: str) -> str:
    if is_url(source):
        parsed = urllib.parse.urlparse(source)
        query = urllib.parse.parse_qs(parsed.query)
        # Douyin web pages such as /jingxuan?modal_id=... or /user/<id>?modal_id=...
        # name the page in the path and the video in the query.
        for key in VIDEO_ID_QUERY_KEYS:
            candidate = re.sub(r"[^A-Za-z0-9_-]", "", (query.get(key) or [""])[0])
            if 4 <= len(candidate) <= 80:
                return candidate
        parts = [part for part in parsed.path.split("/") if part]
        segment = re.sub(r"[^A-Za-z0-9_-]", "", parts[-1] if parts else "")
        # A digit-free segment in front of a query (/watch?v=...) is a page name,
        # not a video id, so only the full URL can tell those videos apart.
        if 4 <= len(segment) <= 80 and (not parsed.query or re.search(r"\d", segment)):
            part_number = (query.get("p") or [""])[0]
            if part_number.isdigit() and int(part_number) > 1:
                return f"{segment}-p{int(part_number)}"
            return segment
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise WorkflowError(f"Input file does not exist: {path}")
    return f"local-{sha256_file(path)[:16]}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.stat().st_size == destination.stat().st_size and sha256_file(source) == sha256_file(destination):
            return
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> None:
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip().splitlines()[-1:] or process.stdout.strip().splitlines()[-1:]
        raise WorkflowError(f"Command failed: {command[0]}: {' '.join(detail)}")


def probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        process = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        try:
            return float(process.stdout.strip())
        except ValueError:
            pass

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise WorkflowError("ffmpeg or ffprobe is required")
    process = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", process.stderr)
    if not match:
        raise WorkflowError("Unable to read media duration with ffmpeg")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def require_audio_stream(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise WorkflowError("ffmpeg is required")
    process = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    if not re.search(r"Stream #\d+:\d+.*: Audio:", process.stderr):
        raise WorkflowError("downloaded file is not media with an audio track")


def extract_audio(video_path: Path, audio_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise WorkflowError("ffmpeg is required")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    # Later runs trust any existing audio file, so only a finished extraction may
    # take the final name; an interrupted one must not look complete.
    partial_path = audio_path.with_name(f"partial-{audio_path.name}")
    try:
        run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "64k",
                "-y",
                str(partial_path),
            ]
        )
    except BaseException:
        partial_path.unlink(missing_ok=True)
        raise
    os.replace(partial_path, audio_path)


def extract_review_frames(video_path: Path, duration: float, frames_dir: Path) -> list[str]:
    if shutil.which("ffmpeg") is None or duration <= 0:
        return []
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, fraction in enumerate((0.05, 0.5, 0.9), 1):
        destination = frames_dir / f"frame-{index:02d}.jpg"
        if not destination.exists():
            run_command(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{max(0.0, duration * fraction):.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    "-y",
                    str(destination),
                ]
            )
        paths.append(str(destination))
    return paths


def normalize_ai_douyin_endpoint(base: str) -> str:
    clean = base.rstrip("/")
    if clean.endswith("/api/v1"):
        return f"{clean}/video/download-url"
    if clean.endswith("/api"):
        return f"{clean}/v1/video/download-url"
    return f"{clean}/api/v1/video/download-url"


def resolve_online_video(source: str) -> dict[str, Any]:
    provider = os.getenv("VIDEO_INFO_PROVIDER", "ai-douyin").strip()
    if provider != "ai-douyin":
        raise WorkflowError("The integrated workflow currently requires VIDEO_INFO_PROVIDER=ai-douyin")
    api_key = os.getenv("AI_DOUYIN_API_KEY", "").strip()
    if not api_key:
        raise WorkflowError("AI_DOUYIN_API_KEY is not configured")
    endpoint = normalize_ai_douyin_endpoint(
        os.getenv("AI_DOUYIN_API_BASE", "https://top9.cc")
    )
    payload = json.dumps({"url": source}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WorkflowError(f"AI Douyin HTTP {exc.code}: {body[:500]}") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"AI Douyin resolution failed: {exc}") from exc


def acquire_source(source: str, job_dir: Path) -> tuple[Path | None, Path]:
    if is_url(source):
        video_path = job_dir / "video.mp4"
        if not video_path.exists():
            response = resolve_online_video(source)
            candidates = extract_candidates(response)
            if not candidates:
                raise WorkflowError("Video resolver returned no download candidate")
            try:
                download_first_working_candidate(
                    candidates, video_path, timeout=60, validate=require_audio_stream
                )
            except RuntimeError as exc:
                raise WorkflowError(f"Video download failed: {exc}") from exc
        audio_path = job_dir / "audio.mp3"
        if not audio_path.exists():
            extract_audio(video_path, audio_path)
        return video_path, audio_path

    input_path = Path(source).expanduser().resolve()
    suffix = input_path.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        video_path = job_dir / f"video{suffix}"
        link_or_copy(input_path, video_path)
        audio_path = job_dir / "audio.mp3"
        if not audio_path.exists():
            extract_audio(video_path, audio_path)
        return video_path, audio_path
    if suffix in AUDIO_SUFFIXES:
        audio_path = job_dir / f"audio{suffix}"
        link_or_copy(input_path, audio_path)
        return None, audio_path
    raise WorkflowError(f"Unsupported local media type: {suffix}")


def adopted_temp_video_paths(source_dir: Path, job_dir: Path, video_path: Path | None) -> list[str]:
    if video_path is None or not is_within(source_dir, TEMP_VIDEO_ROOT):
        return []
    paths = []
    cached_stat = video_path.stat()
    for candidate in sorted(source_dir.glob("video.*")):
        if candidate.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        candidate_stat = candidate.stat()
        if (candidate_stat.st_dev, candidate_stat.st_ino) == (cached_stat.st_dev, cached_stat.st_ino):
            paths.append(str(candidate.resolve()))
    return paths


def adopt_existing(source_dir: Path, job_dir: Path) -> tuple[Path | None, Path, list[str]]:
    if not source_dir.is_dir():
        raise WorkflowError(f"Adopt directory does not exist: {source_dir}")
    if source_dir.resolve() == job_dir.resolve():
        raise WorkflowError("Adopt directory must differ from the target job directory")
    copied = 0
    for name in ADOPT_FILES:
        source = source_dir / name
        if source.exists():
            destination = job_dir / name
            if destination.suffix in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
                link_or_copy(source, destination)
            else:
                # Transcripts get rewritten in place by later runs; a hard link
                # would carry those writes back into the adopted directory.
                destination.unlink(missing_ok=True)
                shutil.copy2(source, destination)
            copied += 1
    if copied == 0:
        raise WorkflowError("Adopt directory contains no recognized workflow files")
    frame_source = source_dir / "frame-001.png"
    if frame_source.exists():
        link_or_copy(frame_source, job_dir / "frames" / "frame-source.png")
    video_candidates = sorted(job_dir.glob("video.*"))
    audio_candidates = sorted(job_dir.glob("audio.*"))
    if not audio_candidates and video_candidates:
        extract_audio(video_candidates[0], job_dir / "audio.mp3")
        audio_candidates = [job_dir / "audio.mp3"]
    if not audio_candidates:
        raise WorkflowError("Adopted job has no audio or video")
    video_path = video_candidates[0] if video_candidates else None
    return video_path, audio_candidates[0], adopted_temp_video_paths(source_dir, job_dir, video_path)


def build_context(title: str | None, author: str | None, resonance: str | None) -> str | None:
    parts = []
    if title:
        parts.append(f"视频标题：{title}")
    if author:
        parts.append(f"作者：{author}")
    if resonance:
        parts.append(f"用户特别关注：{resonance}")
    return "；".join(parts) or None


def run_faster_whisper(audio_path: Path, job_dir: Path) -> dict[str, Any]:
    python = os.getenv("FW_PYTHON", "").strip()
    default_python = Path.home() / ".cache" / "video-to-subtitle-summary" / "faster-whisper-venv" / "bin" / "python"
    if not python:
        python = str(default_python) if default_python.exists() else sys.executable
    clean_env = os.environ.copy()
    for key in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        clean_env.pop(key, None)
    raw_path = job_dir / "faster-whisper" / "text.txt"
    previous_raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else None
    run_command(
        [
            python,
            str(SKILL_DIR / "scripts" / "transcribe_faster_whisper.py"),
            str(audio_path),
            "--output-dir",
            str(job_dir / "faster-whisper"),
            "--language",
            os.getenv("QWEN_LANGUAGE", "zh"),
        ],
        env=clean_env,
    )
    srt_path = job_dir / "faster-whisper" / "subtitle.srt"
    transcript = raw_path.read_text(encoding="utf-8")
    if not transcript.strip():
        raise WorkflowError("faster-whisper transcript is empty")
    # Own file name and a real copy: the Qwen slot may hold another backend's
    # edits, and a hard link would let corrections rewrite the raw transcript.
    corrected_path = job_dir / "faster-whisper-corrected.txt"
    corrected_preserved = corrected_path.exists() and corrected_path.read_text(encoding="utf-8") not in (
        previous_raw,
        transcript,
    )
    if not corrected_preserved:
        shutil.copyfile(raw_path, corrected_path)
    outputs = {
        "model": f"faster-whisper:{os.getenv('FW_MODEL_SIZE', 'small')}",
        "timestamp_quality": "segment",
        "raw_text": str(raw_path),
        "corrected_text": str(corrected_path),
        "srt": str(srt_path),
    }
    if corrected_preserved:
        outputs["corrected_text_preserved"] = True
    return outputs


def run_tencent_flash(audio_path: Path, job_dir: Path) -> dict[str, Any]:
    credentials = {
        "appid": os.getenv("TENCENT_APPID", "").strip(),
        "secret_id": os.getenv("TENCENT_SECRET_ID", "").strip(),
        "secret_key": os.getenv("TENCENT_SECRET_KEY", "").strip(),
    }
    missing = [key for key, value in credentials.items() if not value]
    if missing:
        names = {
            "appid": "TENCENT_APPID",
            "secret_id": "TENCENT_SECRET_ID",
            "secret_key": "TENCENT_SECRET_KEY",
        }
        raise WorkflowError(
            "Tencent ASR credentials are not configured: "
            + ", ".join(names[key] for key in missing)
        )
    prepared_audio = audio_path
    if audio_path.suffix.lower() != ".mp3":
        prepared_audio = job_dir / "audio-tencent.mp3"
        if not prepared_audio.exists():
            extract_audio(audio_path, prepared_audio)
    return transcribe_tencent(prepared_audio, job_dir, **credentials)


def adopted_asr_outputs(job_dir: Path) -> dict[str, Any] | None:
    candidates = (
        (
            "tencent",
            "tencent-flash:16k_zh",
            "sentence_and_word",
        ),
        (
            "qwen",
            "qwen3-asr-flash-filetrans",
            "sentence_and_word",
        ),
    )
    for prefix, model, timestamp_quality in candidates:
        corrected = job_dir / f"{prefix}-corrected.txt"
        if not corrected.exists():
            continue
        outputs: dict[str, Any] = {
            "model": model,
            "timestamp_quality": timestamp_quality,
            "corrected_text": str(corrected),
        }
        for key, suffix in (
            ("raw_text", "raw.txt"),
            ("srt", "raw.srt"),
            ("sentences_tsv", "sentences.tsv"),
            ("result_json", "result.json"),
        ):
            path = job_dir / f"{prefix}-{suffix}"
            if path.exists():
                outputs[key] = str(path)
        return outputs
    return None


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", value.strip())
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-. ")
    return (cleaned or fallback)[:80]


def build_writing_brief(job_dir: Path, manifest: dict[str, Any]) -> Path:
    transcript_path = Path(manifest["outputs"]["corrected_text"])
    transcript = transcript_path.read_text(encoding="utf-8").strip()
    resonance = manifest.get("resonance") or (
        "用户尚未点明具体共鸣。保留原意，并把可能的触动写成开放问题，不替用户虚构人生经历。"
    )
    title = manifest.get("title") or "待从画面或正文确认"
    author = manifest.get("author") or "待确认"
    source = manifest["source"]
    content = f"""# 视频写作素材

## 用户真正想留下的点

{resonance}

## 来源信息

- 标题：{title}
- 作者：{author}
- 来源：{source}
- 时长：{manifest['duration_seconds']:.1f} 秒
- ASR：{manifest['asr_model']}

## 最小校订稿

{transcript}

## 成文边界

- 写成一篇能直接读进去的中文文章，不拆成知识卡、摘要和主题地图。
- 用户明确的共鸣点是文章主轴；视频的其他内容只作背景。
- 不虚构用户经历，不把 ASR 可能的误识别写成确定事实。
- 默认只用少量大章节；来源与转写链接集中放在文末。
"""
    brief_path = job_dir / "写作素材.md"
    brief_path.write_text(content, encoding="utf-8")
    return brief_path


def export_to_vault(job_dir: Path, manifest: dict[str, Any], vault: Path) -> dict[str, str]:
    if not (vault / "10-文章").is_dir() or not (vault / "98-附件").is_dir():
        raise WorkflowError(f"Not a compatible reading vault: {vault}")
    export_root = vault / "98-附件" / "视频转写"
    recorded = manifest.get("vault_attachment_dir")
    if recorded and Path(recorded).parent == export_root and Path(recorded).is_dir():
        attachment_dir = Path(recorded)
    else:
        label = manifest.get("title") or manifest["job_id"]
        base_name = f"{date.today().isoformat()}-{slugify(label, manifest['job_id'])}"
        export_root.mkdir(parents=True, exist_ok=True)
        attempt = 0
        while True:
            suffix = "" if attempt == 0 else f"-{manifest['job_id']}"
            if attempt > 1:
                suffix += f"-{attempt}"
            attachment_dir = export_root / (base_name + suffix)
            try:
                # Different jobs hold different locks: claim the export directory
                # atomically so simultaneous same-title exports cannot overwrite.
                attachment_dir.mkdir()
                break
            except FileExistsError:
                attempt += 1
    output_map = {
        "raw_text": "原始转写.txt",
        "corrected_text": "最小校订稿.txt",
        "srt": "时间轴字幕.srt",
        "sentences_tsv": "句级时间轴.tsv",
        "result_json": "完整识别结果.json",
    }
    for key, destination_name in output_map.items():
        source_value = manifest["outputs"].get(key)
        if not source_value:
            continue
        source_path = Path(source_value)
        if source_path.exists():
            shutil.copy2(source_path, attachment_dir / destination_name)
    relative_corrected = (attachment_dir / "最小校订稿.txt").relative_to(vault).as_posix()
    return {
        "attachment_dir": str(attachment_dir),
        "corrected_wikilink": f"[[{relative_corrected}|查看校订转写稿]]",
    }


def is_complete_cache(manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        corrected = Path(manifest["outputs"]["corrected_text"])
        return manifest.get("status") == "complete" and corrected.exists()
    except (OSError, KeyError, json.JSONDecodeError, TypeError):
        return False


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cleanup_original_video(
    job_dir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    confirmed: bool,
    temporary_root: Path = TEMP_VIDEO_ROOT,
) -> dict[str, Any]:
    if not confirmed:
        raise WorkflowError(
            "Refusing to delete video without --confirm-note-reviewed after explicit user confirmation"
        )
    if manifest.get("status") != "complete":
        raise WorkflowError("Refusing to delete video before the transcription job is complete")
    corrected_value = manifest.get("outputs", {}).get("corrected_text")
    if not corrected_value or not Path(corrected_value).exists():
        raise WorkflowError("Refusing to delete video because the corrected transcript is missing")

    raw_paths = manifest.get("owned_video_paths") or []
    if not raw_paths and manifest.get("video_path"):
        raw_paths = [manifest["video_path"]]
    candidate_paths: list[Path] = []
    seen: set[Path] = set()
    allowed_temp_dir = temporary_root.resolve() / str(manifest.get("job_id", job_dir.name))
    for raw_path in raw_paths:
        candidate = Path(raw_path).expanduser().resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.suffix.lower() not in VIDEO_SUFFIXES or not candidate.name.startswith("video"):
            raise WorkflowError(f"Refusing unexpected video cleanup target: {candidate}")
        if not is_within(candidate, job_dir) and not is_within(candidate, allowed_temp_dir):
            raise WorkflowError(f"Refusing video cleanup outside owned cache paths: {candidate}")
        candidate_paths.append(candidate)

    existing = [path for path in candidate_paths if path.exists()]
    inode_records: dict[tuple[int, int], dict[str, int]] = {}
    for path in existing:
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        record = inode_records.setdefault(
            key,
            {"size": stat.st_size, "initial_links": stat.st_nlink, "deleted_links": 0},
        )
        record["deleted_links"] += 1
    for path in existing:
        path.unlink()

    logical_bytes = sum(record["size"] for record in inode_records.values())
    estimated_released = sum(
        record["size"]
        for record in inode_records.values()
        if record["deleted_links"] >= record["initial_links"]
    )
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest["video_path"] = None
    manifest["owned_video_paths"] = []
    manifest["video_cleanup_status"] = "deleted" if existing else "already_absent"
    manifest["video_deleted_at"] = now
    manifest["video_deleted_path_count"] = len(existing)
    manifest["video_deleted_logical_bytes"] = logical_bytes
    manifest["video_estimated_released_bytes"] = estimated_released
    manifest["updated_at"] = now
    save_manifest(manifest_path, manifest)
    return {
        "cleanup_status": manifest["video_cleanup_status"],
        "deleted_path_count": len(existing),
        "logical_bytes_removed": logical_bytes,
        "estimated_bytes_released": estimated_released,
        "preserved": ["audio", "transcripts", "subtitles", "recognition_json", "writing_brief"],
    }


def process(args: argparse.Namespace) -> dict[str, Any]:
    load_env_file(SKILL_DIR / ".env")
    source = args.source
    job_id = safe_job_id(source)
    cache_root = Path(args.cache_root or os.getenv("VIDEO_CACHE_DIR", DEFAULT_CACHE_ROOT)).expanduser().resolve()
    job_dir = cache_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    with job_lock(job_dir):
        return process_locked(args, source, job_id, job_dir)


def process_locked(args: argparse.Namespace, source: str, job_id: str, job_dir: Path) -> dict[str, Any]:
    manifest_path = job_dir / "manifest.json"

    if args.cleanup_video:
        if args.force or args.export_vault or args.adopt_dir:
            raise WorkflowError(
                "--cleanup-video cannot be combined with --force, --export-vault, or --adopt-dir"
            )
        if not is_complete_cache(manifest_path):
            raise WorkflowError("A complete cached job is required before video cleanup")
        manifest = load_manifest(manifest_path)
        cleanup = cleanup_original_video(
            job_dir,
            manifest_path,
            manifest,
            confirmed=args.confirm_note_reviewed,
        )
        return {
            "job_id": job_id,
            "status": manifest["status"],
            "manifest": str(manifest_path),
            "cleanup": cleanup,
        }
    if args.confirm_note_reviewed:
        raise WorkflowError("--confirm-note-reviewed is only valid with --cleanup-video")

    cache_hit = is_complete_cache(manifest_path) and not args.force
    if cache_hit:
        manifest = load_manifest(manifest_path)
        if args.qwen_model == "filetrans" and manifest.get("timestamp_quality") == "whole_audio_only":
            raise WorkflowError(
                "Cached transcript only has whole-audio timestamps; --qwen-model filetrans needs a new "
                "paid transcription, so re-run with --force to confirm"
            )
        metadata_changed = False
        for key in ("title", "author", "resonance"):
            value = getattr(args, key)
            if value and manifest.get(key) != value:
                manifest[key] = value
                metadata_changed = True
        if args.adopt_dir and manifest.get("video_path"):
            adopted_paths = adopted_temp_video_paths(
                Path(args.adopt_dir).expanduser().resolve(),
                job_dir,
                Path(manifest["video_path"]),
            )
            owned_paths = list(dict.fromkeys([manifest["video_path"], *adopted_paths]))
            if manifest.get("owned_video_paths") != owned_paths:
                manifest["owned_video_paths"] = owned_paths
                metadata_changed = True
        if metadata_changed:
            manifest["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            save_manifest(manifest_path, manifest)
    else:
        if args.adopt_dir:
            video_path, audio_path, adopted_video_paths = adopt_existing(
                Path(args.adopt_dir).expanduser().resolve(), job_dir
            )
        else:
            video_path, audio_path = acquire_source(source, job_dir)
            adopted_video_paths = []
        duration = probe_duration(audio_path)
        frames = extract_review_frames(video_path, duration, job_dir / "frames") if video_path else []
        backend = os.getenv("ASR_BACKEND", DEFAULT_ASR_BACKEND).strip().lower()
        adopted_outputs = adopted_asr_outputs(job_dir) if args.adopt_dir else None
        if adopted_outputs:
            outputs = adopted_outputs
        elif backend == "tencent":
            outputs = run_tencent_flash(audio_path, job_dir)
        elif backend == "qwen":
            api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
            if not api_key:
                raise WorkflowError("DASHSCOPE_API_KEY is not configured")
            outputs = transcribe(
                audio_path,
                job_dir,
                duration_seconds=duration,
                model_selection=args.qwen_model,
                language=os.getenv("QWEN_LANGUAGE", "zh") or None,
                enable_itn=parse_bool(os.getenv("QWEN_ENABLE_ITN", "false")),
                enable_words=parse_bool(os.getenv("QWEN_ENABLE_WORDS", "true"), True),
                context=build_context(args.title, args.author, args.resonance),
                api_key=api_key,
                api_base=normalize_api_base(os.getenv("DASHSCOPE_API_BASE")),
                compatible_api_base=os.getenv("DASHSCOPE_COMPATIBLE_BASE"),
                poll_interval=2.0,
                timeout_seconds=1800.0,
            )
        elif backend == "faster-whisper":
            outputs = run_faster_whisper(audio_path, job_dir)
        else:
            raise WorkflowError(f"Unsupported ASR_BACKEND for integrated workflow: {backend}")
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "job_id": job_id,
            "source": source,
            "title": args.title,
            "author": args.author,
            "resonance": args.resonance,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "media_sha256": sha256_file(video_path or audio_path),
            "video_path": str(video_path) if video_path else None,
            "owned_video_paths": (
                list(dict.fromkeys([str(video_path), *adopted_video_paths])) if video_path else []
            ),
            "audio_path": str(audio_path),
            "review_frames": frames,
            "asr_model": outputs["model"],
            "timestamp_quality": outputs.get("timestamp_quality"),
            "outputs": outputs,
        }
        # A forced re-run still owns the vault folder its earlier export created.
        try:
            recorded_export = load_manifest(manifest_path).get("vault_attachment_dir")
        except (OSError, ValueError):
            recorded_export = None
        if recorded_export:
            manifest["vault_attachment_dir"] = recorded_export
        save_manifest(manifest_path, manifest)

    brief_path = build_writing_brief(job_dir, manifest)
    export_result = None
    if args.export_vault:
        export_result = export_to_vault(job_dir, manifest, Path(args.export_vault).expanduser().resolve())
        if manifest.get("vault_attachment_dir") != export_result["attachment_dir"]:
            manifest["vault_attachment_dir"] = export_result["attachment_dir"]
            save_manifest(manifest_path, manifest)
    result = {
        "job_id": job_id,
        "cache_hit": cache_hit,
        "status": manifest["status"],
        "asr_model": manifest["asr_model"],
        "duration_seconds": manifest["duration_seconds"],
        "timestamp_quality": manifest.get("timestamp_quality"),
        "job_dir": str(job_dir),
        "manifest": str(manifest_path),
        "writing_brief": str(brief_path),
        "export": export_result,
    }
    if manifest["outputs"].get("corrected_text_preserved"):
        result["corrected_text_preserved"] = True
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Video URL or local video/audio path")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--resonance", help="The point that most resonated with the user")
    parser.add_argument("--adopt-dir", help="Reuse an existing completed work directory")
    parser.add_argument("--cache-root")
    parser.add_argument("--qwen-model", choices=("auto", "short", "filetrans"), default="auto")
    parser.add_argument("--export-vault", help="Explicitly copy transcript artifacts into this Obsidian vault")
    parser.add_argument(
        "--cleanup-video",
        action="store_true",
        help="Delete only workflow-owned video files after the note has been reviewed",
    )
    parser.add_argument(
        "--confirm-note-reviewed",
        action="store_true",
        help="Required confirmation token for --cleanup-video",
    )
    parser.add_argument("--force", action="store_true", help="Reprocess even when a complete cache exists")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = process(args)
    except (
        OSError,
        ValueError,
        http.client.HTTPException,
        WorkflowError,
        QwenAsrError,
        TencentFlashAsrError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
