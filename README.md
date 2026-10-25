# AI動画スタジオ(Claude プラグイン)

Claude に話しかけるだけで、動画の **絵コンテ → 仮の音声つきで再生(アニマティック)→ AIで動画にする** までを進められるプラグインです。Mac 専用です。

- 絵コンテ: カットごとに、画像・構図・カメラの動き・光・テンポ・音声を、質問に答えながら組み立てます。参考にしたい動画を渡すと、カット割りや雰囲気を読み取ります。
- アニマティック: 絵コンテを、Mac の読み上げ音声と字幕つきでブラウザで再生します。尺やセリフはその場で直せます。
- 画像づくり: GPT Image(ChatGPT Images)などで絵コンテの画像を作ります。直したい範囲を塗って、そこだけ直すこともできます。
- 動画づくり: Kling / Seedance / Gemini で動画にします。お金がかかる操作は、必ず先に確認します。
- 修正の記録: プロンプトや画像を直すたびに版を残し、なぜ直したかも記録します。

## はじめかた(5分)

### 1. Claude デスクトップアプリを用意する

[Claude デスクトップアプリ](https://claude.ai/download)を入れて、ログインします。左上の「Code」タブを使います。

### 2. 動画用のフォルダを開く

「ムービー」の中に「AI動画」などのフォルダを作り、Code タブでそのフォルダを開きます。

### 3. プラグインを入れる

Code タブの入力欄に、次の2行を1行ずつ入力して送信します。

```
/plugin marketplace add matsuyama-k1/ai-video-studio
/plugin install ai-video@ai-video-studio
```

(入力欄の左の「+」→「プラグインを追加」からも入れられます。)

### 4. 準備をする

入力欄に次のように入力して送信します。

```
/ai-video:setup
```

あとは Claude が順番に案内します。必要な部品(ffmpeg)のインストール、APIキー(サービスを使うための合言葉)の設定、サンプルの再生まで進みます。

## 使い方

話しかけるだけです。

| やりたいこと | 話しかけ方の例 |
| --- | --- |
| 絵コンテを作る | 「15秒の〇〇の動画の絵コンテを作りたい」 |
| 参考動画をまねる | 「この動画みたいにしたい」+ 動画ファイルをドラッグ |
| 仮の音声つきで再生する | 「アニマティックで再生して」 |
| 画像の一部を直す | 「c02 の画像を直したい」 |
| 動画にする | 「プロンプトにして Kling で生成して」 |
| 生成した動画を直す | 「s02 の笑顔が硬いので直して」 |
| 調子が悪い・準備をやり直す | 「/ai-video:setup」 |

## 費用の目安(1ドル150円で計算)

| 内容 | 目安 |
| --- | --- |
| 絵コンテ・アニマティック | 無料 |
| 画像1枚(GPT Image) | 約1〜6円 |
| 動画5秒(Kling 3.0) | 約65〜95円 |
| 動画5秒(Seedance 2.0) | 約60〜115円 |

各サービスの料金は変わることがあります。最新の料金は各社のページで確認してください。

## アップデート

`/plugin` → 「Marketplaces」→ `ai-video-studio` →「Enable auto-update」で、自動で更新されます。

---

## 開発者向け

```
.claude-plugin/marketplace.json      マーケットプレイス(このリポジトリ)
plugins/ai-video/
  .claude-plugin/plugin.json          プラグイン本体(version を上げると配布される)
  skills/setup/                       初期設定(doctor.py)
  skills/storyboard/                  絵コンテ・アニマティック・画像(sb.py, analyze_ref.py, animatic.py, imagegen.py, frames.py)
  skills/video-prompt/                プロンプト管理・動画生成(vp.py, seedance.py, kling.py, omni.py)
.claude/skills/*                      開発用のシンボリックリンク(このフォルダで直接試す用)
```

- 検証: `claude plugin validate ./plugins/ai-video` と `claude plugin validate ./`
- ローカルで試す: `claude --plugin-dir ./plugins/ai-video`
- 配布: `plugin.json` の `version` を上げて push する
- スクリプトは Python 標準ライブラリだけで動きます。ffmpeg は setup が `~/Library/Application Support/AI Video Studio/bin` に入れます。
- APIキーは利用者の作業フォルダの `.env.local` に置きます(`.gitignore` 済み)。
