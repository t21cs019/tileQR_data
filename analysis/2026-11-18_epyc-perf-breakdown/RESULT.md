# EPYC 7543 で QR の時間の内訳を測る：c0 と τ の切り分け（2026-11-18）

**状態：手順書までが済み、計測は未了（ユーザーが EPYC 7543 で流す）。** 内訳の表・判定は計測が届いてから書く。

## 済んだこと

- 手順書と条件の表：`INSTRUCTIONS.md`
- スクリプト（計算機には接続していない。`bash -n` と、perf script の形の合成データで `reduce_perf.py` の動作だけ確かめた。EPYC での実機の確認は 4.2 の事前確認）
  - `scripts/0_preflight.sh`：他のジョブ・perf・strace・plasmatest の出力の形の確認
  - `scripts/1_perf_breakdown.sh`：本番（plain / ref / perf / strace）
  - `scripts/reduce_perf.py`：perf script の出力を、計時区間の中の区分け（libiomp5・BLAS・core_blas・カーネルのページフォルト／munmap／futex など）に集計

## 未了

- 計測（4.2〜4.5）。結果は `~/Download/epyc/epyc_20261118/` に置く
- 内訳の表、c0・τ の判定（INSTRUCTIONS.md 第2部）
