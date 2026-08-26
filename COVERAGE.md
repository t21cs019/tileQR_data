# COVERAGE

`scripts/ingest.py` が自動生成する。手で編集しない。

## qr_sweep

| config | threads | size | ノード数 | ノード |
|---|---|---|---|---|
| `aoba-b_s1_smt-off` | 64 | 4096 | 5 | par001, par002, par003, par004, par006 |
| `aoba-b_s2_smt-off` | 128 | 4096 | 5 | par001, par002, par004, par006, par007 |

## 欠損の候補

- なし

## kernel_dtsmqr

| node | threads | nb 範囲 |
|---|---|---|
| corei5-13400F | 4 | 4-350 |
| corei5-13400F | 8 | 4-350 |
| corei5-13400F | 16 | 4-350 |
