# Seedance プロンプトの書き方(公式ガイドの要約)

出典: BytePlus ModelArk の「Dreamina Seedance 2.0 series prompt guide」と「Seedance 2.5 prompt guide」、および公式スキル sd2-pe / sd25-pe(2026-10 時点)。

## 基本テンプレート(2.5 / sd25-pe)

```
<Subject> <performs the main action or event> in <scene and environment>.
The visuals present <visual style or mood>.
The camera uses <shot size, camera position, camera movement, or cuts>.
The sound includes <dialogue, ambient sound, sound effects, or music>.
```

## 要素の順番(2.0)

subject → action details → scene/environment → lighting & color tone → camera movement → visual style → image quality → constraints

つまり「誰が・何を」→「どこで・どんな空気で」→「どう撮るか」→ スタイル・画質・制約、の順に書く。

## ルール

- **ショット**: 2.0 は秒数の指定が効きにくいので `Shot 1: … Shot 2: …` と書く。2.5 は `0-3 seconds: … 3-7 seconds: …` のように、すき間のない整数秒で書ける。
- **カメラ**: 1ショットにつき動きは1つにする。medium shot、close-up、slow push-in、lateral tracking、fixed shot、dolly zoom、FPV などはそのまま書いてよい。マイナーな用語は「用語 + 画面で何が起きるか」で書く。
- **動作**: どの部位を、どの程度、どの速さで動かすかを書く。ゆっくり、なめらか、連続した動きが安定する。
- **感情**: 形容詞ではなく、体の動きで表す。例: anxious → "glances at her watch, fingers tapping the desk"。強すぎる感情語は避ける(目が光る不具合の原因になる)。
- **音と文字の記号**:

  | 種類 | 書き方 |
  | --- | --- |
  | セリフ | `{…}` |
  | 効果音 | `<…>` |
  | 音楽 | `(…)` |
  | 画面上の字幕 | `【…】` |

  セリフは `言語 + (なまり) + 話し方 + 話者 + {セリフ}` の形にする。例: `She says softly in Japanese {やっと、ここまで来た}`。英語で話させたいときは "Use English." と明記する。1つのセリフの中で言語を混ぜない。
- **否定の指示**: 基本は肯定文で書く。字幕と音だけは否定でも効く: "No subtitles."、"No BGM; only ambient and action sounds."
- **制約語**: 2.0 では "no subtitles, no logo or watermark, the face stays stable without deformation, movements are natural and smooth" を足すと安定する。2.5 では、ユーザーが頼んでいない制約語は足さない。
- **参照素材**: 被写体には毎回 `@Image1` を付ける。素材は、人物1〜2枚、背景1枚、カメラワーク用の動画1本、音声1本くらいがよい。2.0 は、実在人物の顔が写った素材をそのまま入力できない。
- **パラメータ**: 尺・比率・解像度はプロンプトに書かず、APIのパラメータで渡す。

## 例(ユーザーの元プロンプトをテンプレートで整えたもの)

```
A woman in her late twenties stands by the floor-to-ceiling window of a near-future office, backlit by the low morning sun.
She slowly turns toward the camera, her shoulders relaxing, and a quiet smile spreads across her face.
The visuals present a warm, cinematic live-action look with soft golden rim light and gentle lens flare.
The camera uses a slow dolly-in from a medium shot to a close-up, keeping focus on her expression.
The sound includes calm solo piano music and faint city traffic outside the window. She says softly in English {I finally made it here.}
```

## Kling 向けの書き方(公式クイックスタート)

- 式: `Subject (description) + Subject movement + Scene (description) + (Camera language + Lighting + Atmosphere)`
- 画像から生成するときは、Subject と Movement だけでよい(見た目は画像が決める)。
- 文は短くする。動作は5〜10秒に収まる量にする。
- 数や物の個数、複雑な物理表現は苦手。
- カメラの指示がないと、固定カメラになる。
- セリフは二重引用符で書く(例: `She says, "I finally made it here."`)。公式ドキュメントでは未確認なので、結果を見て調整する。

## Gemini Omni Flash 向けの書き方(公式ガイド)

- 何も指定しないとショットが切り替わる。1ショットにしたいときは "single continuous shot" または "No scene cuts" と書く。
- 尺は、自然な文章か、`[0-3s] ... [3-6s] ...` のようなタイムコードで書く。
- 音とBGMは具体的に書く。要らないものは "No dialogue"、"No extra sound effects" と書く。
- 画面に出す文字は、そのままの文言でプロンプトに書く。
- セリフは二重引用符で書く。評価されているのは英語だけ。
