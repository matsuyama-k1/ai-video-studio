"""Cut pictures with history: generate, edit (whole image or a masked region), grab from video, switch version.
Used by sb.py (CLI) and animatic.py (browser editor).

Every new picture becomes storyboard/frames/<cut>-v<N>.<ext> and is appended to cut["frame_history"]
with how it was made (mode, provider, prompt, mask, base image, refs), so revisions keep their reasons.
"""
import base64
import datetime as dt
import subprocess
from pathlib import Path

import imagegen


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def next_path(project_dir, cut_id, ext="png"):
    frames = project_dir / "storyboard" / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(p.stem.rsplit("-v", 1)[1]) for p in frames.glob(f"{cut_id}-v*.*")
                 if p.stem.rsplit("-v", 1)[1].isdigit()] or [0])
    return frames / f"{cut_id}-v{n}.{ext}"


def rel(project_dir, path):
    return str(Path(path).resolve().relative_to(Path(project_dir).resolve()))


def record(project_dir, cut, path, **entry):
    """Make `path` the cut's current picture and log how it was made."""
    cut["frame"] = rel(project_dir, path)
    hist = cut.setdefault("frame_history", [])
    if not hist and entry.get("base"):
        hist.append({"file": entry["base"], "at": "", "mode": "original"})
    hist.append({"file": cut["frame"], "at": now(), **{k: v for k, v in entry.items() if v not in (None, "", [])}})
    return cut["frame"]


def ref_paths(project_dir, refs):
    return [str(project_dir / r) for r in refs or []]


def generate(project_dir, data, cut, provider, prompt=None, refs=None, quality=None):
    prompt = prompt or cut.get("frame_prompt")
    if not prompt:
        raise RuntimeError(f"{cut['id']}: frame_prompt is empty")
    cut["frame_prompt"] = prompt
    refs = cut.get("refs") if refs is None else refs
    dest = next_path(project_dir, cut["id"])
    imagegen.generate(provider, prompt, ref_paths(project_dir, refs), data["project"].get("aspect") or "16:9",
                      dest, quality=quality)
    return record(project_dir, cut, dest, mode="generate", provider=provider, prompt=prompt, refs=refs, quality=quality)


def edit(project_dir, data, cut, provider, prompt, mask_png=None, refs=None, quality=None, reason=None):
    """Edit the current picture. mask_png: PNG bytes, same size as the picture, transparent = area to change."""
    if not cut.get("frame"):
        raise RuntimeError(f"{cut['id']}: no picture to edit yet")
    base = project_dir / cut["frame"]
    dest = next_path(project_dir, cut["id"])
    mask_rel = None
    if mask_png:
        mask = dest.with_name(dest.stem + "-mask.png")
        mask.write_bytes(mask_png)
        mask_rel = rel(project_dir, mask)
    imagegen.edit(provider, str(base), prompt, str(project_dir / mask_rel) if mask_rel else None,
                  ref_paths(project_dir, refs), data["project"].get("aspect") or "16:9", dest, quality=quality)
    return record(project_dir, cut, dest, mode="edit-region" if mask_rel else "edit", provider=provider,
                  prompt=prompt, mask=mask_rel, base=cut["frame"], refs=refs, quality=quality, reason=reason)


def grab(project_dir, cut, video, sec):
    dest = next_path(project_dir, cut["id"], "jpg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(sec), "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(dest)], check=True)
    return record(project_dir, cut, dest, mode="grab", source=f"{video} @ {sec}s")


def use(project_dir, cut, file):
    """Switch back to an earlier version (no new file)."""
    if not (project_dir / file).exists():
        raise RuntimeError(f"not found: {file}")
    cut["frame"] = file
    cut.setdefault("frame_history", []).append({"file": file, "at": now(), "mode": "use"})
    return file


def decode_data_url(url):
    return base64.b64decode(url.split(",", 1)[1]) if url else None
