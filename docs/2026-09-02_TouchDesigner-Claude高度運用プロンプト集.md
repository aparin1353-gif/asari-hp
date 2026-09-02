# TouchDesigner × Claude Code 高度運用プロンプト集

作成: 2026-09-02 / 対象: 浅利さんの個人PC（Windows）
用途: ネット上の作品を参照し、構造を分析して TouchDesigner で再現するまでを Claude Code に回させる

---

## 0. 設計の前提（なぜこの構成にするか）

### 0-1. 構成の全体像

```
[参考作品URL]
  │ ① フレーム化（ブラウザSS or ffmpeg）※Claudeは動画を直接視聴できない
  ▼
[静止画 3〜6枚 + 連続2枚]
  │ ② 構造分析 → analysis/YYYY-MM-DD_作品名.md（実装しない、分析だけ）
  ▼
[再現レシピ（オペレータ構成の設計図）]
  │ ③ builder/build_*.py を書く → MCP経由でTD内で実行
  ▼
[TouchDesigner上に実体のネットワーク]
  │ ④ observe（PNG/GIF）で自分の出力を撮る → 参考フレームと並べて差分評価 → 修正（収束ループ）
  ▼
[完成 .toe + build script + 分析メモ]
```

### 0-2. 3つの原則

**1. ソースはPython、.toeは出力**
ネットワークは `builder/build_*.py` が構築する。`.toe` はその実行結果。
→ 破ると: `.toe` はバイナリでgit差分が取れない。壊れたら復元不能・Claudeが大胆に試せない。

**2. 検証は画像で閉じる**
Claudeが `observe` で自分の出力を撮り、参考フレームと比較して自己修正する。
→ 破ると: 「多分できました」で終わる。人間が毎回目視で差し戻す羽目になる。

**3. 分析と実装を分ける**
②で分析シートを確定させてから③に入る。
→ 破ると: 序盤の誤読（例: フィードバックをパーティクルと誤認）を最後まで引きずる。

### 0-3. MCPサーバーの選定

**推奨: johnsabath/touchdesigner-mcp**
https://github.com/johnsabath/touchdesigner-mcp

`.tox` をプロジェクトにドラッグするだけ（port 9988）、TouchDesigner 2024+、外部依存なし。
決定的なのは以下3つのツールを持っていること。これがないと自己検証ループが閉じない。

- `observe` … 現在の出力を PNG または アニメーションGIF でキャプチャ
- `render` … TDネイティブ録画で MP4 出力
- `docs` … 任意のオペレータ型のパラメータ・メニュー・デフォルト・コネクタを引ける（＝Claudeの記憶違いを実機で正せる）

他に `run`（Python実行）/ `create`（位置・パラメータ・結線を一括指定して生成）/ `wire`（結線とパラメータ式のバッチ）/ `inspect` / `list` / `map`（ネットワークをテキスト地図化）/ `read`・`write`・`edit`（Text DAT操作）/ `set`。

**代替: 8beeeaaat/touchdesigner-mcp**
https://github.com/8beeeaaat/touchdesigner-mcp

npm配布（`npx -y touchdesigner-mcp-server --stdio`）でDockerのHTTP transportもある。`get_td_classes` / `get_td_class_details` / `get_td_module_help` でTDのPython APIを引けるのが強み。画像は `get_top_image`。GIF・MP4は持たない。
→ 両方入れて併用が最善（johnsabathで作って検証、8beeeaaatでAPI照会）。

**最小構成: Derivative公式コミュニティの.tox版**
https://derivative.ca/community-post/asset/simple-mcp-server-tox-connect-claude-and-touchdesigner/74528

`.tox` をドロップして「Install / Update Claude Desktop」ボタン一発。まず動かしたいだけならこれ。

### 0-4. Claudeができないこと ＝ 最初に潰す制約

- **動画URLを渡されても再生して見ることはできない**
  → 静止画に落とす。①ブラウザで再生ページを開き任意の秒でスクリーンショット（DLしない） ②手元の動画なら ffmpeg でフレーム抽出 → 画像ファイルとして読む

