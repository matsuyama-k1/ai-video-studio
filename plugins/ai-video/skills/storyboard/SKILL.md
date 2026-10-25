---
name: storyboard
description: 動画の絵コンテを対話しながら作る。カットごとに、画像・構図・カメラ・ライティング・テンポ・音声を組み立てる。参考動画を入れると、カット割り・構図・カメラワーク・光・テンポを読み取って反映する。絵コンテは claude.ai の Artifact(ページ)として見せ、直すたびに同じページを更新する。コマ画像は Codex や GPT Image で生成し、一部だけの修正もできる。macOS の音声合成で仮音声を付けたアニマティックは、MP4にして動画プレーヤーで再生する。完成した絵コンテは、シーンごとの動画プロンプト(video-prompt スキル)に変換する。「絵コンテを作りたい」「カット割りを考えて」「この動画みたいにしたい」「参考動画を分析して」「絵コンテを再生したい」「アニマティック」などのときに使う。
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" init *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" check *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" grab *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" render *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" tts *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" animatic *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" export *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" sheet *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" to-prompts *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py" set-url *) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/analyze_ref.py" *) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" init *) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" scene *) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" revise *) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" diff *) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" status *) Bash(open *) Bash(ffprobe *)
---

# storyboard

流れ: **聞き取り → 参考動画を読む → カット割り → 1カットずつ組み立てる → コマ画像 → アニマティックで確認 → プロンプトに変換**

動画生成(有料)の前に、アニマティック(静止画を尺どおりに並べ、仮の音声と字幕を付けたもの)で流れ・テンポ・セリフの長さを固める。そうすると、本番の生成を何度もやり直さずに済む。

絵コンテの正本は `projects/<project>/storyboard/cuts.json`。Claude がこのファイルを編集し、スクリプトで確認・表示・変換する。

**絵コンテはいつも Artifact で見せる。** ローカルでWebサーバーを立ち上げる画面(`sb editor`)は、ユーザーが自分で範囲を塗って直したいと言ったときだけ使う。直しの要望はチャットで受け、Claude が `cuts.json` を直して Artifact を更新する。

- `sb` = `python3 "${CLAUDE_SKILL_DIR}/scripts/sb.py"`
- `analyze` = `python3 "${CLAUDE_SKILL_DIR}/scripts/analyze_ref.py"`
- 無料の操作は事前に許可済み。お金がかかる `sb frame`(codex 以外)と `sb edit` は、毎回ユーザーに許可を求める画面が出る。その前に、必ず料金を伝えてOKをもらう。
- どちらも作業フォルダ(`projects/` と `.env.local` がある場所)で実行する。準備ができていなければ、先に setup スキルを案内する。

## 0. 準備

- `sb init <project>` を実行する。プロジェクトがなければ一緒に作られる。
- できるもの: `storyboard/cuts.json`(見本の1カット入り)、`storyboard/frames/`、`storyboard/log.md`、`refs/video/`。
- 見本のカットは、各項目の書き方の例として残しておき、最初のカットを書くときに置き換える。

## 1. 聞き取り

AskUserQuestion で、次をまとめて聞く(1回で最大4問)。

- 目的と公開先(SNS縦型 / YouTube / 広告 / 作品)。ここから縦横比が決まる。
- 全体の長さ(秒)
- トーン・スタイル(実写シネマ / アニメ / ドキュメンタリー調 など)
- 素材の有無(台本、キャラクター画像、参考動画)

答えは `cuts.json` の `project` に書く: `aspect`、`style_ja`、`style_en`、`provider`(既定は kling)。台本があれば `script.md` に貼る。

## 2. 参考動画を読む(あれば)

1. 動画を `refs/video/` にコピーし、`analyze refs/video/<file> --out refs/video/<name>/` を実行する。
2. 結果の読み方:
   - `analysis.json` → カット数、平均カット長、1分あたりのカット数、各カットの長さ、音量、無音区間
   - `overview.jpg` → 全カットの中央のコマを並べた一覧。まずこれを Read で見る。
   - `cut-NN.jpg` → 各カットの最初・中央・最後の3コマ。変化を見て、カメラの動きを判断する(寄る、引く、横に流れる、固定)。
   - `waveform.png` → 音の盛り上がり
3. 読み取ったことを、日本語の表でユーザーに見せる。

   | 観点 | 読み取ったこと |
   | --- | --- |
   | カット割り | 例: 8カット、平均1.9秒、後半ほど短い |
   | 構図 | 例: 寄りが多く、人物はほぼ中央 |
   | カメラ | 例: 手持ちのゆっくりした寄り、パンが2回 |
   | 光・色 | 例: 逆光、暖色、コントラストは低め |
   | テンポ | 例: 音楽の拍に合わせてカットが切り替わる |
   | 音 | 例: 前半は静か、cut 5 で盛り上がる(波形より) |

   - 音の中身(セリフの言葉、曲名)は聞き取れない。分かるのは音量の変化だけなので、ユーザーに確認する。
