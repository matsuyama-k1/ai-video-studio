#!/usr/bin/env python3
"""First-video tutorial: a ready-made 10-second storyboard (2 cuts x 5 s, one scene = one generation).

  tutorial.py themes                                     list the preset themes
  tutorial.py new --theme cat|coffee|city [--aspect 16:9|9:16] [--provider kling|seedance|omni]
                                                         make projects/first-video (or first-video-2, ...)
  tutorial.py new --theme blank ...                      same shape, but the cuts are left for Claude to fill

Standard library only. Run from the folder that holds projects/.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent.parent / "storyboard" / "scripts" / "sb.py"
SCENE = "s01-first"

THEMES = {
    "cat": {
        "title": "はじめての動画: 日だまりの猫",
        "style_ja": "やわらかい自然光の実写、浅い被写界深度",
        "style_en": "a soft, natural-light live-action look with shallow depth of field",
        "subject": ("茶トラの猫(白い足先、ふわふわの毛)",
                    "a fluffy orange tabby cat with white paws,"),
        "cuts": [
            dict(summary_ja="日だまりの窓辺で丸くなって眠る猫。しっぽがゆっくり揺れる",
                 action=("丸くなって眠り、しっぽだけがゆっくり揺れる", "sleeps curled up, only its tail slowly swaying"),
                 setting=("午後のリビングの、日の当たる窓辺", "on a sunlit windowsill in a quiet living room in the afternoon"),
                 composition=dict(shot="WS", angle="eye-level", lens="35mm", framing="cat centered, framed by the window",
                                  ja="ワイド、目線の高さ、猫を中央に窓枠で囲む"),
                 camera=("slow dolly-in", "ゆっくり寄る"),
                 lighting=("レースのカーテン越しの午後の日差し", "warm afternoon sunlight streaming through sheer curtains"),
                 color=("はちみつ色の暖色、ハイライトはやわらかく", "warm honey tones with soft highlights"),
                 tempo=("slow", "ゆったり。しっぽの揺れを見せる"),
                 audio=dict(music="gentle acoustic guitar", ambience="faint birdsong outside", sfx="",
                            ja="やさしいアコースティックギター、外の小鳥の声"),
                 narration_ja="午後の日だまりは、特等席。",
                 frame_prompt="Cinematic still, wide shot at eye level, 35mm lens. A fluffy orange tabby cat with white paws "
                              "sleeps curled up in the center of a sunlit windowsill in a quiet living room, framed by the window. "
                              "Warm afternoon sunlight streams through sheer curtains, warm honey tones, soft highlights, "
                              "shallow depth of field, natural-light live-action look."),
            dict(summary_ja="目を覚まして大きくあくび。前足をぐーっと伸ばす",
                 action=("目を開けて大きくあくびをし、前足を前にぐーっと伸ばす",
                         "opens its eyes, gives a big yawn, and stretches its front paws far forward"),
                 setting=("同じ窓辺", "on the same sunlit windowsill"),
                 composition=dict(shot="CU", angle="eye-level", lens="85mm", framing="cat's face and front paws fill the frame",
                                  ja="アップ、目線の高さ、顔と前足で画面を埋める"),
                 camera=("fixed shot", "固定"),
                 lighting=("横からの暖かい日差し、毛先が光る", "warm side sunlight making the tips of its fur glow"),
                 color=("はちみつ色の暖色", "warm honey tones"),
                 tempo=("slow", "あくびで一瞬止まり、伸びで終わる"),
                 audio=dict(music="gentle acoustic guitar", ambience="faint birdsong outside", sfx="a tiny soft meow",
                            ja="ギターの続き、小さな「にゃ」"),
                 narration_ja="",
                 frame_prompt="Cinematic still, close-up at eye level, 85mm lens. A fluffy orange tabby cat with white paws "
                              "yawning widely on a sunlit windowsill, its face and front paws filling the frame. Warm side "
                              "sunlight makes the tips of its fur glow, warm honey tones, shallow depth of field, "
                              "natural-light live-action look."),
        ],
    },
    "coffee": {
        "title": "はじめての動画: 朝のコーヒー",
        "style_ja": "明るくやわらかい朝の実写、浅い被写界深度",
        "style_en": "a bright, soft morning live-action look with shallow depth of field",
        "subject": ("30代前半の女性(肩までの茶髪、クリーム色のニット)",
                    "a Japanese woman in her early thirties with shoulder-length brown hair, wearing a cream knit sweater,"),
        "cuts": [
            dict(summary_ja="ドリッパーにお湯を注ぐ手元。湯気が立ちのぼる",
                 action=("細口のケトルで、ドリッパーにゆっくりお湯を注ぐ(手元だけが映る)",
                         "slowly pours hot water from a gooseneck kettle into a pour-over dripper, only her hands visible, steam rising"),
                 setting=("朝の明るいキッチンの木のカウンター", "at a wooden counter in a bright, minimal kitchen in the early morning"),
                 composition=dict(shot="CU", angle="high angle", lens="50mm", framing="kettle spout and dripper in the center",
                                  ja="アップ、やや上から、ケトルの口とドリッパーを中央に"),
                 camera=("fixed shot", "固定"),
                 lighting=("横の窓からのやわらかい朝の光、湯気が光る", "soft morning window light from the side, the steam glowing in the light"),
                 color=("白と木の色、やわらかい暖色", "clean whites and natural wood with soft warm tones"),
                 tempo=("slow", "ゆったり。注ぐ音を聞かせる"),
                 audio=dict(music="calm lo-fi piano", ambience="quiet morning kitchen", sfx="the gentle trickle of pouring water",
                            ja="静かなピアノ、お湯を注ぐ音"),
                 narration_ja="朝の一杯から、一日が始まる。",
                 frame_prompt="Cinematic still, close-up from a slight high angle, 50mm lens. The hands of a Japanese woman "
                              "in a cream knit sweater pour hot water from a gooseneck kettle into a pour-over dripper on a "
                              "wooden counter in a bright, minimal kitchen. Soft morning window light from the side, steam "
                              "glowing in the light, clean whites and natural wood, shallow depth of field."),
            dict(summary_ja="窓辺でカップを両手で持ち、一口飲んでほっと微笑む",
                 action=("カップを両手で持って一口飲み、肩の力が抜けて微笑む",
                         "holds the mug with both hands, takes a sip, and her shoulders drop as a relaxed smile appears"),
                 setting=("同じキッチンの窓辺", "by the window of the same bright kitchen"),
                 composition=dict(shot="MS", angle="eye-level", lens="50mm", framing="subject on the right third, window on the left",
                                  ja="ミディアム、目線の高さ、右1/3に人物・左に窓"),
                 camera=("slow push-in", "ゆっくり寄る"),
                 lighting=("窓からのやわらかい朝の光", "soft morning light from the window falling across her face"),
                 color=("やわらかい暖色", "soft warm tones"),
                 tempo=("slow", "一口飲んで、笑顔で止める"),
                 audio=dict(music="calm lo-fi piano", ambience="faint birdsong outside the window", sfx="",
                            ja="ピアノの続き、窓の外の小鳥"),
                 narration_ja="",
                 frame_prompt="Cinematic still, medium shot at eye level, 50mm lens. A Japanese woman in her early thirties "
                              "with shoulder-length brown hair and a cream knit sweater holds a coffee mug with both hands by "
                              "the window of a bright kitchen, standing on the right third, smiling softly. Soft morning light "
                              "falls across her face, soft warm tones, shallow depth of field."),
        ],
    },
    "city": {
        "title": "はじめての動画: 夕暮れの屋上",
        "style_ja": "夕焼けの実写シネマ調、暖色とすみれ色",
        "style_en": "a cinematic live-action sunset look in orange and violet",
        "subject": ("20代の男性(短い黒髪、紺のジャケット)",
                    "a young Japanese man in his twenties with short black hair, wearing a navy jacket,"),
        "cuts": [
            dict(summary_ja="夕焼けに染まるビル街。屋上の手すりに立つ男性の後ろ姿",
                 action=("屋上の手すりの前に立ち、街を見渡している(画面の中では小さく)",
                         "stands at the rooftop railing, small in the frame, looking out over the city"),
                 setting=("夕暮れの、ガラスのビルが並ぶ街を見下ろす屋上", "on a rooftop above a dense city of glass towers at sunset"),
                 composition=dict(shot="EWS", angle="eye-level", lens="24mm", framing="skyline fills the frame, man silhouetted on the left third",
                                  ja="超ロング、目線の高さ、街並みで画面を埋め、左1/3に人物のシルエット"),
                 camera=("slow pan right across the skyline", "ゆっくり右へパン"),
                 lighting=("沈む夕日の逆光", "a low setting sun backlighting the skyline"),
                 color=("オレンジからすみれ色の空", "an orange-to-violet sky gradient"),
                 tempo=("slow", "ゆったり。街を見せる"),
                 audio=dict(music="soft ambient synth pad", ambience="distant city hum and wind", sfx="",
                            ja="やわらかいシンセ、遠くの街の音と風"),
                 narration_ja="今日も、よくがんばった。",
                 frame_prompt="Cinematic still, extreme wide shot at eye level, 24mm lens. A dense city of glass towers at "
                              "sunset fills the frame; a young man in a navy jacket stands at a rooftop railing on the left "
                              "third, silhouetted and small in the frame. A low setting sun backlights the skyline, an "
                              "orange-to-violet sky gradient, cinematic live-action look."),
            dict(summary_ja="風に髪がなびき、振り返って小さく笑う",
                 action=("風に髪がなびき、カメラの方へ振り返って小さく笑う",
                         "turns toward the camera as the wind moves his hair, and gives a small smile"),
                 setting=("同じ屋上", "on the same rooftop at sunset"),
                 composition=dict(shot="MCU", angle="eye-level", lens="85mm", framing="face on the right third, blurred skyline behind",
                                  ja="バストアップ、目線の高さ、右1/3に顔・背景はぼけた街"),
                 camera=("slow orbit around him", "ゆっくり回り込む"),
                 lighting=("夕日の逆光、髪と肩に暖色のリムライト", "golden sunset backlight with a warm rim light on his hair and shoulders"),
                 color=("オレンジとすみれ色", "orange and violet tones"),
                 tempo=("slow", "振り返りに3秒、笑顔で止める"),
                 audio=dict(music="soft ambient synth pad", ambience="wind on the rooftop", sfx="",
                            ja="シンセの続き、屋上の風"),
                 narration_ja="",
                 frame_prompt="Cinematic still, medium close-up at eye level, 85mm lens. A young Japanese man in his twenties "
                              "with short black hair and a navy jacket on a rooftop at sunset, his face on the right third, "
                              "hair moving in the wind, a small smile. Golden sunset backlight with a warm rim light on his "
                              "hair and shoulders, blurred skyline of glass towers behind, orange and violet tones."),
        ],
    },
}


def free_name(base="first-video"):
    name, n = base, 1
    while (Path("projects") / name).exists():
        n += 1
        name = f"{base}-{n}"
    return name


def make_cut(template, i, theme, spec):
    c = json.loads(json.dumps(template))
    c.pop("ref_video", None)
    sub_ja, sub_en = theme["subject"]
    c.update(id=f"c0{i}", scene=SCENE, duration=5, summary_ja=spec["summary_ja"], refs=[], frame="",
             frame_source="", frame_prompt=spec["frame_prompt"], narration_ja=spec["narration_ja"], notes_ja="",
             use_frame_as_first_frame=(i == 1))
    c["subject"] = {"ja": sub_ja, "en": sub_en}
    for key in ("action", "setting", "lighting", "color"):
        c[key] = {"ja": spec[key][0], "en": spec[key][1]}
    c["composition"] = spec["composition"]
    c["camera"] = {"move": spec["camera"][0], "ja": spec["camera"][1]}
    c["tempo"] = {"pace": spec["tempo"][0], "transition_out": "cut", "ja": spec["tempo"][1]}
    c["audio"] = dict(spec["audio"], dialogue=[])
    return c


def cmd_themes(a):
    for key, t in THEMES.items():
        print(f"{key:7} {t['title']} — " + " / ".join(c["summary_ja"] for c in t["cuts"]))


def cmd_new(a):
    name = free_name()
    r = subprocess.run([sys.executable, str(SB), "init", name], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    p = Path("projects") / name / "storyboard" / "cuts.json"
    data = json.loads(p.read_text())
    template = data["cuts"][0]
    data["project"].update(aspect=a.aspect, provider=a.provider,
                           voices={"narrator": "Kyoko", "default": "Kyoko"}, ref_videos=[])
    if a.theme == "blank":
        data["project"].update(title="はじめての動画")
        cuts = []
        for i in (1, 2):
            c = json.loads(json.dumps(template))
            c.pop("ref_video", None)
            c.update(id=f"c0{i}", scene=SCENE, duration=5, refs=[], frame="", frame_source="",
                     summary_ja="", frame_prompt="", narration_ja="", use_frame_as_first_frame=(i == 1))
            c["action"] = {"ja": "", "en": ""}   # sb check flags these until Claude fills them
            cuts.append(c)
        data["cuts"] = cuts
    else:
        theme = THEMES[a.theme]
        data["project"].update(title=theme["title"], style_ja=theme["style_ja"], style_en=theme["style_en"])
        data["cuts"] = [make_cut(template, i, theme, spec) for i, spec in enumerate(theme["cuts"], 1)]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"project": name, "cuts_json": str(p), "theme": a.theme}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("themes").set_defaults(f=cmd_themes)
    s = sub.add_parser("new")
    s.add_argument("--theme", required=True, choices=[*THEMES, "blank"])
    s.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    s.add_argument("--provider", default="kling", choices=["kling", "seedance", "omni"])
    s.set_defaults(f=cmd_new)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