- **音の解析（オーディオリアクティブ作品の駆動源特定）**
  → 波形・スペクトログラムを画像化して渡す（`ffmpeg -lavfi showspectrumpic`）。または「音は後で自分で繋ぐ」と割り切り、まず LFO CHOP で代替駆動する

- **リアルタイムの体感（気持ちよさ・本番照明での見え方）**
  → 最後は自分の目で見る。Claudeは「静止画の一致度」までしか保証できない

- **GPU実測負荷**
  → Perform CHOP の値をClaudeに読ませて数値で判断させる（プロンプト⑤）

---

## 1. 初回セットアップ（1回だけ）

### 1-1. 個人PC側で手を動かす部分

```
winget install Gyan.FFmpeg
```

TouchDesigner 本体（https://derivative.ca/download ）と Claude Code は先に入れておく。
Non-Commercialライセンスだと出力解像度が 1280×1280 に制限される。再現の検証はこれで足りるが、納品時は要注意。

作業ディレクトリを切る（個人PC側、例）:

```
mkdir -p ~/td-lab/builder ~/td-lab/analysis ~/td-lab/reference ~/td-lab/capture ~/td-lab/out
```

- `reference/` … 参考作品のフレーム画像（作品ごとにサブフォルダ）
- `analysis/` … 構造分析シート（Markdown）
- `builder/` … ネットワークを構築するPythonスクリプト ★これが正
- `capture/` … Claudeが observe で撮った自分の出力
- `out/` … 完成 .toe / 書き出し動画

```
cd ~/td-lab && git init
```

`.gitignore` に `out/` と `capture/` を入れる（生成物なので）。

### 1-2. プロンプト① 環境セットアップ

--- ここからコピペ ---

TouchDesigner を Claude Code から操作できる環境を、この `~/td-lab` に構築してほしい。

1. johnsabath/touchdesigner-mcp の README を読み、`td_mcp_server.tox` の入手と設置手順を私向けに具体化して提示して。私がTouchDesigner上で手を動かす必要がある操作は、クリックする場所まで書いて。
2. MCPクライアント側の設定（http://localhost:9988/mcp への接続）をこのプロジェクトの `.mcp.json` に書いて。
3. 接続できたら `list` と `docs` を実際に叩いて、疎通と TouchDesigner のバージョンを確認して報告して。
4. 疎通が確認できたら、`builder/build_smoke_test.py` を書いて実行し、「Noise TOP → Level TOP → Out TOP」の最小ネットワークを生成、`observe` でPNGを撮って `capture/` に保存して。画像を見て、ノイズが出ていることを自分で確認してから完了報告して。

途中でMCPサーバーがエラーを返したら、サーバー側のスクリプトを読んで原因を特定してから直して。私に「もう一度試してください」とだけ言うのは禁止。

--- ここまで ---

---

## 2. 常設ファイル: プロジェクト直下の CLAUDE.md

これが一番効く。以下を `~/td-lab/CLAUDE.md` として置くと、毎回のプロンプトが短くて済む。

--- ここからコピペ ---

# td-lab ／ TouchDesigner 再現ラボ

参考作品を構造分析し、TouchDesignerで再現する個人プロジェクト。Claude Codeから操作する。

## 絶対ルール

1. **ネットワークはPythonスクリプトで構築する。** 手作業前提の指示を私に投げない。
   すべて `builder/build_<作品名>.py` に書き、MCPの `run` で実行する。`.toe` はその出力物。
2. **作ったら必ず `observe` で自分の出力を見る。** 画像を確認せずに「完成しました」と言わない。
3. **パラメータ名を記憶で書かない。** `docs` で対象オペレータの正式パラメータ名を引いてから書く。
4. **エラーは `inspect` で読む。** ノードが赤い/黄色い状態のまま完了報告しない。
5. **分析と実装を混ぜない。** 分析フェーズでは `create` を一切呼ばない。

## ネットワークの作法（TouchDesigner側の規律）

- **ノードを重ねない。** X間隔160px以上、Y間隔120px以上を確保する。
- **信号は左→右に流す。** 入力 → 処理 → 出力。フィードバックの戻り線だけが例外で、これは1段下の行に落として引く。
- **命名は 役割_連番。** `noise_base`, `fb_loop`, `post_bloom` のように、型名の連番（`noise1`）を残さない。
- **系統ごとにコンテナで囲う。** `/project1/BASE`, `/project1/MOTION`, `/project1/POST` のように分ける。
  1コンテナ内のノードが20個を超えたら分割を検討する。
