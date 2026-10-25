---
name: tutorial
description: はじめての人と一緒に、10秒の動画を1本作るチュートリアル。テーマを選ぶだけで、絵コンテ(2カット×5秒)→ コマ画像 → 仮の音声つき再生(アニマティック)→ AIで動画にする、までを15分ほどで一通り体験できる。動画用の合言葉(APIキー)がなければ、無料の仮動画(MP4)で終える。「チュートリアル」「最初の動画を作りたい」「試しに1本作りたい」「使い方を体験したい」などのときや、setup が終わった直後に使う。
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/tutorial.py" *) Bash(python3 "${CLAUDE_SKILL_DIR}/../setup/scripts/doctor.py" check) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" check *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" tts *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" animatic *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" render *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" set-url *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" export *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" sheet *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" to-prompts *) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" frame * --provider codex) Bash(python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py" frame * --dry-run) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" render * --dry-run) Bash(python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py" status *) Bash(open *)
---

# tutorial: はじめての10秒動画

AIにあまり詳しくない人と、10秒の動画を1本作る。目的は「一通りの流れを体で覚えてもらうこと」。細かい作り込みはしない。話し方は setup スキルと同じにする(専門用語なし、1回に伝えることは少なく、選択は AskUserQuestion)。

**全体の形(固定)**: 2カット × 5秒 = 10秒。2カットとも同じ scene(`s01-first`)にまとめ、**動画の生成は1回だけ**にする。1カット目の画像を動画の最初のコマに使う。

- `tut` = `python3 "${CLAUDE_SKILL_DIR}/scripts/tutorial.py"`
- `sb` = `python3 "${CLAUDE_SKILL_DIR}/../storyboard/scripts/sb.py"`
- `vp` = `python3 "${CLAUDE_SKILL_DIR}/../video-prompt/scripts/vp.py"`
- `doctor` = `python3 "${CLAUDE_SKILL_DIR}/../setup/scripts/doctor.py"`
- すべて作業フォルダ(`projects/` と `.env.local` がある場所)で実行する。
- 段階は「チュートリアル 2/6: 絵コンテ」のように示す。各段階の最後に、**今やったことを1行で**伝える(例: 「これが『絵コンテ』です。動画の設計図にあたります」)。

## 1/6 準備の確認とあいさつ

1. `doctor check` を実行する(結果の表は見せなくてよい)。
   - ffmpeg がない、または作業フォルダができていない → 「先に準備が必要です」と伝え、`/ai-video:setup` を案内して終える。
2. 結果から、次の2つを決めておく(ユーザーには聞かない)。
   - **画像の作り方**: Codex がログイン済み → `codex`(ChatGPTのプランの枠内)。そうでなければ `OPENAI_API_KEY` → `openai`、`ARK_API_KEY` → `seedream`、`GEMINI_API_KEY` → `gemini`。どれもなければ「画像なし」(灰色の画面で進める)。
   - **動画の作り方**: `KLING_API_KEY` → `kling`、`ARK_API_KEY` → `seedance`、`GEMINI_API_KEY` → `omni`。どれもなければ「無料コース」(最後は仮動画のMP4)。
3. 3行で説明する。費用は決めた作り方に合わせて書く。

   > これから、10秒の動画を1本いっしょに作ります。15分ほどです。
   > 流れは「絵コンテ(設計図)→ 画像 → 仮の音声で再生 → AIで動画にする」です。
   > お金がかかるのは最後の動画づくり(約190円)だけで、その前に必ず確認します。

   - 費用の目安(1ドル150円): kling 10秒・音声あり 約$1.26(約190円)、seedance(mini)10秒 約$0.76(約115円)、omni 約$1.0(約150円)。画像は codex なら追加料金なし、openai 2枚 約12円、seedream 約5円、gemini 約10円。
   - 無料コースなら「今回は動画用の合言葉がないので、無料の仮動画まで作ります。合言葉はあとからでも設定できます」と言う。

## 2/6 テーマを選ぶ → 絵コンテ

1. AskUserQuestion で2問を一度に聞く。
   - 「どんな10秒にしますか?」: 日だまりの猫(推奨)/ 朝のコーヒー / 夕暮れの屋上。「Other」で自由に書いてもらってもよい。
   - 「画面の向きは?」: 横長(YouTube・パソコン向け)/ 縦長(スマホ・SNS向け)
2. `tut new --theme <cat|coffee|city> --aspect <16:9|9:16> --provider <動画の作り方。無料コースは kling>` を実行する。出力の `project` がプロジェクト名(以下 `<p>`)。
   - **自由テーマのとき**: `--theme blank` で作り、`projects/<p>/storyboard/cuts.json` の2カットを Claude が書く。書き方は storyboard スキルのステップ4に従う(英語と日本語の両方、subject の英語は2カットで一字一句同じ、カメラの動きは1カット1つ、`frame_prompt` も書く)。1カット目の `narration_ja` に15文字ほどの短いナレーションを入れる。実在の人物・ブランド・作品のキャラクターは避けるよう、やんわり提案する。
3. `sb check <p>` を実行し、次のような表で見せる。

   | カット | 秒 | 内容 | 映し方 |
   | --- | --- | --- | --- |
   | c01 | 5 | 日だまりの窓辺で眠る猫 | 広く・ゆっくり寄る |
   | c02 | 5 | あくびをして伸びをする | アップ・固定 |

4. 「本番では、カットごとに構図・カメラの動き・光・音を一緒に選んで決めます。今回はおまかせで作りました」と添える。
5. `sb render <p>` を実行し、出力の `file_path`・`files`・`description` で Artifact を公開する(初回は `icon: "film"`)。続けて `sb set-url <p> <URL>` を実行する。「絵コンテのページを作りました。画像や動画ができるたびに、このページが更新されます」とリンクを伝える。Artifact ツールがないときは `sb render <p> --open` で開く。
6. AskUserQuestion: 「このまま進めますか?」— このまま進む(推奨)/ 少し変えたい。変えたいと言われたら、要望を聞いて `cuts.json` を直す(1〜2か所まで。大きく変えたいなら、チュートリアル後に storyboard スキルで作ることを勧める)。

## 3/6 コマ画像

「画像なし」のときは、「今回は画像を作らずに進みます(灰色の画面になります)」と伝えて4へ進む。

1. `codex` 以外は有料なので、料金を伝えて AskUserQuestion でOKをもらう。
2. `sb frame <p> c01 --provider <画像の作り方>` と `sb frame <p> c02 --provider <...>` を、Bash の `run_in_background` で**同時に**実行する(1枚1分ほど)。待っている間に「絵コンテの各カットに1枚ずつ、設計図の絵を付けています」と伝える。
3. できた画像を Read で見て、意図どおりか確認してから、`open` で開いて見てもらう。
   - codex で失敗したら、エラーを短く伝え、ほかの作り方があれば料金を伝えて提案する。なければ画像なしで進む。
   - 作り直しは、明らかにおかしいとき(人物の顔が崩れている、別の動物になっている等)に、そのカットだけ1回まで。
4. 「この1枚目の絵が、AIが作る動画の最初のコマになります」と伝える。
5. `sb render <p>` を実行し、Artifact を同じページに更新する(出力の `url` を `url` に渡す)。「絵コンテのページに画像が入りました」と伝える。

## 4/6 仮の音声で再生(アニマティック)

1. `sb animatic <p>` を実行する。仮の音声つきの10秒の動画ができ、Mac の動画プレーヤーで開く。
2. 伝えることは2つだけ。
   - 絵と仮の声をつないだ「動く絵コンテ」です。声はパソコンの読み上げなので、本番の声ではありません。
   - お金をかける前に、ここで流れとテンポを確かめるのがコツです。
3. `sb render <p>` を実行して Artifact を更新する(ページの一番上でも再生できるようになる)。
4. AskUserQuestion: 「流れはこれでよいですか?」— よい(推奨)/ 直したい。直したい場合は、要望(秒数・ナレーションなど)をチャットで聞いて `cuts.json` を直し、もう一度 1 と 3 を行う。尺を変えて合計が10秒からずれても、4〜15秒の範囲ならそのまま進めてよい。

## 5/6 AIで動画にする

### 無料コースのとき

1. 4/6 で作った `storyboard/animatic.mp4` を `open` で開く(なければ `sb animatic <p>`)。
2. 「これが無料版の10秒動画です(絵と仮の音声をつないだもの)」と伝える。
3. 「動画用の合言葉を設定すれば、同じ絵コンテから本物の動画を作れます。`/ai-video:setup` で設定したあと『<p> を動画にして』と話しかけてください」と案内し、6へ進む。

### 合言葉があるとき

1. `sb to-prompts <p>` を実行する。`projects/<p>/scenes/s01-first/prompts/v001.md` ができる。
2. 中身を Read で見て、`## Prompt` を英語のまま全部は見せず、「AIへの指示書(英語)を作りました。中身は、1カット目が〜、2カット目が〜です」と日本語で2行にまとめて伝える。
3. `vp render projects/<p>/scenes/s01-first --dry-run` で送る内容を確認する(Claude が見るだけ。ユーザーには見せない)。
4. AskUserQuestion で確認する。伝えること: サービス名とモデル、長さ10秒、音声あり、**費用の目安**、数分かかること。選択肢: 作る / やめておく(無料の仮動画にする)。
   - やめておく → 無料コースと同じ手順にする。
5. OKなら `vp render projects/<p>/scenes/s01-first` を Bash の `run_in_background` で実行する(この操作は毎回、許可を求める画面が出る。そこで「許可」を押してもらうよう一言添える)。待っている間に、「生成した結果は、指示書の版(v001)とひもづけて保存されます。直すときは新しい版を作るので、前の版に戻れます」と伝える。
6. 終わったら、出力の `video` のパスを `open` で開く。
   - 失敗したら、エラーを短く日本語にして伝える(残高不足・合言葉の誤り・混雑など)。勝手に再実行しない。

## 6/6 まとめ

1. 今日やったことを、作ったファイルと一緒に表で見せる。

   | やったこと | できたもの |
   | --- | --- |
   | 絵コンテ(設計図) | `projects/<p>/storyboard/cuts.json` |
   | コマ画像 | `projects/<p>/storyboard/frames/` |
   | 絵コンテのページ | Artifact(リンク) |
   | 仮の音声で再生 | `projects/<p>/storyboard/animatic.mp4` |
   | AIで動画 | `projects/<p>/scenes/s01-first/renders/v001-r1.mp4`(無料コースは `storyboard/animatic.mp4`) |

2. 次の一歩を2つだけ示す。
   - 直してみる: 「s01 の猫をもっとゆっくり動かして」のように話しかけると、指示書を新しい版にして作り直せる(また費用がかかるので、事前に確認します)。
   - 自分の動画を作る: 「15秒の〇〇の動画の絵コンテを作りたい」と話しかける。今度はカットごとに構図や光を一緒に選ぶ。
3. 困ったときは「うまくいかない」と話しかければよい、と一言添えて終える。
