#!/usr/bin/env python3
"""BytePlus ModelArk Seedance: create a video task, poll until done, download the mp4.

Standard library only. Reads ARK_API_KEY (and optional ARK_BASE_URL) from the
environment or from .env.local in the current directory.

Used two ways:
- as a library from vp.py: `run(cfg, prompt, out_dir, stem)`
- as a CLI for one-off clips: `python3 seedance.py --prompt "..." --out outputs/x`
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import toolpath  # noqa: E402,F401  (ffmpeg installed by the setup skill)

DEFAULT_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_MODEL = "dreamina-seedance-2-0-mini-260615"
FINAL = {"succeeded", "failed", "expired", "cancelled"}


def load_env(path=".env.local"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def request(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}")


def image_ref(src):
    """URL, asset:// ID, or local path (converted to a base64 data URL)."""
    if src.startswith(("http://", "https://", "asset://", "data:")):
        return src
    mime = mimetypes.guess_type(src)[0] or "image/png"
    return f"data:{mime.lower()};base64,{base64.b64encode(Path(src).read_bytes()).decode()}"


def build_body(cfg, prompt):
    """cfg keys: model, resolution, ratio, duration, seed, audio, watermark,
    first_frame, last_frame, ref_images (list of paths/URLs)."""
    content = [{"type": "text", "text": prompt}]
    images = [("first_frame", cfg.get("first_frame")), ("last_frame", cfg.get("last_frame"))]
    images += [("reference_image", s) for s in cfg.get("ref_images") or []]
    for role, src in images:
        if src:
            content.append({"type": "image_url", "image_url": {"url": image_ref(src)}, "role": role})
    body = {
        "model": cfg.get("model") or DEFAULT_MODEL,
        "content": content,
        "watermark": bool(cfg.get("watermark", False)),
        "return_last_frame": True,
    }
    for k in ("resolution", "ratio", "duration", "seed"):
        if cfg.get(k) not in (None, ""):
            body[k] = cfg[k]
    if cfg.get("audio") is False:
        body["generate_audio"] = False
    return body


def redact(body):
    shown = json.loads(json.dumps(body))
    for c in shown["content"]:
        url = c.get("image_url", {}).get("url", "")
        if url.startswith("data:"):
            c["image_url"]["url"] = url[:40] + "..."
    return shown


def run(cfg, prompt, out_dir, stem, interval=10, log=print):
    """Create a task, wait, download. Returns a result dict (never raises on task failure)."""
    load_env()
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise RuntimeError("ARK_API_KEY is not set (put it in .env.local)")
    base = os.environ.get("ARK_BASE_URL", DEFAULT_BASE).rstrip("/")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    body = build_body(cfg, prompt)
    task_id = request("POST", f"{base}/contents/generations/tasks", key, body)["id"]
    log(f"task: {task_id}")
    while True:
        task = request("GET", f"{base}/contents/generations/tasks/{task_id}", key)
        status = task.get("status")
        log(f"status: {status}")
        if status in FINAL:
            break
        time.sleep(interval)

    (out_dir / f"{stem}.json").write_text(json.dumps(task, ensure_ascii=False, indent=2))
    result = {"provider": "seedance", "task_id": task_id, "status": status,
              "tokens": (task.get("usage") or {}).get("completion_tokens"),
              "error": task.get("error")}
    if status == "succeeded":
        video = out_dir / f"{stem}.mp4"
        urllib.request.urlretrieve(task["content"]["video_url"], video)
        result["video"] = str(video)
        if task["content"].get("last_frame_url"):
            frame = out_dir / f"{stem}-last.jpg"
            urllib.request.urlretrieve(task["content"]["last_frame_url"], frame)
            result["last_frame"] = str(frame)
    return result


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--resolution")
    ap.add_argument("--ratio")
    ap.add_argument("--duration", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--first-frame")
    ap.add_argument("--last-frame")
    ap.add_argument("--ref-image", action="append")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--watermark", action="store_true")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="print the request body and exit")
    a = ap.parse_args()

    prompt = Path(a.prompt_file).read_text().strip() if a.prompt_file else a.prompt
    cfg = {"model": a.model, "resolution": a.resolution, "ratio": a.ratio, "duration": a.duration,
           "seed": a.seed, "audio": not a.no_audio, "watermark": a.watermark,
           "first_frame": a.first_frame, "last_frame": a.last_frame, "ref_images": a.ref_image}
    if a.dry_run:
        print(json.dumps(redact(build_body(cfg, prompt)), ensure_ascii=False, indent=2))
        return
    try:
        res = run(cfg, prompt, a.out, time.strftime("%Y%m%d-%H%M%S"), a.interval)
    except RuntimeError as e:
        sys.exit(str(e))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["status"] != "succeeded":
        sys.exit(1)


if __name__ == "__main__":
    main()
