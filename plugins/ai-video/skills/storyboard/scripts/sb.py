#!/usr/bin/env python3
"""Storyboard: cuts with a frame image + composition / camera / lighting / tempo / audio,
rendered as an HTML sheet and turned into per-scene prompts for the video-prompt skill.

  sb.py init <project>                         add projects/<project>/storyboard/ (creates the project if needed)
  sb.py check <project>                        validate cuts.json, print a one-line-per-cut summary
  sb.py grab <project> <cut> <video> <sec>     use a frame from a video as the cut's picture
  sb.py frame <project> <cut> [--provider codex|openai|seedream|gemini] [--quality low|medium|high] [--dry-run]
                                               generate the cut's picture from frame_prompt (+ refs)
  sb.py edit <project> <cut> --prompt "..." [--mask m.png] [--ref refs/x.png] [--provider openai] [--reason "..."]
                                               edit the current picture (mask: transparent = area to change)
  sb.py tts <project> [--rate 180]             temporary voice for every cut (macOS say) -> storyboard/audio/
  sb.py animatic <project> [--port 8765]       play / edit the storyboard in the browser (edits saved to cuts.json)
  sb.py export <project>                       storyboard/animatic.mp4 (stills + camera move + voice + subtitles)
  sb.py sheet <project> [--cols 3]             storyboard/sheet.png (all cuts on one page)
  sb.py render <project> [--open]              write storyboard/index.html
  sb.py to-prompts <project> [--scenes s01,s02] [--reason "..."]
                                               write/revise scenes/<scene>/prompts/vNNN.md from the cuts

Run from the repository root. Standard library + ffmpeg.
"""
import argparse
import hashlib
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VP_DIR = HERE.parent.parent / "video-prompt" / "scripts"
sys.path.insert(0, str(VP_DIR))
sys.path.insert(0, str(HERE))
import vp  # noqa: E402

ROOT = Path("projects")
TEMPLATE = HERE.parent / "templates" / "cuts.json"

PREPOSITIONS = {"in", "at", "on", "by", "near", "inside", "under", "beside", "through", "across", "along",
                "outside", "over", "behind", "among", "against", "atop", "within", "into", "onto", "from"}

SHOT_NAMES = {
    "EWS": "extreme wide shot", "WS": "wide shot", "FS": "full shot", "MWS": "medium wide shot",
    "MS": "medium shot", "MCU": "medium close-up", "CU": "close-up", "ECU": "extreme close-up",
    "OTS": "over-the-shoulder shot", "POV": "point-of-view shot", "INSERT": "insert shot",
}


# ---------- data ----------

def sb_dir(project):
    return ROOT / project / "storyboard"


def load(project):
    p = sb_dir(project) / "cuts.json"
    if not p.exists():
        sys.exit(f"{p} not found; run: sb.py init {project}")
    return json.loads(p.read_text())


