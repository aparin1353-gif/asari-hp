# td-lab サンプル: `drift`

`../2026-09-02_TouchDesigner-Claude高度運用プロンプト集.md` の運用を、
1本分まるごと通した実例。個人PCの `~/td-lab/` にそのままコピーして使える。

![drift](preview/drift_preview.png)

## 中身

| ファイル | 役割 |
|---|---|
| `builder/build_drift.py` | ★これが正。TouchDesigner のネットワークを構築する。MCP の `run` で実行 |
| `preview/preview_drift.py` | TDを使わずに同じ演算を numpy で再現し、絵とパラメータを先に確定させる |
| `preview/drift_preview.png` / `.gif` | 上の出力。TDに入る前の「目標画像」 |
| `techniques/feedback_drift.md` | §9 の技法カード。この1本から抽出した資産 |

## 使い方

```
# 1. プレビューで絵とパラメータを詰める（PCでもどこでも動く）
pip install numpy pillow
python preview/preview_drift.py

# 2. TouchDesigner に MCP を繋いだうえで、Claude Code に投げる
#    「builder/build_drift.py を run で実行して、observe でPNGを撮って、
#      preview/drift_preview.png と並べて4指標で比較して」
```

## 設計メモ

- パラメータ名は preview と builder で**1:1に揃えてある**。preview で詰めた数値をそのまま TD へ持っていける。
- `builder` 側は `setpar()` を通してパラメータを設定する。**名前が存在しなければ即座に例外で止まる。**
  TouchDesigner はパラメータ名を間違えても黙って無視するため、これが無いと
  「設定したつもりで効いていない」に気づけない（運用メモ §7-3 の2番目）。
- 冒頭で同名コンテナを削除してから作るので、何度実行しても同じ結果になる。

## パラメータ名の検証状況

TouchDesigner 実機での実行は**していない**（作成環境に TD が無いため）。
そのぶんパラメータ名を公式ドキュメントで裏取りし、誤りを4件修正した。

| 項目 | 状況 |
|---|---|
| Feedback TOP の Target TOP = `top` | 確認済（[Feedback TOP](https://docs.derivative.ca/Feedback_TOP)） |
| Level TOP = `blacklevel` / `gamma1` / `opacity` | 確認済（[Level TOP](https://docs.derivative.ca/Level_TOP)） |
| Composite TOP の Operation = `operand` | 確認済（[Composite TOP](https://docs.derivative.ca/Composite_TOP)） |
| Transform TOP の Extend = `extend`（hold/zero/repeat/mirror） | 確認済（[Transform TOP](https://docs.derivative.ca/Transform_TOP)） |
| Ramp TOP の `type` に radial がある | 確認済（[Ramp TOP](https://docs.derivative.ca/Ramp_TOP)） |
| Script TOP の Callbacks DAT = `callbacks` | 確認済（[Script TOP](https://docs.derivative.ca/Script_TOP)） |
| **Transform TOP の Scale は `scale1` ではなく `s1`/`s2`** | ★修正済 |
| **Noise TOP の Monochrome は `monochrome` ではなく `mono`** | ★修正済 |
| **`resolutionw/h` は `outputresolution` を custom にしないと効かない** | ★修正済（`set_res()` に集約） |
| **Transform TOP の rotate に `absTime.frame` を掛けていた** | ★修正済（下記） |
| Blur TOP の Filter Size = `size` | 未確認。初回実行時に `setpar()` が落ちたら `docs` で引く |
| メニュー型パラメータを文字列で設定できるか | 未確認（運用メモ §7-3 の2番目。索引指定が要る場合がある） |

### 修正のうち1件は名前ではなく論理の誤り

`xform_drift` の rotate に `Driftrot * absTime.frame` を書いていた。
**回転角の蓄積はフィードバックループ自身がやっている**ので、ここで時間を掛けると
二重に積まれ、フレームが進むほど回転が加速して絵が崩れる。正しくは
1フレームあたりの角度＝定数 `Driftrot`。preview 側の `warp(state, DRIFTROT, ...)` が
毎フレーム同じ角度を適用しているのと揃った。

preview と builder でパラメータ名を1:1に揃えてあるのは、この種のズレを
見つけやすくするため。片方だけ見ていたら気づけなかった。
