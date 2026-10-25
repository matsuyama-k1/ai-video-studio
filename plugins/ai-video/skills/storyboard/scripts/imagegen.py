"""Storyboard frame images. Used by `sb.py frame`.

providers:
  codex     Codex CLI's built-in image generation (GPT Image), billed to the ChatGPT plan, no API key.
            Needs a working `codex` login (codex-cli 0.164, verified 2026-10-25: ~50 s per image).
            Codex is asked to save the image to a path and we check that the file appears.
            stdin must be closed, or `codex exec` waits for more input forever.
  seedream  BytePlus ModelArk Seedream (ARK_API_KEY). dola-seedream-5-0-flash-260915, about $0.018/image.
  gemini    Gemini API image model (GEMINI_API_KEY). gemini-nano-banana-2.1 at 1K, about $0.034/image.
  openai    OpenAI Images API, GPT Image 2 (OPENAI_API_KEY; model via OPENAI_IMAGE_MODEL). The only provider
            with a real mask edit. ~1536x864 medium is about $0.041/image (+ input image tokens for edits).

edit(): change an existing picture. With a mask (PNG, same size, transparent = area to change) OpenAI
edits only that region; the other providers get the mask as a hint and redraw the whole image.
Every result is centre-cropped to the storyboard aspect ratio.
"""
import base64
import json
import math
import mimetypes
import os
import shutil
import subprocess
import urllib.error
import sys
import tempfile
import urllib.request
from pathlib import Path

VP_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "video-prompt" / "scripts"
sys.path.insert(0, str(VP_SCRIPTS))
from seedance import load_env  # noqa: E402

OPENAI_MODEL = "gpt-image-2"   # override with OPENAI_IMAGE_MODEL (e.g. gpt-image-2.5-sunburst: newer, best at precise edits)
SEEDREAM_MODEL = "dola-seedream-5-0-flash-260915"
GEMINI_MODEL = "gemini-nano-banana-2.1"


def size_for(aspect, pixels=1_200_000):
    w, h = (float(x) for x in aspect.split(":"))
    width = math.sqrt(pixels * w / h)
    height = width * h / w
    return f"{int(width // 16 * 16)}x{int(height // 16 * 16)}"


def data_url(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime.lower()};base64,{base64.b64encode(Path(path).read_bytes()).decode()}"


def post(url, headers, body, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:600]}")


def multipart(fields, files):
    """fields: [(name, value)], files: [(name, path)] -> (body bytes, content-type)."""
    boundary = "----sb" + os.urandom(12).hex()
    out = []
    for name, value in fields:
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, path in files:
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{Path(path).name}"\r\n'
                   f"Content-Type: {mime}\r\n\r\n".encode() + Path(path).read_bytes() + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def post_multipart(url, headers, fields, files, timeout=600):
    body, ctype = multipart(fields, files)
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": ctype, **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:600]}")


def openai_size(aspect):
    """gpt-image-2+ takes any WxH: multiples of 16, ratio <= 3:1, 655,360-8,294,400 px. ~1.33 MP keeps cost at the 1536x1024 tier."""
    return size_for(aspect, pixels=1_327_104)


def openai_fields(prompt, aspect, quality, size=None):
    model = os.environ.get("OPENAI_IMAGE_MODEL") or OPENAI_MODEL
    return [("model", model), ("prompt", prompt), ("n", "1"),
            ("size", size or openai_size(aspect)), ("quality", quality or "medium"), ("output_format", "png")]


