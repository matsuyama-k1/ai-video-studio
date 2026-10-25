---
name: video-prompt
description: 台本・絵コンテ・参考画像をプロジェクトにまとめ、シーンごとに英語の動画プロンプトをバージョン管理(修正根拠つき)しながら作り、Seedance / Kling / Gemini Omni Flash で生成する。「動画プロジェクトを始めたい」「シーンのプロンプトを作って」「このシーンを直して」「生成して」「プロンプトをエンハンス」などのときに使う。
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py" init *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py" scene *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py" revise *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py" diff *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py" status *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" check *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" render *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" to-prompts *) Bash(open *) Bash(ffprobe *)
---

# video-prompt

全体の流れ: **素材をまとめる → シーンを分ける → シーンごとにプロンプト化 → 生成 → 評価して改訂 → 再生成**

ツールは `python3 "${CLAUDE_SKILL_DIR}/scripts/vp.py"`(以下 `vp`)。作業フォルダ(`projects/` と `.env.local` がある場所)で実行する。準備ができていなければ、先に setup スキルを案内する。どのステップでも、ユーザーの確認を取ってから次へ進む。生成は課金が発生するので、必ず明示的なOKをもらってから実行する。

## ワークスペース

```
projects/<project>/
  project.md        既定の provider・model・比率・解像度・尺 + 固定記述(キャラ・場所・スタイルの英語)
  script.md         台本
  storyboard/       絵コンテ(storyboard スキル): cuts.json・frames/・index.html
  refs/             参考画像 + index.md(何の画像で、どのシーンで使うか)
  scenes/sNN-<slug>/
    scene.md        台本の該当箇所・日本語ドラフト(8要素)・使う参考画像・前後のつながり
    prompts/vNNN.md プロンプト本体。ヘッダに生成パラメータ、本文に Prompt / 日本語要約 / 修正根拠 / 評価
    renders/        vNNN-rK.mp4・vNNN-rK.json・vNNN-rK-last.jpg(最終フレーム)
    log.md          変更履歴(改訂と生成を1行ずつ追記)
```

**ルール**

- プロンプトファイルは上書きしない。直すときは必ず `vp revise` で新しいバージョンを作る。
- 生成結果は、元になったプロンプトのバージョンと同じ名前で保存される(v002-r1 = v002の1回目)。

## 1. 素材をまとめる

1. `vp init <project>` を実行する。
2. ユーザーの台本を `script.md` に貼る。
3. 参考画像を `refs/` にコピーし、`refs/index.md` に1行ずつ説明を書く。ファイル名は `char-` `loc-` `prop-` `style-` `frame-` で始める。
4. `project.md` の固定記述を、英語で書いてユーザーに確認してもらう。キャラクター・場所・スタイルの見た目を書く欄で、各シーンのプロンプトに一字一句コピーして使う。これがシーン間で見た目がぶれないようにする要になる。
5. `project.md` のヘッダで、既定の provider と model を決める(下の「providers」を参照)。

## 2. 絵コンテ → シーン

絵コンテは **storyboard スキル**で作る。カットごとに画像・構図・カメラ・ライティング・テンポ・音声を組み立て、参考動画があればそれも読み取る。

最後に `sb.py to-prompts` を実行すると、scene ごとに `scenes/<scene>/prompts/vNNN.md` が自動で作られる。そのあとはステップ3の方針で英語を整え、ステップ4へ進む。

絵コンテを使わずに直接シーンを作るときは、次のとおり。

- `vp scene <project> <nn> <slug>` でシーンを作り、`scene.md` の日本語ドラフト(8要素)を埋める。
- 足りない要素は推測で埋めず、AskUserQuestion で候補を出して選んでもらう。

## 3. プロンプト化(エンハンス)

シーンごとに英語のプロンプトを **3案** 作り、選んでもらう。書き方は [reference.md](reference.md) に従う。

| 案 | 方針 |
| --- | --- |
| A 忠実 | ドラフトをそのまま整った英語にする |
| B シネマティック | レンズ・光・質感・カメラワークを具体化する |
| C ショット分割 | `Shot 1 / Shot 2` などで展開をつける |

- 固定記述は一字一句そのまま入れる。
- 尺・比率・解像度はプロンプトに書かず、ヘッダに書く。
- 選ばれた案を `prompts/v001.md` の `## Prompt` に書く。`## 日本語要約` にはその要約を書く。ヘッダのパラメータと参照画像も埋める(パスはプロジェクトルートからの相対パス)。

