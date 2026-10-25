#!/usr/bin/env python3
"""Kling AI official API (new style, kling.ai/document-api): create a video task, poll, download.

Standard library only. Reads KLING_API_KEY from the environment or .env.local.
Same interface as seedance.py: build_body(cfg, prompt), redact(body), run(cfg, prompt, out_dir, stem).

Endpoint is chosen from the inputs:
- ref_images            -> /omni-video/kling-3.0-omni  (write @image_1, @image_2 ... in the prompt)
- first_frame/last_frame -> /image-to-video/<model>
- text only             -> /text-to-video/<model>
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from seedance import load_env

BASE = "https://api-singapore.klingai.com"
DEFAULT_MODEL = "kling-3.0"
OMNI_MODEL = "kling-3.0-omni"
NO_AUDIO_FIELD = ("turbo", "4.0")  # these endpoints have no settings.audio


def request(method, path, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}")
    if res.get("code") != 0:
        raise RuntimeError(f"Kling error {res.get('code')}: {res.get('message')}")
    return res["data"]


def image_url(src):
    """URL as is; local file as raw base64 (Kling wants no data: prefix)."""
    if src.startswith(("http://", "https://")):
        return src
    return base64.b64encode(Path(src).read_bytes()).decode()


def build_body(cfg, prompt):
    """Returns {'path': endpoint, 'body': request body}."""
    model = cfg.get("model") or DEFAULT_MODEL
    refs = cfg.get("ref_images") or []
    settings = {}
    if cfg.get("resolution"):
        settings["resolution"] = cfg["resolution"]
    if cfg.get("duration"):
        settings["duration"] = int(cfg["duration"])

    if refs:
        model = OMNI_MODEL
        path = f"/omni-video/{model}"
        contents = [{"type": "prompt", "text": prompt}]
        for tag in ("first_frame", "last_frame"):
            if cfg.get(tag):
                contents.append({"type": tag, "url": image_url(cfg[tag])})
        for i, src in enumerate(refs, 1):
            contents.append({"type": "refer_image", "url": image_url(src), "id": f"image_{i}"})
        if not cfg.get("first_frame"):
            settings["aspect_ratio"] = cfg.get("ratio") or "16:9"
        body = {"contents": contents}
    elif cfg.get("first_frame"):
        path = f"/image-to-video/{model}"
        contents = [{"type": "prompt", "text": prompt},
                    {"type": "first_frame", "url": image_url(cfg["first_frame"])}]
        if cfg.get("last_frame"):
            contents.append({"type": "last_frame", "url": image_url(cfg["last_frame"])})
        body = {"contents": contents}
    else:
        path = f"/text-to-video/{model}"
        settings["aspect_ratio"] = cfg.get("ratio") or "16:9"
        body = {"prompt": prompt}

    if not any(t in model for t in NO_AUDIO_FIELD):
        settings["audio"] = "off" if cfg.get("audio") is False else "native"
    if model in ("kling-3.0", OMNI_MODEL):
        settings["multi_shot"] = bool(cfg.get("multi_shot"))
    body["settings"] = settings
    body["options"] = {"watermark_info": {"enabled": bool(cfg.get("watermark", False))}}
    return {"path": path, "body": body}


def redact(req):
    shown = json.loads(json.dumps(req))
    for c in shown["body"].get("contents", []):
        url = c.get("url", "")
        if url and not url.startswith("http"):
            c["url"] = url[:24] + "..."
    return shown


def run(cfg, prompt, out_dir, stem, interval=10, log=print):
    load_env()
    key = os.environ.get("KLING_API_KEY")
    if not key:
        raise RuntimeError("KLING_API_KEY is not set (put it in .env.local)")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    req = build_body(cfg, prompt)
    task_id = request("POST", req["path"], key, req["body"])["id"]
    log(f"task: {task_id} ({req['path']})")
    while True:
        task = request("GET", f"/tasks?task_ids={task_id}", key)[0]
        status = task.get("status")
        log(f"status: {status}")
        if status in ("succeeded", "failed"):
            break
        time.sleep(interval)

    (out_dir / f"{stem}.json").write_text(json.dumps(task, ensure_ascii=False, indent=2))
    result = {"provider": "kling", "task_id": task_id, "status": status,
              "tokens": task.get("billing"), "error": task.get("message") if status == "failed" else None}
    outputs = [o for o in task.get("outputs") or [] if o.get("type") == "video"]
    if status == "succeeded" and outputs:
        video = out_dir / f"{stem}.mp4"
        urllib.request.urlretrieve(outputs[0]["url"], video)
        result["video"] = str(video)
    return result
