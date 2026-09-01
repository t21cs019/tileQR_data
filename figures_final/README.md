# figures_final — 発表・論文に使った確定版の図

## figures/ との違い

| | `figures/` | `figures_final/`（ここ） |
|---|---|---|
| 性質 | 探索用・使い捨て | 発表に実際に使った確定版 |
| Git | **管理外**（`.gitignore`） | **コミットする** |
| 再現 | parquet + `figures_src/` から常に作り直せる | 作り直せることを `PROVENANCE.md` で担保する |
| 生成 | `scripts/generate_figures.py` を回すたび大量に出る | 手で選んで置く |

探索用を Git に入れないのは、解析のたびに数十枚が入れ替わり、
履歴が図のバイナリで埋まるため。あちらは入力（parquet）と生成コードが
リポジトリにある限りいつでも復元できるので、成果物を持つ必要がない。

逆にここに置くものは**発表の時点で確定した版**で、あとから
「あのスライドの図はどのデータから作ったか」を辿れないと困る。
だから図そのものと `PROVENANCE.md` の両方をコミットする。

## サブディレクトリ

**発表・成果物の単位**で切る。日付やバージョン番号では切らない
（読み手が探すのは「中間発表で使った図」であって「v3 の図」ではない）。

```
figures_final/
├── 卒論/
│   ├── PROVENANCE.md
│   └── *.png
├── 中間発表/
├── 修論/
└── ゼミ/
```

初期状態では `卒論/` のみ。他は必要になった時点で作る。
新しく作るときは `PROVENANCE.md` を必ず一緒に置く。

## 置くときの手順

1. `scripts/generate_figures.py --outdir figures_final/卒論` で直接出す
   か、`figures_src/fig_*.py --outdir figures_final/卒論` で個別に出す
2. **`PROVENANCE.md` を更新する。** コミットハッシュ、入力データの更新日、
   図ごとの生成コマンド、そして**採用した集約方法**（median / mean）
3. 図と `PROVENANCE.md` を同じコミットに入れる

`generate_figures.py` が出すサイドカー JSON
（`figures/sweep/xxx.png.meta.json`）に、入力ハッシュ・試行数・
集約方法・各 size の `nb*` とバンド範囲が入っている。
`PROVENANCE.md` はここから転記すればよい。

## ファイル名

既存の規約に揃える。

```
{node}_size{N}_t{threads}_{内容}.png       個別の機材の図
{config}_{agg}.png                         generate_figures.py の sweep
{config}_size{N}_{agg}.png                 generate_figures.py の heatmap
fig_{内容}.png                             figures_src/ の1図1スクリプト
```

集約方法（`median` / `mean`）をファイル名に残すのは、あとから図だけを
見たときにどちらで作ったか判別できるようにするため。**確定版では
特に重要**で、集約方法が違えば `nb*` が変わりうる（実測で 57 条件中
15 条件で変化し、最大 40 ずれた）。
