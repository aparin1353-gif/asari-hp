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

## 未検証であることの明示

`builder/build_drift.py` は **TouchDesigner 実機で実行していない**（この環境に TD が無いため）。
構文は検証済みだが、オペレータのパラメータ名は未確認のものを含む。
初回実行時は `setpar()` が名前の誤りを例外で教えるので、`docs` で正式名を引いて直すこと。
これは運用メモの絶対ルール3（パラメータ名を記憶で書かない）に対する、
「書いてしまった側」からの安全装置として設計してある。