4. 「どこを借りたいか」を AskUserQuestion の複数選択で聞く(カット割りのリズム / カメラワーク / 光と色 / 構図 / 全部)。
5. 借りる箇所は、各カットの `ref_video`(file、start、end、borrow_ja)に記録する。

## 3. カット割り

1. 台本・聞き取り・参考動画をもとに、カットの一覧を作る。各カットは `id`、`scene`、`duration`、`summary_ja` の1行。
2. 一覧を表で見せて確認をもらう。`cuts.json` に書いたら、ステップ6の手順で Artifact にも出す(以後、絵コンテが変わるたびに更新する)。直す点があれば直してから進む。
3. **scene のまとめ方**: scene は動画を1回生成する単位で、同じ scene のカットは1本の動画にまとめて生成される。
   - 尺の上限: Kling 3.0 は3〜15秒、Seedance 2.0 は4〜15秒。
   - 同じ場所で続くカット、カメラが途切れないカットは、同じ scene にまとめる。
   - 場所や時間が飛ぶところで scene を分ける。
   - scene の名前は `s01-<英小文字の短い名前>` にする。

## 4. 1カットずつ組み立てる

カットごとに、AskUserQuestion で次の4問を聞く。各問の選択肢は2〜4個。参考動画や前後のカットから考えた推奨案を最初に置き、「(推奨)」と付ける。

| 問 | 選択肢の例 |
| --- | --- |
| 構図 | ショットサイズ(EWS / WS / FS / MS / MCU / CU / ECU / OTS / POV)× アングル(目線 / ローアングル / ハイアングル / 真上 / ダッチ) |
| カメラ | 固定 / ゆっくり寄る / 引く / パン / ティルト / 横移動 / 追いかける / クレーン / 手持ち / 回り込み |
| ライティング | 時間帯 × 光の方向(順光 / 逆光 / サイド / トップ)× 質(柔らかい / 硬い)× 色温度 |
| 音 | BGM / 環境音 / 効果音 / セリフ(言語・話し方)の組み合わせ |

そのあと、テンポ(速さ、どこで止めるか、次のカットへのつなぎ: cut / dissolve / match cut / whip pan)と尺を1問で確認する。

答えを `cuts.json` の該当カットに書き込む。日本語(`ja`)と英語(`en`)の両方を書く。

- 英語はプロンプトにそのまま使う。subject の見た目は、全カットで一字一句同じにする。
- `setting.en` は前置詞から書き始める(`by the window of ...`、`in a ...`)。
- カメラの動きは1カットにつき1つ。
- 感情は形容詞ではなく、体の動きで書く。
- 書き終えたら、`sb check <project>` で抜けがないか確認する。

## 5. コマ画像

各カットに1枚、絵コンテの画を付ける。1カット1枚の独立した画像にする(Seedance 2.5 の公式ガイドでは、複数コマを1枚にまとめた画像より、コマごとの画像のほうが映像の一致度が高い)。

1. **生成する**(既定は Codex)
   1. `frame_prompt`(英語の静止画の説明)を書き、`sb frame <project> <cut> --dry-run` で送る内容を確認する。
   2. `sb frame <project> <cut> [--provider codex|seedream|gemini]` を実行する。1枚1分ほどかかるので、Bash の `run_in_background` で実行する。複数カットは並べて同時に実行してよい。
   3. キャラクターの参考画像(`refs`)があれば一緒に送られる。

   | provider | 料金 | 必要なもの |
   | --- | --- | --- |
   | `openai` | GPT Image 2。中画質で約$0.04/枚(低画質は約$0.005)。修正時は入力画像の分が少し加算 | `OPENAI_API_KEY` |
   | `codex`(既定) | ChatGPTのプランの利用枠内(画像生成は枠の減りが速い)。1枚約50秒 | `codex` CLI にログイン済みであること |
   | `seedream` | 約$0.018/枚(Seedream 5.0 flash) | `ARK_API_KEY` |
   | `gemini` | 約$0.034/枚(Nano Banana 2.1、1K) | `GEMINI_API_KEY` |

   - 有料の provider を使うときは、料金を伝えてOKをもらってから実行する。
   - codex で失敗したら、エラーを見せたうえで seedream か gemini を提案する。
2. **参考動画から取る**: `sb grab <project> <cut> <video> <秒>`
3. **ユーザーの画像を使う**: `storyboard/frames/` にコピーし、`frame` にパスを書く。

