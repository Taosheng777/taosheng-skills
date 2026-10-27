#!/usr/bin/env python3
"""Transcribe audio with Qwen ASR without exposing credentials."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Sequence


SHORT_MODEL = "qwen3-asr-flash"
LONG_MODEL = "qwen3-asr-flash-filetrans"
SHORT_LIMIT_SECONDS = 300.0
DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/api/v1"
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


class QwenAsrError(RuntimeError):
    pass


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def normalize_api_base(value: str | None) -> str:
    base = (value or DEFAULT_API_BASE).strip().rstrip("/")
    if not base.startswith(("https://", "http://")):
        raise ValueError("DASHSCOPE_API_BASE must be an HTTP(S) URL")
    return base


def compatible_base(api_base: str, override: str | None = None) -> str:
    if override:
        return override.strip().rstrip("/")
    if api_base.endswith("/api/v1"):
        return f"{api_base[:-7]}/compatible-mode/v1"
    return f"{api_base}/compatible-mode/v1"


def select_model(duration_seconds: float, forced: str = "auto") -> str:
    if forced == "auto":
        return SHORT_MODEL if duration_seconds <= SHORT_LIMIT_SECONDS else LONG_MODEL
    if forced in {"short", SHORT_MODEL}:
        if duration_seconds > SHORT_LIMIT_SECONDS:
            raise ValueError("qwen3-asr-flash only supports audio up to 5 minutes")
        return SHORT_MODEL
    if forced in {"filetrans", "long", LONG_MODEL}:
        return LONG_MODEL
    raise ValueError(f"Unsupported Qwen model selection: {forced}")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise QwenAsrError(f"DashScope HTTP {exc.code}: {raw[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise QwenAsrError(f"DashScope request failed: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QwenAsrError("DashScope returned invalid JSON") from exc


def upload_multipart(upload_host: str, fields: dict[str, str], file_path: Path) -> None:
    parsed = urllib.parse.urlparse(upload_host)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise QwenAsrError("Invalid temporary upload host")

    boundary = f"----codex-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    field_parts: list[bytes] = []
    for name, value in fields.items():
        field_parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
    content_length = sum(map(len, field_parts)) + len(file_header) + file_path.stat().st_size + len(closing)

    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.netloc, timeout=180)
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"
    try:
        connection.putrequest("POST", request_path)
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Content-Length", str(content_length))
        connection.endheaders()
        for part in field_parts:
            connection.send(part)
        connection.send(file_header)
        with file_path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                connection.send(chunk)
        connection.send(closing)
        response = connection.getresponse()
        response_body = response.read()
        if response.status < 200 or response.status >= 300:
            message = response_body.decode("utf-8", errors="replace")[:1000]
            raise QwenAsrError(f"Temporary OSS upload failed: HTTP {response.status}: {message}")
    finally:
        connection.close()


def upload_temporary_audio(
    audio_path: Path,
    *,
    api_key: str,
    api_base: str,
    model: str = LONG_MODEL,
) -> str:
    policy_url = f"{api_base}/uploads?action=getPolicy&model={urllib.parse.quote(model)}"
    policy_response = request_json(
        policy_url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    data = policy_response.get("data")
    if not isinstance(data, dict):
        raise QwenAsrError("Temporary upload policy is missing data")
    required = {
        "upload_host",
        "upload_dir",
        "oss_access_key_id",
        "policy",
        "signature",
        "x_oss_object_acl",
        "x_oss_forbid_overwrite",
    }
    missing = sorted(required - data.keys())
    if missing:
        raise QwenAsrError(f"Temporary upload policy is missing fields: {', '.join(missing)}")

    object_name = f"{data['upload_dir'].rstrip('/')}/{audio_path.name}"
    fields = {
        "OSSAccessKeyId": str(data["oss_access_key_id"]),
        "policy": str(data["policy"]),
        "Signature": str(data["signature"]),
        "key": object_name,
        "x-oss-object-acl": str(data["x_oss_object_acl"]),
        "x-oss-forbid-overwrite": str(data["x_oss_forbid_overwrite"]),
        "success_action_status": "200",
    }
    upload_multipart(str(data["upload_host"]), fields, audio_path)
    return f"oss://{object_name}"


def extract_short_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "".join(parts).strip()
    output = response.get("output")
    if isinstance(output, dict):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, list):
                return "".join(
                    item.get("text", "") for item in content if isinstance(item, dict)
                ).strip()
            if isinstance(content, str):
                return content.strip()
        text = output.get("text")
        if isinstance(text, str):
            return text.strip()
    raise QwenAsrError("Unable to locate transcript text in qwen3-asr-flash response")


def transcribe_short(
    audio_path: Path,
    *,
    api_key: str,
    api_base: str,
    compatible_api_base: str | None,
    language: str | None,
    enable_itn: bool,
    context: str | None,
) -> tuple[dict[str, Any], str]:
    if audio_path.stat().st_size > 7_500_000:
        raise QwenAsrError("Audio is too large for Base64 short-model input; use filetrans")
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/mpeg"
    data_uri = f"data:{mime_type};base64,{base64.b64encode(audio_path.read_bytes()).decode('ascii')}"
    messages: list[dict[str, Any]] = []
    if context:
        messages.append({"role": "system", "content": context[:2000]})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"data": data_uri},
                }
            ],
        }
    )
    asr_options: dict[str, Any] = {"enable_itn": enable_itn}
    if language:
        asr_options["language"] = language
    response = request_json(
        f"{compatible_base(api_base, compatible_api_base)}/chat/completions",
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": SHORT_MODEL,
            "messages": messages,
            "stream": False,
            "asr_options": asr_options,
        },
        timeout=360,
    )
    return response, extract_short_text(response)


def transcription_url_from_query(response: dict[str, Any]) -> str:
    output = response.get("output")
    if not isinstance(output, dict):
        raise QwenAsrError("Task query response is missing output")
    result = output.get("result")
    if isinstance(result, dict) and result.get("transcription_url"):
        return str(result["transcription_url"])
    results = output.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and item.get("subtask_status") == "SUCCEEDED":
                return str(item.get("transcription_url", ""))
    raise QwenAsrError("Completed task does not include a transcription URL")


def transcribe_filetrans(
    audio_path: Path,
    *,
    api_key: str,
    api_base: str,
    language: str | None,
    enable_itn: bool,
    enable_words: bool,
    context: str | None,
    poll_interval: float,
    timeout_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    file_url = upload_temporary_audio(audio_path, api_key=api_key, api_base=api_base)
    parameters: dict[str, Any] = {
        "channel_id": [0],
        "enable_itn": enable_itn,
        "enable_words": enable_words,
    }
    if language:
        parameters["language"] = language
    if context:
        parameters["corpus"] = {"text": context[:2000]}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-DashScope-Async": "enable",
        "X-DashScope-OssResourceResolve": "enable",
    }
    submit = request_json(
        f"{api_base}/services/audio/asr/transcription",
        method="POST",
        headers=headers,
        payload={
            "model": LONG_MODEL,
            "input": {"file_url": file_url},
            "parameters": parameters,
        },
    )
    output = submit.get("output")
    task_id = output.get("task_id") if isinstance(output, dict) else None
    if not task_id:
        raise QwenAsrError("Qwen filetrans task submission did not return task_id")

    deadline = time.monotonic() + timeout_seconds
    query: dict[str, Any] = {}
    while time.monotonic() < deadline:
        query = request_json(
            f"{api_base}/tasks/{urllib.parse.quote(str(task_id))}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        query_output = query.get("output")
        status = query_output.get("task_status") if isinstance(query_output, dict) else None
        if status in TERMINAL_STATES:
            if status != "SUCCEEDED":
                raise QwenAsrError(f"Qwen filetrans task ended with status {status}")
            break
        time.sleep(poll_interval)
    else:
        raise QwenAsrError("Timed out while waiting for Qwen filetrans task")

    result_url = transcription_url_from_query(query)
    result = request_json(result_url, timeout=180)
    return result, {"task_id": str(task_id), "task_status": "SUCCEEDED"}


def ms_to_srt(milliseconds: int | float) -> str:
    total = max(0, round(float(milliseconds)))
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def extract_timed_content(result: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    transcripts = result.get("transcripts")
    if not isinstance(transcripts, list) or not transcripts:
        raise QwenAsrError("Qwen filetrans result has no transcripts")
    texts: list[str] = []
    sentences: list[dict[str, Any]] = []
    for transcript in transcripts:
        if not isinstance(transcript, dict):
            continue
        text = transcript.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
        raw_sentences = transcript.get("sentences")
        if isinstance(raw_sentences, list):
            sentences.extend(item for item in raw_sentences if isinstance(item, dict))
    return "\n".join(texts).strip(), sentences


def write_outputs(
    output_dir: Path,
    *,
    model: str,
    raw_response: dict[str, Any],
    duration_seconds: float,
    text: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "qwen-result.json"
    raw_path = output_dir / "qwen-raw.txt"
    corrected_path = output_dir / "qwen-corrected.txt"
    srt_path = output_dir / "qwen-raw.srt"
    sentences_path = output_dir / "qwen-sentences.tsv"

    result_path.write_text(
        json.dumps(raw_response, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    timestamp_quality = "sentence_and_word"
    if model == LONG_MODEL:
        final_text, sentences = extract_timed_content(raw_response)
    else:
        final_text = (text or "").strip()
        sentences = [
            {
                "sentence_id": 0,
                "begin_time": 0,
                "end_time": round(duration_seconds * 1000),
                "text": final_text,
            }
        ]
        timestamp_quality = "whole_audio_only"
    if not final_text:
        raise QwenAsrError("Qwen transcript is empty")

    previous_raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else None
    raw_path.write_text(final_text + "\n", encoding="utf-8")
    # An unedited copy of the previous transcript follows the new one; manual edits stay.
    corrected_preserved = corrected_path.exists() and corrected_path.read_text(encoding="utf-8") not in (
        previous_raw,
        final_text + "\n",
    )
    if not corrected_preserved:
        corrected_path.write_text(final_text + "\n", encoding="utf-8")

    srt_chunks: list[str] = []
    tsv_lines = ["sentence_id\tbegin_ms\tend_ms\ttext"]
    for index, sentence in enumerate(sentences, 1):
        sentence_text = str(sentence.get("text", "")).strip().replace("\t", " ").replace("\n", " ")
        if not sentence_text:
            continue
        begin = int(sentence.get("begin_time", 0))
        end = int(sentence.get("end_time", begin))
        srt_chunks.append(
            f"{len(srt_chunks) + 1}\n{ms_to_srt(begin)} --> {ms_to_srt(end)}\n{sentence_text}\n\n"
        )
        tsv_lines.append(f"{sentence.get('sentence_id', index - 1)}\t{begin}\t{end}\t{sentence_text}")
    srt_path.write_text("".join(srt_chunks), encoding="utf-8")
    sentences_path.write_text("\n".join(tsv_lines) + "\n", encoding="utf-8")

    outputs = {
        "model": model,
        "timestamp_quality": timestamp_quality,
        "text_sha256": hashlib.sha256(final_text.encode("utf-8")).hexdigest(),
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
    duration_seconds: float,
    model_selection: str,
    language: str | None,
    enable_itn: bool,
    enable_words: bool,
    context: str | None,
    api_key: str,
    api_base: str,
    compatible_api_base: str | None,
    poll_interval: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    model = select_model(duration_seconds, model_selection)
    if model == SHORT_MODEL:
        response, text = transcribe_short(
            audio_path,
            api_key=api_key,
            api_base=api_base,
            compatible_api_base=compatible_api_base,
            language=language,
            enable_itn=enable_itn,
            context=context,
        )
        task_info = {"task_status": "SUCCEEDED"}
    else:
        response, task_info = transcribe_filetrans(
            audio_path,
            api_key=api_key,
            api_base=api_base,
            language=language,
            enable_itn=enable_itn,
            enable_words=enable_words,
            context=context,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
        )
        text = None
    outputs = write_outputs(
        output_dir,
        model=model,
        raw_response=response,
        duration_seconds=duration_seconds,
        text=text,
    )
    outputs.update(task_info)
    return outputs


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--duration", required=True, type=float)
    parser.add_argument("--model", default="auto", choices=("auto", "short", "filetrans"))
    parser.add_argument("--language", default=os.getenv("QWEN_LANGUAGE", "zh"))
    parser.add_argument("--enable-itn", default=os.getenv("QWEN_ENABLE_ITN", "false"))
    parser.add_argument("--enable-words", default=os.getenv("QWEN_ENABLE_WORDS", "true"))
    parser.add_argument("--context")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=1800.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: DASHSCOPE_API_KEY is not configured", file=sys.stderr)
        return 2
    try:
        result = transcribe(
            args.audio_path.expanduser().resolve(),
            args.output_dir.expanduser().resolve(),
            duration_seconds=args.duration,
            model_selection=args.model,
            language=args.language or None,
            enable_itn=parse_bool(args.enable_itn),
            enable_words=parse_bool(args.enable_words, True),
            context=args.context,
            api_key=api_key,
            api_base=normalize_api_base(os.getenv("DASHSCOPE_API_BASE")),
            compatible_api_base=os.getenv("DASHSCOPE_COMPATIBLE_BASE"),
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout,
        )
    except (OSError, ValueError, QwenAsrError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