- **マジックナンバーを直書きしない。** 調整したい値は親コンテナのカスタムパラメータに出し、
  子は `parent().par.Xxx` で参照する。再現の微調整はここだけ触れば済む状態にする。

## オペレータ選択の方針

- GPUで済むものはGPUで（TOP/POPを優先、CHOPでピクセル処理をしない）
- 同じ絵が Feedback TOP でも Instancing でも作れる場合、まずFeedbackで試す（軽く、パラメータが少ない）
- GLSL TOPは「他の手段で作れないと確認できてから」使う（読めない資産になるため）

## 検証の作法

- `observe` のPNGは `capture/<作品名>_<試行番号>.png` に保存する
- 参考フレームと自分の出力を比較するときは、**測れるもので比較する**（下記4指標）。「雰囲気が近い」は評価に使わない
  1. 主要色（16進で3〜5色）
  2. 要素の粒度（画面幅に対する主要要素のサイズ比）
  3. 動きの周期（秒）と方向
  4. 明暗のコントラスト幅
- 収束したら `builder/` をcommitする。コミットメッセージは日本語1行

## やらないこと

- `git push` はしない（ローカル完結）
- ファイル名に `_v2` `_v3` を付けない。上書きしてgitで履歴を残す
- 参考作品の動画・音源をダウンロードして再配布しない

--- ここまで ---

---

## 3. プロンプト② 構造分析（URLを渡す段）

このプロンプトが本体。ここの精度が再現の成否をほぼ決める。

--- ここからコピペ ---

参考作品を構造分析してほしい。この段階では TouchDesigner に一切触らないこと（`create` / `run` を呼ばない）。分析シートを作るまでが仕事。

参考URL: `<ここにURLを貼る>`

### Step 1: フレーム化

ブラウザでそのページを開き、以下のタイミングでスクリーンショットを撮って `reference/<作品名>/` に保存して。

- 冒頭・中盤・終盤の3枚（構成が変わる作品なら変化点ごとに追加、最大6枚）
- 動きが激しい箇所で「約1秒差の連続2枚」（これで動きの向きと速さを推定する）

動画をダウンロードせず、再生ページ上のスクリーンショットで済ませて。
手元に動画ファイルがある場合は ffmpeg でフレーム抽出してよい。

### Step 2: 観察（推測を混ぜない）

撮った画像を実際に開いて見て、見えている事実だけを書き出して。
何色があるか（16進で）、要素は何個くらいあるか、輪郭は硬いか柔らかいか、
前後に重なりがあるか、画面のどこが動いてどこが止まっているか。
この段階でオペレータ名を出さないこと。

### Step 3: 7層分解

観察をもとに、以下7層それぞれについて「何が使われていると思われるか」を候補2つまで挙げ、
その画像上の根拠（どこを見てそう判断したか）を必ず添えて。

1. **出力形式** … 2D合成か3Dレンダか粒子か
   → TOP合成 / SOP+Render TOP / POP・particlesGPU / ボリューム
2. **素の生成源** … 一番最初の絵は何から生まれているか
   → Noise TOP / Ramp / Movie File In / Text / SOPジオメトリ / GLSL
3. **時間の駆動** … 何が動きを作っているか
   → LFO CHOP / absTime.seconds / Timer / Audio / Speed CHOP / フィードバックの自励
4. **変形の主役** … 形が崩される仕組み
   → Displace TOP / Transform+Feedback / Optical Flow / Time Machine(スリットスキャン) / Remap / Limit
5. **反復・増殖** … 要素が増えている仕組み
   → Feedback TOP ループ / Instancing / Copy SOP / Cache TOP
6. **色** … 色はどう付いているか
   → Ramp+Lookup TOP / HSV Adjust / Level / ソース元の色そのまま
7. **後処理** … 最後に何を足しているか
   → Bloom / Blur / Chroma収差 / Grain / Vignette / Composite blend mode

### Step 4: 再現レシピ