ヘッダの例:

```
provider: seedance
model: dreamina-seedance-2-0-mini-260615
resolution: 720p
ratio: 16:9
duration: 5
audio: true
first_frame: prev:last
ref_images: refs/char-aya.png, refs/loc-office.png
```

- 先頭フレームと末尾フレームの指定(first_frame / last_frame)と、参考画像(ref_images)は同時に使えない(Seedance)。

## 4. 生成

1. `vp render <scene_dir> --dry-run` で、送信する内容を確認する。
2. モデル・解像度・尺・概算料金をユーザーに見せ、OKをもらう。
3. `vp render <scene_dir>` を実行する。数分かかるので、Bash の `run_in_background` で実行する。
   - 特定のバージョンを生成するときは `--version v002` を付ける。
4. 終わったら、mp4 のパスと結果を報告する。log.md には自動で1行追記される。
5. 全体の進み具合は `vp status <project>` で確認できる。

## 5. 評価して改訂

1. ユーザーに結果を見てもらい、感想を、生成元バージョンの `## 評価` に書く。
2. 直すときは `vp revise <scene_dir> --reason "<根拠>"` を実行する。最新版がコピーされ、新しいバージョンができる。
   - 根拠には「どの生成結果の、何が問題で、何を変えるか、なぜか」を1行で書く。
   - 例: `v001-r1: 笑顔が硬い → 口元と肩の動きを具体化(ガイド: 感情は動作で書く)`
3. 新しいバージョンの `## Prompt` を直す。直すのは根拠に書いた箇所だけにする。
4. `vp diff <scene_dir>` で差分をユーザーに見せる。そのあと、4の生成に戻る。

## providers

プロンプトのヘッダの `provider:` で切り替える。`model:` が別の provider のものなら、その provider の既定モデルに置き換わる(警告が出る)。

| provider | 主なモデル | 5秒720pの目安 | 尺 | キー(.env.local) |
| --- | --- | --- | --- | --- |
| `seedance` | `dreamina-seedance-2-0-mini-260615`(既定)、`dreamina-seedance-2-0-260128`、`dreamina-seedance-2-5-260628` | $0.38 / $0.76 / $1.16 | 4〜15秒(2.5は30秒) | `ARK_API_KEY` |
| `kling` | `kling-3.0`(既定)、`kling-3.0-turbo`、`kling-4.0`、参考画像ありは自動で `kling-3.0-omni` | $0.63(音声あり)/ $0.42(無音) | 3〜15秒(4.0は30秒) | `KLING_API_KEY` |
| `omni` | `gemini-omni-1.1-flash` | $0.51 | パラメータなし(プロンプトで `[0-3s] ...` と指定) | `GEMINI_API_KEY` |

provider ごとの違い:

- **seedance**
  - 先頭フレームと末尾フレームの指定(first_frame / last_frame)と、参考画像(ref_images)は同時に使えない。
  - 最終フレームが自動で保存されるので、次のシーンで `prev:last` を使える。
  - `seedance-1-5-pro-251215` は2026-11-11に提供終了するので使わない。
- **kling**
  - 参考画像は、プロンプトの中で `@image_1`、`@image_2` と書いて指す(ref_images の順番どおり)。
  - ショットを分けるときは、ヘッダに `multi_shot: true` を書き、プロンプトを `shot 1, 3, ...; shot 2, 2, ...;` の形にする。
  - `kling-3.0-turbo` と `kling-4.0` には、音声のオン・オフの指定がない。
  - 生成された動画のURLは30日で消える(ダウンロード済みなので影響なし)。
- **omni**
  - 音声は常に生成される。`audio: false` にすると、プロンプトに「音なし」の指示を足す。
  - 尺を指定するパラメータはなく、プロンプトで指定する。
  - 何も指定しないとショットが切り替わることがあるので、1ショットにしたいときは "single continuous shot" と書く。
  - 無料枠はない。
- **共通**
  - Kling と Omni は最終フレームを返さない。生成後に ffmpeg で最後の画を切り出し、`-last.jpg` として保存する。
  - キーの値は表示しない。

## ワンショット(プロジェクトなし)

1本だけ試すときは、ステップ3の3案を作って選んでもらい、次を実行する。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/seedance.py" --prompt-file <file> --out outputs/<name> [--duration 5 --ratio 16:9]
```
