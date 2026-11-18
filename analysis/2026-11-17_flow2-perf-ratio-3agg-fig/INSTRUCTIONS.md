# 任された作業（2026-11-17、司令塔から）

テーマ：flow2-perf-ratio-3agg-fig（日付 2026-11-17）

作業：~/Workspace/tileQR_data/analysis/2026-11-17_flow2-perf-ratio-3agg/ の集計（速い水準／遅い水準だけ／5回の平均）を使い、不老・弐（size 1024〜8192）の図を2種類作る。集計の定義と値は、その RESULT.md と 11-11 の report.md（~/Workspace/tileQR_data/analysis/2026-11-10_flow2-sweep-check/report.md）のとおりにし、計算し直さない。
- 図A：横軸 nb、縦軸 GFlops。size ごとに1枚ずつ（2×2 の4枚）。どのパネルにも3水準の線を描き、予測 nb（理論値の c, k、β = 124）を縦の破線で示す。size 8192 で速い水準と遅い水準が分かれていないことを注記する
- 図B：~/Documents/slides/weekly/2026-11-11.pptx の p.9 の右の図（不老・弐、性能比 %、理論値と57条件の当てはめを並べ、size ごとに棒を色分け）を、3水準それぞれで作る。元の図を作ったスクリプトを探し（候補：~/Workspace/tileQR_data/analysis/2026-11-11_flow2-curves/、~/Workspace/research-slides/build_2026-11-11.py）、色・軸・棒の上の数値の書き方をそろえる。β = 124（ib = nb/8）だけを使う（p.9 と同じ）
- スライドやノートの図のラベルに η を使わない（E_カーネル・E_並列 と書く）

## 完了条件
- 図A・図B の PNG が analysis/2026-11-17_flow2-perf-ratio-3agg-fig/ にある（スライドに貼れる横長の比率）
- 図B の棒の値が、2026-11-17_flow2-perf-ratio-3agg の RESULT.md の表と一致することを、スクリプトの中で確かめている
- 「速い水準」で描いた図B の値が、p.9 の元の図の値（理論値 3・2・3・24、当てはめ 3・3・6・36）と一致する