def as_png(path, tmpdir):
    """The mask must match the image's format and size, so non-PNG inputs are converted first."""
    if Path(path).suffix.lower() == ".png":
        return path
    out = Path(tmpdir) / (Path(path).stem + ".png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), str(out)], check=True)
    return str(out)


def openai_save(res, dest):
    item = (res.get("data") or [{}])[0]
    if not item.get("b64_json"):
        raise RuntimeError(f"openai returned no image: {json.dumps(res)[:400]}")
    Path(dest).write_bytes(base64.b64decode(item["b64_json"]))


def fit_aspect(path, aspect):
    """Centre-crop to the storyboard aspect ratio (no-op when already within 1%)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(","))
    except ValueError:
        return
    aw, ah = (float(x) for x in aspect.split(":"))
    target = aw / ah
    if abs(w / h - target) / target < 0.01:
        return
    cw, ch = (int(h * target) // 2 * 2, h) if w / h > target else (w, int(w / target) // 2 * 2)
    tmp = Path(path).with_name(Path(path).stem + ".crop" + Path(path).suffix)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vf", f"crop={cw}:{ch}", str(tmp)], check=True)
    tmp.replace(path)


# ---------- request builders ----------

def seedream_body(prompt, refs, aspect):
    body = {"model": SEEDREAM_MODEL, "prompt": prompt, "size": size_for(aspect),
            "response_format": "b64_json", "output_format": "png", "watermark": False}
    if refs:
        body["image"] = [data_url(r) for r in refs]
    return body


def gemini_body(prompt, refs, aspect):
    parts = [{"text": prompt}]
    for r in refs:
        mime = mimetypes.guess_type(r)[0] or "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(Path(r).read_bytes()).decode()}})
    return {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": aspect, "imageSize": "1K"}}}


def codex_instruction(prompt, refs, aspect, dest):
    ref_note = (" Use the attached reference image(s) to keep the character's and place's appearance consistent."
                if refs else "")
    return (f"Generate exactly one image with your built-in image generation tool and save it as a PNG file at "
            f"this absolute path: {dest}\n"
            f"Aspect ratio: {aspect}. It is a single storyboard keyframe for a video: no text, no captions, "
            f"no panel borders, no watermark.{ref_note}\n"
            f"Do not create or modify any other files.\n\nImage description:\n{prompt}")


def preview(provider, prompt, refs, aspect):
    if provider == "seedream":
        b = seedream_body(prompt, [], aspect)
        b["image"] = [f"<{r}>" for r in refs] or None
        return {"endpoint": "ark /images/generations", "body": {k: v for k, v in b.items() if v is not None}}
    if provider == "gemini":
        b = gemini_body(prompt, [], aspect)
        b["contents"][0]["parts"] += [{"inline_data": f"<{r}>"} for r in refs]
        return {"endpoint": f"{GEMINI_MODEL}:generateContent", "body": b}
    if provider == "openai":
        if refs:
            return {"endpoint": "POST /v1/images/edits (multipart)", "fields": dict(openai_fields(prompt, aspect, None)),
                    "image[]": refs}
        return {"endpoint": "POST /v1/images/generations", "body": dict(openai_fields(prompt, aspect, None))}
    if provider == "codex":
        return {"command": ["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check",
                            *sum((["-i", r] for r in refs), []), "<instruction>"],
                "instruction": codex_instruction(prompt, refs, aspect, "<frames/cNN-vK.png>")}
    raise SystemExit(f"unknown image provider: {provider}")


# ---------- generation ----------

def generate(provider, prompt, refs, aspect, dest, quality=None):
    dest = Path(dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    if provider == "seedream":
        key = os.environ.get("ARK_API_KEY") or sys.exit("ARK_API_KEY is not set")
        base = os.environ.get("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3").rstrip("/")
        res = post(f"{base}/images/generations", {"Authorization": f"Bearer {key}"}, seedream_body(prompt, refs, aspect))
        item = (res.get("data") or [{}])[0]
        if item.get("error") or not item.get("b64_json"):
            raise RuntimeError(f"seedream: {item.get('error') or res.get('error') or res}")
        dest.write_bytes(base64.b64decode(item["b64_json"]))
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not set")
        url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
        res = post(url, {"x-goog-api-key": key}, gemini_body(prompt, refs, aspect))
        parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        img = next((p.get("inlineData") or p.get("inline_data") for p in parts if p.get("inlineData") or p.get("inline_data")), None)
        if not img:
            raise RuntimeError(f"gemini returned no image: {json.dumps(res)[:400]}")
        dest.write_bytes(base64.b64decode(img["data"]))
    elif provider == "openai":
        key = openai_key()
        if refs:   # references -> edits endpoint, all images as inputs
            res = post_multipart(openai_url("edits"), {"Authorization": f"Bearer {key}"},
                                 openai_fields(prompt, aspect, quality), [("image[]", r) for r in refs])
        else:
            res = post(openai_url("generations"), {"Authorization": f"Bearer {key}"},
                       dict(openai_fields(prompt, aspect, quality)) | {"n": 1}, timeout=600)
        openai_save(res, dest)
    elif provider == "codex":
        if not shutil.which("codex"):
            raise RuntimeError("codex CLI not found")
        args = ["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check", "-C", str(dest.parent)]
        for r in refs:
            args += ["-i", str(Path(r).resolve())]
        args.append(codex_instruction(prompt, refs, aspect, dest))
        r = subprocess.run(args, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
        if not dest.exists():
            raise RuntimeError("codex did not save the image.\n" + (r.stderr or r.stdout)[-800:])
    else:
        raise SystemExit(f"unknown image provider: {provider}")
    fit_aspect(dest, aspect)
    return dest


def openai_url(endpoint):
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/images/" + endpoint


def openai_key():
    load_env()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set (put it in .env.local)")
    return key


def edit(provider, base, prompt, mask, refs, aspect, dest, quality=None):
    """Edit `base`. mask: PNG path (same size as base, transparent = change) or None for a whole-image edit."""
    dest = Path(dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    keep = ("Keep everything outside the requested change exactly as it is: same composition, framing, "
            "characters, lighting and colours.")
    if provider == "openai":
        key = openai_key()
        with tempfile.TemporaryDirectory() as tmp:
            # the mask applies to the first image, so the picture being edited goes first
            files = [("image[]", as_png(base, tmp))] + [("image[]", r) for r in refs] + ([("mask", mask)] if mask else [])
            text = prompt + ("\n" + keep if not mask else "")
            res = post_multipart(openai_url("edits"), {"Authorization": f"Bearer {key}"},
                                 openai_fields(text, aspect, quality, size="auto"), files)
        openai_save(res, dest)
    else:
        hint = (" Only change the region shown as transparent in the mask image (the last attached image); "
                "leave every other pixel unchanged." if mask else "")
        text = (f"Edit the first image: {prompt}\n{keep}{hint}" +
                (" The other images are references for appearance." if refs else ""))
        inputs = [base] + list(refs) + ([mask] if mask else [])
        if provider == "seedream":
            key = os.environ.get("ARK_API_KEY") or sys.exit("ARK_API_KEY is not set")
            base_url = os.environ.get("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3").rstrip("/")
            res = post(f"{base_url}/images/generations", {"Authorization": f"Bearer {key}"}, seedream_body(text, inputs, aspect))
            item = (res.get("data") or [{}])[0]
            if not item.get("b64_json"):
                raise RuntimeError(f"seedream: {item.get('error') or res}")
            dest.write_bytes(base64.b64decode(item["b64_json"]))
        elif provider == "gemini":
            key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not set")
            url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
            res = post(url, {"x-goog-api-key": key}, gemini_body(text, inputs, aspect))
            parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            img = next((p.get("inlineData") or p.get("inline_data") for p in parts if p.get("inlineData") or p.get("inline_data")), None)
            if not img:
                raise RuntimeError(f"gemini returned no image: {json.dumps(res)[:400]}")
            dest.write_bytes(base64.b64decode(img["data"]))
        elif provider == "codex":
            args = ["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check", "-C", str(dest.parent)]
            for f in inputs:
                args += ["-i", str(Path(f).resolve())]
            args.append(f"Use your built-in image generation tool to edit the first attached image and save the result "
                        f"as a PNG at this absolute path: {dest}\nDo not create or modify any other files.\n\n{text}")
            r = subprocess.run(args, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
            if not dest.exists():
                raise RuntimeError("codex did not save the image.\n" + (r.stderr or r.stdout)[-800:])
        else:
            raise SystemExit(f"unknown image provider: {provider}")
    fit_aspect(dest, aspect)
    return dest
