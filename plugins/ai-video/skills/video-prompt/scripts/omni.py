#!/usr/bin/env python3
"""Gemini Omni Flash (Gemini API, Interactions API): generate one video and download it.

Standard library only. Reads GEMINI_API_KEY from the environment or .env.local.
Same interface as seedance.py: build_body(cfg, prompt), redact(body), run(cfg, prompt, out_dir, stem).

Notes (ai.google.dev/gemini-api/docs/omni, 2026-10):
- Audio is always generated; there is no on/off switch. audio: false appends a "no sound" instruction.
- Duration has no documented parameter; steer it in the prompt (e.g. "[0-3s] ... [3-6s] ...").
- Image roles come from order + tags: first_frame, last_frame, then reference images.
"""
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from seedance import load_env

BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-omni-1.1-flash"


def request(method, url, key, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}")


def image_block(src):
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src) as r:
            raw, mime = r.read(), r.headers.get_content_type()
    else:
        raw, mime = Path(src).read_bytes(), mimetypes.guess_type(src)[0] or "image/png"
    return {"type": "image", "data": base64.b64encode(raw).decode(), "mime_type": mime}


def build_body(cfg, prompt):
    images, sources, refs = [], [], []
    for tag in ("first_frame", "last_frame"):
        if cfg.get(tag):
            images.append(cfg[tag])
            sources.append(f"<{tag.upper()}>@Image{len(images)}")
    for src in cfg.get("ref_images") or []:
        images.append(src)
        refs.append(f"<IMAGE_REF_{len(refs)}>@Image{len(images)}")

    text = prompt
    header = (f"[# Sources {' '.join(sources)}] " if sources else "") + \
             (f"[# References {' '.join(refs)}] " if refs else "")
    if header:
        text = header.strip() + "\n" + text
    if cfg.get("audio") is False:
        text += "\nNo dialogue, no music, no sound effects."

    body = {
        "model": cfg.get("model") or DEFAULT_MODEL,
        "input": [{"type": "text", "text": text}] + [image_block(s) for s in images],
        "response_format": {
            "type": "video",
            "aspect_ratio": cfg.get("ratio") or "16:9",
            "resolution": cfg.get("resolution") or "720p",
            "delivery": "uri",
        },
    }
    if cfg.get("seed") is not None:
        body["generation_config"] = {"seed": cfg["seed"]}
    return body


def redact(body):
    shown = json.loads(json.dumps(body))
    for block in shown["input"]:
        if block.get("data"):
            block["data"] = block["data"][:24] + "..."
    return shown


def find_video(interaction):
    for step in interaction.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for item in step.get("content") or []:
            if item.get("type") == "video":
                return item
    return None


def download_file(uri, key, dest, interval=5):
    """Wait for a Files API file to become ACTIVE, then download it."""
    file_url = uri.split(":download")[0]
    for _ in range(120):
        state = request("GET", file_url, key).get("state")
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError(f"file processing failed: {file_url}")
        time.sleep(interval)
    sep = "&" if "?" in uri else "?"
    req = urllib.request.Request(uri if "alt=media" in uri else f"{uri}{sep}alt=media",
                                 headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=300) as r:
        Path(dest).write_bytes(r.read())


def run(cfg, prompt, out_dir, stem, interval=10, log=print):
    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env.local)")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log("generating (synchronous, may take a few minutes)...")
    inter = request("POST", f"{BASE}/interactions", key, build_body(cfg, prompt))
    status = inter.get("status")
    video = find_video(inter)

    saved = json.loads(json.dumps(inter))
    v = find_video(saved)
    if v and v.get("data"):
        v["data"] = f"<{len(v['data'])} base64 chars>"
    (out_dir / f"{stem}.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2))

    result = {"provider": "omni", "task_id": inter.get("id"), "status": status,
              "tokens": (inter.get("usage") or {}).get("total_output_tokens") or inter.get("usage"),
              "error": inter.get("error")}
    if status == "completed" and video:
        dest = out_dir / f"{stem}.mp4"
        if video.get("data"):
            dest.write_bytes(base64.b64decode(video["data"]))
        else:
            download_file(video["uri"], key, dest)
        result["video"] = str(dest)
        result["status"] = "succeeded"
    elif status == "completed":
        result["status"] = "failed"
        result["error"] = "completed without a video in steps[]"
    return result