4. **一部を直す(範囲選択修正)**: ユーザーがチャットで「c03 の右上の空に気球を足して」のように言ったら、次の手順で直す。
   1. 画像を Read で見て、直す範囲を画像に対する%の四角(左上x, 左上y, 幅, 高さ)で決める。例: 右上なら `60,5,35,35`。
   2. `sb edit <project> <cut> --prompt "<英語の修正指示>" --box x,y,w,h --reason "<ユーザーの要望を日本語で>"` を実行する。
      - 範囲を決めない全体の修正は `--box` を付けない。
      - 見た目を揃えたい画像があれば `--ref refs/x.png` を付ける。
   3. できた画像を Read で見て確認し、Artifact を更新する。
   - 範囲指定がきちんと効くのは `openai`(GPT Image)だけ。ほかの provider は、マスクをヒントとして渡し、画像全体を描き直す。
   - 修正のたびに新しい版(`cNN-vK.png`)ができ、`frame_history` に方法・指示・範囲・元画像・理由が残る。`storyboard/log.md` にも記録される。
   - 前の版に戻すときは、`cuts.json` の `frame` を `frame_history` にある前のファイルに書き換える。
   - ユーザーが「自分で塗って直したい」と言ったときだけ、`sb editor <project>` を Bash の `run_in_background` で実行する。ブラウザで範囲を塗って修正でき、終わったら Claude は `cuts.json` を読み直す。

- できた画像は Read で見て、構図・光・キャラクターの見た目が意図どおりか確認する。違えば `frame_prompt` を直して作り直す(以前の画像は `cNN-vK` の連番で残る)。
- 作り直すのは問題のあるカットだけにする。全カットを作り直さない。
- `use_frame_as_first_frame: true` にすると、その画が動画の先頭フレームとして使われる。

## 6. 絵コンテを見せる(Artifact)

カット割りが決まったとき・画像ができたとき・直したとき・アニマティックを作ったときに、毎回この手順で見せる。

1. `sb render <project>` を実行する。出力されるJSONは次のとおり。
   - `file_path`: ページ本体
   - `files`: 画像と動画の対応表
   - `url`: 前に公開したページのURL(なければ null)
   - `description`: ページの説明
2. Artifact ツールで公開する(Artifact のページづくりの決まりは、このスクリプトが出すページで満たしている)。
   - 渡すもの: `file_path`、`files`(出力の `files` をそのまま)、`description`
   - 初回だけ `icon: "film"` を付ける。
   - `url` があるときは `url` も付けて、同じページを更新する。
3. 初回の公開後に `sb set-url <project> <公開されたURL>` を実行する。次の会話からも同じページを更新できる。
4. ユーザーにはリンクを1行で伝える。直したいことはチャットで言ってもらう。
   - ページのコメント機能でも受け付けられる(ArtifactComments で読む)。
5. Artifact ツールがない環境では、`sb render <project> --open` で、同じページをブラウザで開く(サーバーは立てない)。

- 公開したページは、本人にしか見えない。家族などに見せたいときは、ページ右上の「共有」から相手を追加してもらう。

## 7. アニマティックで確認

ユーザーが「流れを見たい」「再生して」「アニマティック」と言ったら、次を実行する。

1. `sb animatic <project>` を実行する。
   - 仮の音声を作り、MP4(静止画・カメラの動き・仮音声・字幕)を作って、Mac の動画プレーヤーで開く。
   - 画面に出るのは動画だけ。操作は再生・一時停止のみ。
2. 仮の音声のしくみ: セリフ(`audio.dialogue`)とナレーション(`narration_ja`)を、macOS の `say` で読み上げる。
   - 話者ごとの声は `project.voices`(例: `{"Aya": "Kyoko", "default": "Kyoko"}`)。
   - 速さは `project.voice_rate`(既定180)。
   - 音声がカットの尺より長いと出力に「! longer than the cut」と出るので、尺を延ばすかセリフを削るよう提案する。
3. 見終わったら、尺・セリフ・順番の直しをチャットで聞き、`cuts.json` を直す。直したら `storyboard/log.md` に1行追記する(日時・対象カット・変更・理由)。
4. もう一度 `sb animatic` を実行し、Artifact も更新する(ページの一番上に、最新のアニマティックが載る)。
5. 全カットを1枚の画像にしたいときは `sb sheet <project>` → `storyboard/sheet.png`。

- 流れが確定したと言われたら、ステップ8に進む。

## 8. プロンプトに変換

1. `sb to-prompts <project>` を実行する。scene ごとに `scenes/<scene>/prompts/vNNN.md` ができる。
   - 新しい scene は v001 になる。
   - プロンプトが変わった scene だけ、新しいバージョンになる。
   - 一部の scene だけ変換するときは `--scenes s01,s03` を付ける。
   - 修正根拠は `--reason "c03: 俯瞰の入りをクレーンアップに(参考動画 cut 3)"` で付ける。
2. 書式は provider に合わせて自動で変わる。
   - 複数カットの scene: Kling は `shot 1, 5, ...;` + `multi_shot: true`、Seedance は `Shot 1: ...`、Omni は `[0-5s] ...`
   - セリフ: Seedance は `{...}`、Kling と Omni は `"..."`
3. 機械的につないだ文章なので、仕上げとして video-prompt スキルのステップ3の方針で英語を整える。直した場合は、改訂として扱う。
4. 生成以降(dry-run → 料金確認 → render → 評価 → 改訂)は video-prompt スキルに従う。