7層分解から、実際に組むオペレータ構成を「左→右の系統図」として書いて。
コンテナ分割（BASE / MOTION / POST）と、親コンテナに出すカスタムパラメータの一覧も含めて。

### Step 5: 難所と代替案

再現が難しいと思われる箇所を、難しい理由つきで挙げて。それぞれに「妥協案」を1つ添えて。
GLSLが必要そうな箇所は特に明示して。

### Step 6: 収束基準

「再現できた」と判断する条件を、CLAUDE.mdの4指標（主要色・粒度・動きの周期と方向・コントラスト幅）で
具体的な数値・許容範囲として定義して。

### 出力

`analysis/YYYY-MM-DD_<作品名>.md` に上記Step2〜6をまとめて保存。
推測は「〜と思われる」と明示し、断定と区別して。分からない層は「不明」と書いて、埋めるために何を追加で観察すべきかを書いて。

--- ここまで ---

---

## 4. プロンプト③ 再現ビルド

--- ここからコピペ ---

`analysis/YYYY-MM-DD_<作品名>.md` の再現レシピを実装してほしい。

1. **先に `docs` を叩く。** レシピに出てくるオペレータ型すべてについて、正式なパラメータ名とデフォルト値・コネクタ構成を確認して。記憶で書いたパラメータ名は使わない。
2. `builder/build_<作品名>.py` を書く。CLAUDE.mdのネットワーク作法（重ねない・左→右・命名・コンテナ分割・カスタムパラメータ化）を守って。
   冒頭に「既存の同名コンテナがあれば削除してから作る」冪等処理を入れて、何度でも作り直せるようにして。
3. **7層を一度に作らない。** 層ごとに 実行 → `observe` → 画像確認 を回して。
   ①②（素の生成）→ ③④（動き）→ ⑤（反復）→ ⑥（色）→ ⑦（後処理）の順。
   各段で `inspect` してエラーがゼロであることを確認してから次に進む。
4. 各段の `observe` 画像を `capture/<作品名>_step<N>.png` に保存し、その画像を実際に見て「意図した絵になっているか」を1〜2行で報告して。なっていなければ次に進まず直して。
5. 全層を通したら `capture/<作品名>_v1.png` と、動きを見るための2秒GIFを撮って完了報告。

途中で「レシピの前提が間違っている」と判明したら、勝手に作り替えず私に報告して分析シートを更新してから続けて。

--- ここまで ---

---

## 5. プロンプト④ 収束ループ（ここが差を詰める段）

--- ここからコピペ ---

再現の精度を上げたい。以下を指標が収束するか、3周しても改善しなくなるまで繰り返して。

各周でやること:

1. `reference/<作品名>/` の参考フレームと `capture/<作品名>_v<N>.png` を両方開いて見る
2. 分析シートの収束基準4指標について、**参考値／現状値／差** を表にする
   （主要色は16進で、粒度は画面幅比で、動きは周期の秒数で、コントラストは明暗の幅で）
3. **差が最も大きい1指標だけを選ぶ。同時に複数直さない**
4. その指標を詰めるために触るパラメータを1〜3個に絞り、理由を書いてから `builder/` を修正して再実行
5. `observe` して `capture/<作品名>_v<N+1>.png` に保存、指標を再測定

各周を「周回N: 直した指標 / 触ったパラメータ / 結果（改善・悪化・変化なし）」の1行ログで
`analysis/YYYY-MM-DD_<作品名>.md` の末尾に追記して。

悪化した場合は前の値に戻して、その組み合わせを「試して駄目だったこと」として記録して。
3周して改善しなくなったら、「構造レベルの誤読が残っている可能性」として、
7層のどこが怪しいかを挙げて私に相談して。**パラメータの微調整で粘らない。**

--- ここまで ---

---

## 6. プロンプト⑤ 最適化・仕上げ

--- ここからコピペ ---

完成したプロジェクトを実用状態に持っていってほしい。

