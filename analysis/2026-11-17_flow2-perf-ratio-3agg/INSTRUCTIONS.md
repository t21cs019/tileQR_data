# 任された作業（2026-11-17、司令塔から）

テーマ：flow2-perf-ratio-3agg（日付 2026-11-17）

作業：不老・弐（size 1024〜8192）で、予測 nb での性能比を、実測の集計3通り（速い水準／遅い水準だけ／5回の平均）で出す。
β・A は Vault の [[2026-11-11_flow2-dtsmqr-1core]] の値をそのまま使う（2通りあれば両方）。参考：~/Workspace/tileQR_data/analysis/2026-11-11_flow2-dtsmqr-1core/RESULT.md（β = 124・A = 99.7、ib = nb/8。MaxIB では β = 68）。スイープのデータと集計の考え方は ~/Workspace/tileQR_data/analysis/2026-11-10_flow2-sweep-check/report.md（13〜15 ms の遅れの扱い、`scripts/common.py` の `add_baseline`）。11-11 のゼミの p.9（当てはめなしのモデルは不老・弐に合わない）の検証のやり直しで、指摘の内容は Vault の weekly/2026-11-18.md の「前回（11-11）の指摘への対応」にある。

## 完了条件
- 3通り × size の性能比の表が RESULT.md にある
- 「速い水準」「遅い水準」の定義と出典（どのレポートのどの節か）が書いてある
- 3通りで「当てはめなしのモデルが合わない」という結論が変わるかが1行で書いてある

どの集計を採るかは決めない（ゼミで相談する）。