def save(project, data):
    (sb_dir(project) / "cuts.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def find_cut(data, cut_id):
    for c in data["cuts"]:
        if c["id"] == cut_id:
            return c
    sys.exit(f"cut {cut_id} not found")


def g(d, *keys, default=""):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d not in (None, "") else default


# ---------- commands ----------

def cmd_init(a):
    p = ROOT / a.project
    if not p.exists():
        vp.cmd_init(argparse.Namespace(project=a.project))
    d = sb_dir(a.project)
    if (d / "cuts.json").exists():
        sys.exit(f"{d}/cuts.json already exists")
    (d / "frames").mkdir(parents=True, exist_ok=True)
    (p / "refs" / "video").mkdir(parents=True, exist_ok=True)
    data = json.loads(TEMPLATE.read_text())
    data["project"]["title"] = a.project
    save(a.project, data)
    (d / "log.md").write_text("# 絵コンテの変更履歴\n\n| 日時 | 対象 | 変更 | 理由 |\n| --- | --- | --- | --- |\n")
    print(d)


def cmd_check(a):
    data = load(a.project)
    total, problems = 0.0, []
    for c in data["cuts"]:
        total += float(c.get("duration") or 0)
        for key in ("id", "scene", "duration"):
            if not c.get(key):
                problems.append(f"{c.get('id', '?')}: missing {key}")
        if not g(c, "action", "en"):
            problems.append(f"{c['id']}: action.en is empty")
        if c.get("frame") and not (ROOT / a.project / c["frame"]).exists():
            problems.append(f"{c['id']}: frame file not found: {c['frame']}")
        print(f"{c.get('id', '?'):4} {c.get('scene', '-'):22} {c.get('duration', '-'):>4}s "
              f"{g(c, 'composition', 'shot'):5} {g(c, 'camera', 'move')[:28]:28} {g(c, 'summary_ja')[:30]}")
    print(f"--- {len(data['cuts'])} cuts, {total:.1f}s total")
    for p in problems:
        print("!", p)


def cmd_grab(a):
    import frames
    data = load(a.project)
    print(frames.grab(ROOT / a.project, find_cut(data, a.cut), a.video, a.sec))
    save(a.project, data)


def cmd_frame(a):
    import frames
    import imagegen
    data = load(a.project)
    cut = find_cut(data, a.cut)
    if a.dry_run:
        refs = [str(ROOT / a.project / r) for r in cut.get("refs") or []]
        print(json.dumps(imagegen.preview(a.provider, cut.get("frame_prompt") or "", refs,
                                          data["project"].get("aspect") or "16:9"), ensure_ascii=False, indent=2))
        return
    print(frames.generate(ROOT / a.project, data, cut, a.provider, quality=a.quality))
    save(a.project, data)


def cmd_edit(a):
    import frames
    data = load(a.project)
    cut = find_cut(data, a.cut)
    mask = Path(a.mask).read_bytes() if a.mask else None
    refs = a.ref if a.ref is not None else []
    print(frames.edit(ROOT / a.project, data, cut, a.provider, a.prompt, mask, refs, a.quality, a.reason))
    save(a.project, data)


# ---------- HTML sheet ----------

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e1dc;--accent:#3a6ff7;--tag:#eef1fb}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1e1e21;--ink:#ececef;--muted:#9a9aa2;--line:#2e2e33;--accent:#7d9cff;--tag:#252a3a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
header{padding:24px 24px 8px}h1{margin:0 0 4px;font-size:22px}.sub{color:var(--muted)}
.timeline{display:flex;height:28px;margin:16px 24px;border-radius:6px;overflow:hidden;border:1px solid var(--line)}
.timeline div{display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--ink);border-right:1px solid var(--line);white-space:nowrap;overflow:hidden}
.scene{margin:24px}.scene h2{font-size:15px;margin:0 0 10px;color:var(--muted);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.cut{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.frame{aspect-ratio:var(--ar);background:repeating-linear-gradient(45deg,var(--line) 0 2px,transparent 2px 12px);display:flex;align-items:center;justify-content:center;color:var(--muted)}
.frame img{width:100%;height:100%;object-fit:cover;display:block}
.head{display:flex;gap:8px;align-items:baseline;padding:10px 12px 4px}.id{font-weight:700;font-size:16px}.dur{color:var(--accent);font-weight:600}
.tags{display:flex;flex-wrap:wrap;gap:4px;padding:0 12px 6px}.tags span{background:var(--tag);border-radius:4px;padding:1px 6px;font-size:12px}
.sum{padding:0 12px 8px;font-weight:600}
dl{margin:0;padding:0 12px 12px;display:grid;grid-template-columns:72px 1fr;gap:4px 8px}dt{color:var(--muted);font-size:12px}dd{margin:0;font-size:13px}
details{border-top:1px solid var(--line);padding:6px 12px;font-size:12px;color:var(--muted)}details pre{white-space:pre-wrap;margin:6px 0 0;font:12px/1.5 ui-monospace,Menlo,monospace;color:var(--ink)}
.line{font-style:italic}
@media print{body{background:#fff}.cut{break-inside:avoid}}
"""


def esc(s):
    return html.escape(str(s or ""))


def audio_ja(c):
    a = c.get("audio") or {}
    parts = []
    for d in a.get("dialogue") or []:
        parts.append(f"<span class='line'>{esc(d.get('speaker'))}「{esc(d.get('line'))}」</span>")
    if a.get("ja"):
        parts.append(esc(a["ja"]))
    return "<br>".join(parts)


def card(c, project):
    comp, cam, tempo = c.get("composition") or {}, c.get("camera") or {}, c.get("tempo") or {}
    img = f"<img src='../{esc(c['frame'])}' alt='{esc(c['id'])}'>" if c.get("frame") else "画像なし"
    tags = [comp.get("shot"), comp.get("angle"), comp.get("lens"), cam.get("move"), tempo.get("pace")]
    rows = [
        ("構図", comp.get("ja")), ("カメラ", cam.get("ja")), ("光", g(c, "lighting", "ja")),
        ("色・質感", g(c, "color", "ja")), ("動き", g(c, "action", "ja")), ("場所", g(c, "setting", "ja")),
        ("音", audio_ja(c)), ("テンポ", tempo.get("ja")), ("つなぎ", tempo.get("transition_out")),
        ("参考", ", ".join(c.get("refs") or []) + (f" / 動画 {g(c, 'ref_video', 'file')} {g(c, 'ref_video', 'start')}–{g(c, 'ref_video', 'end')}s: {g(c, 'ref_video', 'borrow_ja')}" if c.get("ref_video") else "")),
        ("メモ", c.get("notes_ja")),
    ]
    dl = "".join(f"<dt>{k}</dt><dd>{v if k == '音' else esc(v)}</dd>" for k, v in rows if v)
    en = "\n".join(f"{k}: {v}" for k, v in [
        ("subject", g(c, "subject", "en")), ("action", g(c, "action", "en")), ("setting", g(c, "setting", "en")),
        ("composition", ", ".join(x for x in [SHOT_NAMES.get(comp.get("shot", ""), comp.get("shot", "")), comp.get("angle"), comp.get("lens"), comp.get("framing")] if x)),
        ("camera", cam.get("move")), ("lighting", g(c, "lighting", "en")), ("color", g(c, "color", "en")),
        ("sound", sound_en(c, "kling")), ("frame_prompt", c.get("frame_prompt"))] if v)
    return (f"<article class='cut'><div class='frame'>{img}</div>"
            f"<div class='head'><span class='id'>{esc(c['id'])}</span><span class='dur'>{esc(c.get('duration'))}s</span></div>"
            f"<div class='tags'>{''.join(f'<span>{esc(t)}</span>' for t in tags if t)}</div>"
            f"<div class='sum'>{esc(c.get('summary_ja'))}</div><dl>{dl}</dl>"
            f"<details><summary>English</summary><pre>{esc(en)}</pre></details></article>")


def cmd_render(a):
    data = load(a.project)
    proj, cuts = data["project"], data["cuts"]
    w, h = (proj.get("aspect") or "16:9").split(":")
    total = sum(float(c.get("duration") or 0) for c in cuts) or 1
    scenes = []
    for c in cuts:
        if not scenes or scenes[-1][0] != c.get("scene"):
            scenes.append((c.get("scene"), []))
        scenes[-1][1].append(c)
    hues = [210, 25, 140, 280, 50, 330, 180, 95]
    timeline = "".join(
        f"<div style='flex:{float(c.get('duration') or 0)};background:hsl({hues[i % len(hues)]} 60% 60% / .35)' "
        f"title='{esc(c['id'])} {esc(c.get('duration'))}s'>{esc(c['id'])}</div>"
        for i, (_, group) in enumerate(scenes) for c in group)
    body = "".join(
        f"<section class='scene'><h2>{esc(name)} · {sum(float(c.get('duration') or 0) for c in group):.1f}s</h2>"
        f"<div class='grid'>{''.join(card(c, a.project) for c in group)}</div></section>"
        for name, group in scenes)
    page = (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(proj.get('title'))} 絵コンテ</title><style>{CSS}</style></head>"
            f"<body style='--ar:{w}/{h}'><header><h1>{esc(proj.get('title'))} 絵コンテ</h1>"
            f"<div class='sub'>{len(cuts)}カット · {total:.1f}秒 · {esc(proj.get('aspect'))} · {esc(proj.get('style_ja'))}</div></header>"
            f"<div class='timeline'>{timeline}</div>{body}</body></html>")
    out = sb_dir(a.project) / "index.html"
    out.write_text(page)
    print(out)
    if a.open:
        subprocess.run(["open", str(out)])


# ---------- cuts -> prompts ----------

def dialogue_en(d, provider):
    who = d.get("speaker") or "The character"
    how = f" {d['delivery']}" if d.get("delivery") else ""
    lang = f" in {d['lang']}" if d.get("lang") else ""
    if provider == "seedance":
        return f"{who} says{how}{lang} {{{d.get('line', '')}}}"
    return f'{who} says{how}{lang}, "{d.get("line", "")}"'


def sound_en(c, provider):
    a = c.get("audio") or {}
    parts = [x for x in (a.get("music"), a.get("ambience"), a.get("sfx")) if x]
    s = ", ".join(parts)
    lines = " ".join(dialogue_en(d, provider) for d in a.get("dialogue") or [])
    if c.get("narration_ja"):
        vo = c["narration_ja"]
        lines += (" " if lines else "") + (f"A voice-over narrator says in Japanese {{{vo}}}" if provider == "seedance"
                                           else f'A voice-over narrator says in Japanese, "{vo}"')
    out = f"The sound includes {s}." if s else ""
    if a.get("none"):
        out = "No dialogue, no music."
    return " ".join(x for x in (out, lines) if x)


def cut_text(c, provider, style_en):
    comp, cam = c.get("composition") or {}, c.get("camera") or {}
    subject, action, setting = g(c, "subject", "en"), g(c, "action", "en"), g(c, "setting", "en")
    first = " ".join(x for x in [subject, action] if x)
    if setting:
        first += f" {setting}" if setting.split()[0].lower() in PREPOSITIONS else f" in {setting}"
    visuals = ", ".join(x for x in [g(c, "lighting", "en"), g(c, "color", "en"), style_en] if x)
    shot = SHOT_NAMES.get(comp.get("shot", ""), comp.get("shot", ""))
    framing = ", ".join(x for x in [shot and f"{'an' if shot[0].lower() in 'aeiou' else 'a'} {shot}", comp.get("angle") and f"{comp['angle']} angle",
                                     comp.get("lens") and f"{comp['lens']} lens", comp.get("framing")] if x)
    camera = "; ".join(x for x in [framing, cam.get("move")] if x)
    sentences = [first.strip().rstrip(".") + "." if first.strip() else "",
                 f"The visuals present {visuals}." if visuals else "",
                 f"The camera uses {camera}." if camera else "",
                 sound_en(c, provider)]
    return " ".join(s for s in sentences if s)


def scene_prompt(cuts, provider, style_en):
    if len(cuts) == 1:
        return cut_text(cuts[0], provider, style_en)
    if provider == "kling":
        return " ".join(f"shot {i}, {int(round(float(c.get('duration') or 1)))}, {cut_text(c, provider, '').rstrip('.')};"
                        for i, c in enumerate(cuts, 1)) + (f" Overall style: {style_en}." if style_en else "")
    if provider == "omni":
        t, parts = 0, []
        for c in cuts:
            d = int(round(float(c.get("duration") or 1)))
            parts.append(f"[{t}-{t + d}s] {cut_text(c, provider, '')}")
            t += d
        return "\n".join(parts) + (f"\nOverall style: {style_en}." if style_en else "")
    return "\n".join(f"Shot {i}: {cut_text(c, provider, '')}" for i, c in enumerate(cuts, 1)) + \
        (f"\nThe whole video has {style_en}." if style_en else "")


def scene_meta(project_dir, data, cuts, provider):
    proj = data["project"]
    meta = vp.project_defaults(project_dir)
    if provider != (meta.get("provider") or "seedance"):
        meta["model"] = ""   # vp.py falls back to this provider's default model
    meta.update(provider=provider, ratio=proj.get("aspect") or meta.get("ratio", ""),
                duration=str(int(round(sum(float(c.get("duration") or 0) for c in cuts)))))
    if provider == "kling" and len(cuts) > 1:
        meta["multi_shot"] = "true"
    first = cuts[0]
    refs = sorted({r for c in cuts for r in c.get("refs") or []})
    meta["first_frame"] = first["frame"] if first.get("frame") and first.get("use_frame_as_first_frame") else ""
    meta["last_frame"] = ""
    meta["ref_images"] = ", ".join(refs)
    if provider == "seedance" and meta["first_frame"] and refs:
        meta["ref_images"] = ""   # Seedance can't mix first_frame and reference images
    return meta


def cmd_to_prompts(a):
    data = load(a.project)
    project_dir = ROOT / a.project
    style_en = g(data, "project", "style_en")
    wanted = set(a.scenes.split(",")) if a.scenes else None
    groups = {}
    for c in data["cuts"]:
        groups.setdefault(c["scene"], []).append(c)
    for scene_id, cuts in groups.items():
        if wanted and not any(scene_id == w or scene_id.startswith(w + "-") for w in wanted):
            continue
        scene = project_dir / "scenes" / scene_id
        defaults = vp.project_defaults(project_dir)
        provider = (data["project"].get("provider") or defaults.get("provider") or "seedance")
        prompt = scene_prompt(cuts, provider, style_en)
        meta = scene_meta(project_dir, data, cuts, provider)
        digest = hashlib.sha1(prompt.encode()).hexdigest()[:10]
        ids = ", ".join(c["id"] for c in cuts)
        summary = "\n".join(f"- {c['id']} ({c.get('duration')}s): {c.get('summary_ja', '')}" for c in cuts)

        if not scene.exists():
            nn, slug = scene_id[1:].split("-", 1) if "-" in scene_id else (scene_id[1:], "scene")
            vp.cmd_scene(argparse.Namespace(project=a.project, nn=nn, slug=slug))
            (scene / "scene.md").write_text(f"# {scene_id}\n\n絵コンテ: {ids}\n\n{summary}\n")
            target, reason = scene / "prompts" / "v001.md", f"絵コンテ {ids} から生成"
        else:
            latest_meta, old_body = vp.parse(vp.latest(scene))
            if latest_meta.get("sb_hash") == digest or vp.section(old_body, "Prompt") == prompt:
                print(f"{scene_id}: unchanged")
                continue
            reason = a.reason or f"絵コンテ {ids} の更新を反映"
            if vp.section(old_body, "Prompt"):
                vp.cmd_revise(argparse.Namespace(scene=str(scene), reason=reason))
            target = vp.latest(scene)
        old_meta, body = vp.parse(target)
        meta.update(version=old_meta["version"], parent=old_meta.get("parent", ""), created=old_meta["created"],
                    sb_hash=digest)
        body = vp.replace_section(body, "Prompt", prompt)
        body = vp.replace_section(body, "日本語要約", summary)
        body = vp.replace_section(body, "修正根拠", f"- {reason}")
        target.write_text(vp.dump(meta, body))
        print(target)


def cmd_tts(a):
    import animatic
    data = load(a.project)
    for line in animatic.tts_all(ROOT / a.project, data, a.rate):
        print(line)
    save(a.project, data)


def cmd_animatic(a):
    import animatic
    project_dir = ROOT / a.project
    data = load(a.project)
    animatic.tts_all(project_dir, data)
    for c in data["cuts"]:
        if not c.get("frame"):
            animatic.placeholder(project_dir, data, c)
    save(a.project, data)
    animatic.serve(project_dir, lambda: load(a.project), lambda d: save(a.project, d), a.port, not a.no_open)


def cmd_export(a):
    import animatic
    data = load(a.project)
    animatic.tts_all(ROOT / a.project, data)
    save(a.project, data)
    print(animatic.export(ROOT / a.project, data))


def cmd_sheet(a):
    import animatic
    print(animatic.contact_sheet(ROOT / a.project, load(a.project), a.cols))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("project"); s.set_defaults(f=cmd_init)
    s = sub.add_parser("check"); s.add_argument("project"); s.set_defaults(f=cmd_check)
    s = sub.add_parser("grab"); s.add_argument("project"); s.add_argument("cut"); s.add_argument("video"); s.add_argument("sec", type=float); s.set_defaults(f=cmd_grab)
    s = sub.add_parser("frame"); s.add_argument("project"); s.add_argument("cut"); s.add_argument("--provider", default="codex"); s.add_argument("--quality"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_frame)
    s = sub.add_parser("edit"); s.add_argument("project"); s.add_argument("cut"); s.add_argument("--prompt", required=True); s.add_argument("--mask"); s.add_argument("--ref", action="append"); s.add_argument("--provider", default="openai"); s.add_argument("--quality"); s.add_argument("--reason"); s.set_defaults(f=cmd_edit)
    s = sub.add_parser("render"); s.add_argument("project"); s.add_argument("--open", action="store_true"); s.set_defaults(f=cmd_render)
    s = sub.add_parser("tts"); s.add_argument("project"); s.add_argument("--rate", type=int); s.set_defaults(f=cmd_tts)
    s = sub.add_parser("animatic"); s.add_argument("project"); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-open", action="store_true"); s.set_defaults(f=cmd_animatic)
    s = sub.add_parser("export"); s.add_argument("project"); s.set_defaults(f=cmd_export)
    s = sub.add_parser("sheet"); s.add_argument("project"); s.add_argument("--cols", type=int, default=3); s.set_defaults(f=cmd_sheet)
    s = sub.add_parser("to-prompts"); s.add_argument("project"); s.add_argument("--scenes"); s.add_argument("--reason"); s.set_defaults(f=cmd_to_prompts)
    a = ap.parse_args()
    try:
        a.f(a)
    except FileNotFoundError as e:
        import toolpath
        sys.exit(toolpath.MISSING if e.filename in ("ffmpeg", "ffprobe") else str(e))
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
