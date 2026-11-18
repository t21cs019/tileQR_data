# 作業の指示（2026-11-17、テーマ plasmatest-threads）

司令塔から受け取ったとおりに写す。

作業：plasmatest と PLASMA のスレッドの立ち上げ、不老・弐での CPU の割り当てを、コードと既存のジョブスクリプト・ログで確かめる（計測も接続もしない）。

手がかり：PLASMA のソースは ~/Library/ 以下（自前ビルド、master 548e0bd）。不老・弐のジョブスクリプトは ~/Workspace/plasma-bench（ブランチ feat/tau-campaign、flow/ 以下）、ログは ~/Download/flow/ など。関連する既存の検討：Vault の chats/2026-10-31_flow2-bind-ab.md（§8 に L3 の話）、~/Workspace/tileQR_data/analysis/2026-11-10_flow2-sweep-check/report.md（13〜15 ms の遅れ、スレッドの生成が計時区間に入っていることは確認済み）。不老・弐は libgomp、EPYC 7543 は libiomp5。背景は Vault の weekly/2026-11-18.md の 11-11 の指摘（14:21）。

## 完了条件
- スレッドを作る場所とタイミング（計時区間との関係）が、ファイルと行番号つきで書いてある
- 不老・弐のジョブで OMP_PLACES・OMP_PROC_BIND がどう効くはずかが書いてある
- 「不老・弐だけで固定が効く」理由の候補が、確かめられたものと未確認のものに分けて書いてある
