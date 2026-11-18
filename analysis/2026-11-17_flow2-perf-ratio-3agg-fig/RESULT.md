# 不老・弐 QR の曲線と性能比の図を、集計3通りで作る（2026-11-17）

## 1. 結論

図A・図B を作った。完了条件の3つとも満たした（どれも `scripts/b_ratio_fig.py` の assert で確かめ、通った）。

| 図 | ファイル | 大きさ |
|---|---|---|
| 図A：GFlops–nb、size ごと 2×2、3水準の線＋予測 nb の縦の破線、size 8192 に注記 | `fig_a_curves.png` | 1920×1080（16:9） |
| 図B：3水準を横に並べたもの | `fig_b_ratio_3agg.png` | 2160×720（3:1） |
| 図B：1枚ずつ（p.9 の図と同じ作り、少し横長） | `fig_b_ratio_fast.png`・`fig_b_ratio_slow.png`・`fig_b_ratio_mean.png` | 960×690 |

図B の棒の値（性能比 %、β = 124、ib = nb/8。size 1024・2048・4096・8192）

| 実測の集計 | 理論値の c, k（√7.5、2） | 57条件の c, k（2.590、1.473） |
|---|---|---|
| 速い水準 | 3・2・3・24 | 3・3・6・36 |
| 遅い水準だけ | 4・2・3・21 | 4・3・6・24 |
| 5回の平均 | 2・1・3・20 | 2・3・6・23 |

確かめたこと（`b_ratio_fig.py` の `check()`）

1. 理論値の棒 12 値が、`2026-11-17_flow2-perf-ratio-3agg/RESULT.md` の「A = 99.7、β = 124」の表（3桁）と文字列で一致し、予測 nb も一致。`data/b_summary.csv` の perf とも保存の精度（5桁）で一致（最大差 4.0e-6）
2. 速い水準・5回の平均の棒 16 値（2モデル × 4 size）が、11-11 の `2026-11-11_flow2-curves/data/ratio.csv`（p.9 の図の元）と、4桁の丸めの幅で一致（最大差 5.2e-5）。予測 nb・実測の最適 nb も一致
3. 速い水準の棒の上の数値が p.9 の値（理論値 3・2・3・24、当てはめ 3・3・6・36）と一致

## 2. データの確認

- 曲線は `2026-11-17_flow2-perf-ratio-3agg/data/a_curves.csv`（列 fast・slow・mean。ib について最大）をそのまま使い、集計し直していない。図A の予測 nb（32・40・72・128）と実測の最適 nb は同 `data/b_summary.csv`（kernel = ib=nb/8）の値をそのまま書いた（`data/a_pred_nb.csv`）
- 図B の元の図は `analysis/2026-11-11_flow2-curves/scripts/ratio.py` の `fig_flow2_ratio.png`（`research-slides/build_2026-11-11.py` 491 行目で p.9 に貼っている）。色（size ごとの4色）、背景、軸の範囲 0〜100%、縦軸のラベル、棒の上の整数の書き方、x の2つのラベルは ratio.py と同じにした。モデルの式・β = 123.83・57条件の c, k も ratio.py と同じ
- 57条件の c, k の棒は 3agg の RESULT.md には無いので、ratio.py と同じ式で a_curves.csv から出した（`data/b_ratio.csv`）。速い水準・平均は 11-11 の ratio.csv と一致することを上の 2 で確かめた。遅い水準だけの 57条件の値（4・3・6・24）には照らし合わせる元が無い
- ラベルに η は使っていない

## 3. 手順

1. `scripts/a_curves_fig.py` → `fig_a_curves.png`、`data/a_pred_nb.csv`
2. `scripts/b_ratio_fig.py` → `fig_b_ratio_{fast,slow,mean}.png`、`fig_b_ratio_3agg.png`、`data/b_ratio.csv`（突き合わせの assert を含む）

再現：`cd ~/Workspace/tileQR_data && uv run python analysis/2026-11-17_flow2-perf-ratio-3agg-fig/scripts/a_curves_fig.py`（b も同様）

## 気になる点・判断を保留したこと

- 図A の size 8192 の注記は「速い水準と遅い水準が分かれていない（2026-11-10 report.md C 節）。「遅い水準だけ」は ex > 6 ms で機械的に分けた値」とした
- 3agg の RESULT.md「気になる点」のとおり、予測 nb（32〜128）は base が当てにならない範囲なので、そこでの「遅い水準だけ」は5回の平均とほぼ同じになる。図にはこの注記を入れていない（スライドで使うならノートに書くとよい）
- 図A の size 1024 で、「遅い水準だけ」の曲線は5回の平均より下にある（遅い実行だけを平均するので当然）。曲線はぎざぎざ（3agg の RESULT.md の指摘と同じ）
- 1枚ずつの図B は p.9 の図（5.2×4.6 インチ）より少し横長（6.4×4.6）にした。p.9 と同じ枠に貼るなら、figsize を 5.2×4.6 に戻すだけでよい
