#!/usr/bin/env python3
"""Transcribe MP3 audio with Tencent Cloud recording-file flash ASR."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


HOST = "asr.cloud.tencent.com"
DEFAULT_ENGINE = "16k_zh"
MAX_AUDIO_BYTES = 100 * 1024 * 1024


class TencentFlashAsrError(RuntimeError):
    pass


def clock_timestamp(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds)) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def srt_timestamp(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_request(
    *,
    audio: bytes,
    appid: str,
    secret_id: str,
    secret_key: str,
    timestamp: int | None = None,
) -> urllib.request.Request:
    if not appid or not secret_id or not secret_key:
        raise ValueError("Tencent ASR credentials are incomplete")
    timestamp = int(time.time()) if timestamp is None else int(timestamp)
    params = {
        "secretid": secret_id,
        "engine_type": DEFAULT_ENGINE,
        "voice_format": "mp3",
        "timestamp": str(timestamp),
        "word_info": "2",
        "speaker_diarization": "1",
    }
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    path = f"/asr/flash/v1/{appid}"
    canonical = f"POST{HOST}{path}?{query}"
    signature = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    return urllib.request.Request(
        f"https://{HOST}{path}?{query}",
        data=audio,
        method="POST",
        headers={
            "Host": HOST,
            "Authorization": signature,
            "Content-Type": "application/octet-stream",
        },
    )


def extract_sentences(result: dict[str, Any]) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    for channel in result.get("flash_result") or []:
        for sentence in channel.get("sentence_list") or []:
            text = str(sentence.get("text") or "").strip()
            if not text:
                continue
            start_ms = int(sentence.get("start_time") or 0)
            end_ms = max(start_ms + 1, int(sentence.get("end_time") or start_ms + 1))
            speaker = sentence.get("speaker_id")
            try:
                speaker_number = int(speaker) + 1 if speaker is not None else None
            except (TypeError, ValueError):
                speaker_number = None
            sentences.append(
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "speaker": speaker_number,
                    "text": text,
                }
            )
    sentences.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    return sentences


def write_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    sentences = extract_sentences(result)
    if not sentences:
        raise TencentFlashAsrError("Tencent ASR response contains no recognized sentences")
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript_lines = []
    srt_blocks = []
    timeline_lines = ["start_ms\tend_ms\tspeaker\ttext"]
    for index, sentence in enumerate(sentences, 1):
        speaker_label = f"[说话人{sentence['speaker']}]" if sentence["speaker"] else ""
        transcript_lines.append(
            f"[{clock_timestamp(sentence['start_ms'])}]{speaker_label} {sentence['text']}"
        )
        srt_blocks.append(
            f"{index}\n{srt_timestamp(sentence['start_ms'])} --> "
            f"{srt_timestamp(sentence['end_ms'])}\n{sentence['text']}"
        )
        clean_text = sentence["text"].replace("\t", " ").replace("\r", " ").replace("\n", " ")
        timeline_lines.append(
            f"{sentence['start_ms']}\t{sentence['end_ms']}\t"
            f"{sentence['speaker'] or ''}\t{clean_text}"
        )

    raw_path = output_dir / "tencent-raw.txt"
    corrected_path = output_dir / "tencent-corrected.txt"
    srt_path = output_dir / "tencent-raw.srt"
    sentences_path = output_dir / "tencent-sentences.tsv"
    result_path = output_dir / "tencent-result.json"
    transcript = "\n".join(transcript_lines) + "\n"
    previous_raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else None
    raw_path.write_text(transcript, encoding="utf-8")
    # An unedited copy of the previous transcript follows the new one; manual edits stay.
    corrected_preserved = corrected_path.exists() and corrected_path.read_text(encoding="utf-8") not in (
        previous_raw,
        transcript,
    )
    if not corrected_preserved:
        corrected_path.write_text(transcript, encoding="utf-8")
    srt_path.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    sentences_path.write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    outputs = {
        "model": f"tencent-flash:{DEFAULT_ENGINE}",
        "timestamp_quality": "sentence_and_word",
        "raw_text": str(raw_path),
        "corrected_text": str(corrected_path),
        "srt": str(srt_path),
        "sentences_tsv": str(sentences_path),
        "result_json": str(result_path),
    }
    if corrected_preserved:
        outputs["corrected_text_preserved"] = True
    return outputs


def transcribe(
    audio_path: Path,
    output_dir: Path,
    *,
    appid: str,
    secret_id: str,
    secret_key: str,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    audio_path = Path(audio_path)
    if audio_path.suffix.lower() != ".mp3":
        raise ValueError("Tencent flash ASR integration requires MP3 input")
    audio = audio_path.read_bytes()
    if not audio:
        raise ValueError("Audio file is empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("Tencent flash ASR input exceeds the 100 MB limit")
    request = build_request(
        audio=audio,
        appid=appid,
        secret_id=secret_id,
        secret_key=secret_key,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TencentFlashAsrError(f"Tencent ASR HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise TencentFlashAsrError(f"Tencent ASR request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise TencentFlashAsrError("Tencent ASR returned invalid JSON") from exc

    if result.get("code") != 0:
        code = result.get("code", "unknown")
        message = result.get("message", "unknown error")
        raise TencentFlashAsrError(f"Tencent ASR error {code}: {message}")
    return write_outputs(result, Path(output_dir))
