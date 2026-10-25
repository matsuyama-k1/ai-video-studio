#!/usr/bin/env python3
"""Video project workspace: script / storyboard / refs -> per-scene versioned prompts -> renders.

  vp.py init <project>                       create projects/<project>/
  vp.py scene <project> <nn> <slug>          add scenes/sNN-<slug>/ with an empty v001
  vp.py revise <scene_dir> --reason "..."    copy the latest prompt to the next version
  vp.py diff <scene_dir> [vA] [vB]           show what changed between two versions
  vp.py render <scene_dir> [--version vNNN] [--dry-run]
  vp.py status <project>                     one line per scene

Standard library only. Run from the repository root.
"""
import argparse
import datetime as dt
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import toolpath  # noqa: E402,F401  (ffmpeg installed by the setup skill)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TEMPLATES = HERE.parent / "templates"
ROOT = Path("projects")

FIELDS = ["version", "parent", "created", "provider", "model", "resolution", "ratio",
          "duration", "audio", "seed", "first_frame", "last_frame", "ref_images"]


# ---------- prompt files ----------

def parse(path):
    """Prompt file = '---' key: value lines '---' + markdown body."""
    text = Path(path).read_text()
    m = re.match(r"^---\n(.*?)^---\n(.*)$", text, re.S | re.M)
    if not m:
        sys.exit(f"{path}: missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def dump(meta, body):
    head = "\n".join(f"{k}: {meta.get(k, '')}" for k in FIELDS)
    extra = "\n".join(f"{k}: {v}" for k, v in meta.items() if k not in FIELDS)
    return f"---\n{head}{chr(10) + extra if extra else ''}\n---\n{body}"


def section(body, title):
    m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def replace_section(body, title, text):
    return re.sub(rf"(^## {re.escape(title)}[ \t]*\n).*?(?=^## |\Z)",
                  lambda m: f"{m.group(1)}\n{text}\n\n", body, flags=re.S | re.M)


def versions(scene):
    return sorted((scene / "prompts").glob("v[0-9][0-9][0-9].md"))


def latest(scene):
    vs = versions(scene)
    if not vs:
        sys.exit(f"{scene}: no prompt versions yet")
    return vs[-1]


def project_of(scene):
    return scene.resolve().parent.parent


def project_defaults(project):
    meta, _ = parse(project / "project.md")
    return meta


def append_log(scene, row):
    log = scene / "log.md"
    with log.open("a") as f:
        f.write("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in row) + " |\n")


def today():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------- commands ----------

def cmd_init(a):
    p = ROOT / a.project
    if p.exists():
        sys.exit(f"{p} already exists")
    for d in ("refs", "scenes"):
        (p / d).mkdir(parents=True)
    for name in ("project.md", "script.md"):
        shutil.copy(TEMPLATES / name, p / name)
    shutil.copy(TEMPLATES / "refs-index.md", p / "refs" / "index.md")
    print(p)


def cmd_scene(a):
    p = ROOT / a.project
    scene = p / "scenes" / f"s{int(a.nn):02d}-{a.slug}"
    if scene.exists():
        sys.exit(f"{scene} already exists")
    (scene / "prompts").mkdir(parents=True)
    (scene / "renders").mkdir()
    shutil.copy(TEMPLATES / "scene.md", scene / "scene.md")
    shutil.copy(TEMPLATES / "log.md", scene / "log.md")
    defaults = project_defaults(p)
    meta = {k: defaults.get(k, "") for k in FIELDS}
    meta.update(version="v001", parent="", created=today())
    _, body = parse(TEMPLATES / "prompt.md")
    (scene / "prompts" / "v001.md").write_text(dump(meta, body))
    append_log(scene, ["v001", today(), "作成", "初版", "", ""])
    print(scene)


def cmd_revise(a):
    scene = Path(a.scene)
    src = latest(scene)
    meta, body = parse(src)
    n = int(src.stem[1:]) + 1
    meta.update(version=f"v{n:03d}", parent=src.stem, created=today())
    body = replace_section(body, "修正根拠", f"- {a.reason}")
    body = replace_section(body, "評価", "<!-- 生成結果を見た感想。次の改訂の根拠になる -->")
    dst = scene / "prompts" / f"v{n:03d}.md"
    dst.write_text(dump(meta, body))
    append_log(scene, [dst.stem, today(), f"{src.stem}から改訂", a.reason, "", ""])
    print(dst)


def cmd_diff(a):
    scene = Path(a.scene)
    vs = versions(scene)
    if not (a.a and a.b) and len(vs) < 2:
        sys.exit("need at least two versions")
    va = scene / "prompts" / f"{a.a}.md" if a.a else vs[-2]
    vb = scene / "prompts" / f"{a.b}.md" if a.b else vs[-1]
    out = difflib.unified_diff(va.read_text().splitlines(), vb.read_text().splitlines(),
                               va.stem, vb.stem, lineterm="")
    print("\n".join(out) or "(no differences)")


def resolve_ref(project, scene, value):
    """Paths are relative to the project root. 'prev:last' = last frame of the previous scene's latest render."""
    if not value:
        return None
    if value.startswith(("http://", "https://", "asset://")):
        return value
    if value == "prev:last":
        scenes = sorted(d for d in (project / "scenes").iterdir() if d.is_dir())
        i = scenes.index(scene.resolve())
        if i == 0:
            sys.exit("prev:last used on the first scene")
        frames = sorted((scenes[i - 1] / "renders").glob("*-last.jpg"), key=lambda f: f.stat().st_mtime)
        if not frames:
            sys.exit(f"{scenes[i - 1].name} has no rendered last frame yet")
        return str(frames[-1])
    path = project / value
    if not path.exists():
        sys.exit(f"reference not found: {path}")
    return str(path)


def build_cfg(meta, project, scene):
    def num(k):
        return int(meta[k]) if meta.get(k) not in (None, "") else None
    return {
        "model": meta.get("model"),
        "resolution": meta.get("resolution") or None,
        "ratio": meta.get("ratio") or None,
        "duration": num("duration"),
        "seed": num("seed"),
        "audio": meta.get("audio", "true").lower() != "false",
        "multi_shot": meta.get("multi_shot", "").lower() == "true",
        "first_frame": resolve_ref(project, scene, meta.get("first_frame")),
        "last_frame": resolve_ref(project, scene, meta.get("last_frame")),
        "ref_images": [resolve_ref(project, scene, s.strip())
                       for s in meta.get("ref_images", "").split(",") if s.strip()],
    }


MODEL_MARK = {"seedance": "seedance", "kling": "kling", "omni": "gemini"}


def provider(name):
    if name in ("", "seedance"):
        import seedance
        return seedance
    if name == "kling":
        import kling
        return kling
    if name == "omni":
        import omni
        return omni
    sys.exit(f"unknown provider: {name}")


def extract_last_frame(video):
    """For providers that don't return one (Kling, Omni). Needs ffmpeg; skipped otherwise."""
    if not shutil.which("ffmpeg"):
        return None
    frame = video.with_name(video.stem + "-last.jpg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(frame)], check=False)
    return str(frame) if frame.exists() else None


def cmd_render(a):
    scene = Path(a.scene)
    project = project_of(scene)
    src = scene / "prompts" / f"{a.version}.md" if a.version else latest(scene)
    meta, body = parse(src)
    prompt = section(body, "Prompt")
    if not prompt:
        sys.exit(f"{src}: '## Prompt' section is empty")
    cfg = build_cfg(meta, project, scene)
    name = meta.get("provider") or "seedance"
    prov = provider(name)
    if not cfg["model"] or MODEL_MARK[name] not in cfg["model"]:
        if cfg["model"]:
            print(f"warning: model {cfg['model']} is not a {name} model; using {prov.DEFAULT_MODEL}", file=sys.stderr)
        cfg["model"] = prov.DEFAULT_MODEL

    if a.dry_run:
        print(json.dumps(prov.redact(prov.build_body(cfg, prompt)), ensure_ascii=False, indent=2))
        return
    n = len(list((scene / "renders").glob(f"{src.stem}-r*.json"))) + 1
    stem = f"{src.stem}-r{n}"
    try:
        res = prov.run(cfg, prompt, scene / "renders", stem)
    except RuntimeError as e:
        append_log(scene, [src.stem, today(), "生成エラー", "", stem, str(e)[:200]])
        sys.exit(str(e))
    if res.get("video") and not res.get("last_frame"):
        res["last_frame"] = extract_last_frame(Path(res["video"]))
    note = f"tokens={res.get('tokens')}" if res["status"] == "succeeded" else json.dumps(res.get("error"), ensure_ascii=False)
    append_log(scene, [src.stem, today(), f"生成 {name}/{cfg['model']}",
                       "", f"renders/{stem}.mp4" if res.get("video") else stem, f"{res['status']} {note}"])
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["status"] != "succeeded":
        sys.exit(1)


def cmd_status(a):
    p = ROOT / a.project
    for scene in sorted(d for d in (p / "scenes").iterdir() if d.is_dir()):
        vs = versions(scene)
        renders = sorted((scene / "renders").glob("*.mp4"), key=lambda f: f.stat().st_mtime)
        last = renders[-1].name if renders else "-"
        meta, body = parse(vs[-1]) if vs else ({}, "")
        filled = "済" if section(body, "Prompt") else "未記入"
        print(f"{scene.name:28} {vs[-1].stem if vs else '-':5} prompt:{filled:4} renders:{len(renders):2} latest:{last}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("project"); s.set_defaults(f=cmd_init)
    s = sub.add_parser("scene"); s.add_argument("project"); s.add_argument("nn"); s.add_argument("slug"); s.set_defaults(f=cmd_scene)
    s = sub.add_parser("revise"); s.add_argument("scene"); s.add_argument("--reason", required=True); s.set_defaults(f=cmd_revise)
    s = sub.add_parser("diff"); s.add_argument("scene"); s.add_argument("a", nargs="?"); s.add_argument("b", nargs="?"); s.set_defaults(f=cmd_diff)
    s = sub.add_parser("render"); s.add_argument("scene"); s.add_argument("--version"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_render)
    s = sub.add_parser("status"); s.add_argument("project"); s.set_defaults(f=cmd_status)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