1. **負荷計測:** Perform CHOP を置いて `run` でフレームレートとGPU時間を読み、数値で報告して。60fpsを割っている場合、`map` でネットワーク全体を見渡して重い系統を特定し、解像度・Feedbackの段数・インスタンス数のどこを削るのが影響最小か、理由つきで提案して。
2. **操作系の整理:** 親コンテナのカスタムパラメータを、実際に触る順に並べ替えて。使っていないパラメータは消して。
3. **書き出し:** `render` で10秒のMP4を `out/` に出して。
4. **記録:** `builder/build_<作品名>.py` の冒頭コメントに、この作品で使った技法の要約（7層分解の結論）を書いて、後で他の作品に流用できる状態にして。
5. git commit（日本語1行メッセージ）。`out/` と `capture/` は含めない。

--- ここまで ---

---

## 7. 運用上の注意

### 7-1. 著作権・利用規約

- 再現の学習は問題ないが、成果物の扱いは別。特定作品の模倣を自作として公開・商用利用するのは避ける。技法の習得と、作品としての発表は分けて考える。
- 動画のダウンロードはプラットフォームの利用規約に触れる場合がある（YouTube等）。プロンプト②は再生ページのスクリーンショットを既定にしてあり、ダウンロードを前提にしていない。
- 参考作品の動画・音源そのものをリポジトリにコミットしない（`reference/` はスクリーンショットのみ）。

### 7-2. トークン消費

構造分析は画像を複数枚読むので消費が大きい。フレームは6枚を上限にし、収束ループは「毎周で参考フレーム全部を読み直さない」（差が出ている1枚に絞る）と効率が良い。

### 7-3. うまくいかないときの切り分け

| 症状 | 疑うべき原因 |
|---|---|
| ノードが生成されるが絵が出ない | `inspect` でエラー確認 → 結線の向き（`to.inputConnectors[0].connect(from)`）と、Out TOPまで繋がっているか |
| パラメータ設定が無視される | パラメータ名の記憶違い。`docs` で正式名を引く。メニュー型パラメータは文字列ではなくインデックス指定が必要な場合がある |
| 絵は近いが動きが違う | ③時間の駆動層の誤読。連続2フレームを撮り直して動きベクトルから再推定させる |
| 何周回しても近づかない | ①出力形式か⑤反復層の誤読（例: Feedbackなのにインスタンシングで作っている）。パラメータ調整では埋まらないので構造から作り直す |

### 7-4. 段階的に導入する順番

1. まずプロンプト①だけ通す（疎通とノイズ1枚が出れば成功）
2. 次に簡単な作品でプロンプト②③を回す（推奨: 単純なフィードバック系の抽象アニメーション。パーティクル大量系や3D系は最初に選ばない）
3. ④の収束ループの感覚を掴んでから、複雑な作品に上げる

---

## 8. 出典

- **johnsabath/touchdesigner-mcp** … 推奨MCPサーバー（ツール一覧・要件はREADME記載）
  https://github.com/johnsabath/touchdesigner-mcp
- **8beeeaaat/touchdesigner-mcp** … 代替MCPサーバー（13ツール、npm配布）
  https://github.com/8beeeaaat/touchdesigner-mcp
- **Simple MCP Server .tox to connect Claude and TouchDesigner | Derivative** … 公式コミュニティの最小構成
  https://derivative.ca/community-post/asset/simple-mcp-server-tox-connect-claude-and-touchdesigner/74528
- **Claude Code + MCP_server + Touchdesigner (the easy way) | Derivative** … 「ノードを重ねない」「左→右に流す」等の指示は本記事の知見を反映
  https://derivative.ca/community-post/asset/claude-code-mcpserver-touchdesigner-easy-way/74168
- **Connector Class | Derivative** … 結線のPython API（`to.inputConnectors[0].connect(from)`）
  https://derivative.ca/UserGuide/Connector_Class
- **Slit Scan Effect + Time displacement | AllTouchDesigner** … 7層分解④の技法例
  https://alltd.org/slit-scan-effect-time-displacement-touchdesigner-tutorial/
- **Feedback Particles | elekktronaut** … 7層分解⑤の技法例
  https://www.elekktronaut.com/tutorials/feedback-particles
- **GPU Particle Systems | Introduction to TouchDesigner** … GLSL粒子系の判断材料
  https://nvoid.gitbooks.io/introduction-to-touchdesigner/content/GLSL/12-7-GPU-Particle-Systems.html
