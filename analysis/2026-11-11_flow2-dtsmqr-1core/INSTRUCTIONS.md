# 不老・弐 DTSMQR 1コア計測の解析（2026-11-11）

devbox-lab の別のチャットに渡す依頼。計測は済んでいて、結果は `/home/ryo/Download/flow/ssrfb/` にある。

---

あなたの仕事は、不老・弐 Type I（EPYC 9965、Zen 5c）で取った DTSMQR の1コア計測から、この機種の **β と A** を決め、それを使った当てはめなしのモデルが不老・弐の QR（p = 192）にどれだけ合うかを示すことです。新しい計測はしません。**数値を疑うつもりで**読んでください。

## 背景（これ以上の背景資料は読まなくてよい）

tile QR（PLASMA）の性能モデル（当てはめなし）：

```
G_QR(nb) = p · A · E(nb) · η理論(nb)      E(nb) = nb / (nb + β)
```

- A と β はカーネル（DTSMQR）の性能曲線 `GFlops ≈ A · nb/(nb+β)` から決める。**β は1コアの計測で決める**（2026-10-28 のゼミの決定）
- これまでの手続き：`/home/ryo/Workspace/tileQR_data/analysis/2026-10-21/scripts/common.py` の `beta_from_ssrfb()`（69 行目から。**最初に読む**）。(node, size) ごとに (nb, ib) で平均し、ib = nb/8 の断面（`kurzak.ib_rule_slice`、nb ≥ 64）を取り、`kurzak.fit_E` で当てはめる。MRE が 5% を超える曲線は除く。`kurzak` は `src/tileqr_data/kurzak.py`
- 他の機種では MAT_SIZE 1024〜8192 の4つから決めた。β は MAT_SIZE にほとんどよらない（±5%）。**今回は size 4096 だけ**（有償のため）
- 不老・弐の QR は 2026-11-10 に size 1024〜8192 を各5回計測済み（config `flow2-t1_s1_smt-off`、`derived/qr_sweep.parquet` に取り込み済み）。1回の実行に約 13〜15 ms の遅れが確率的に入るため、5回の平均は使わない。推奨の集計は `analysis/2026-11-10_flow2-sweep-check/report.md` と `scripts/common.py` の `add_baseline` にある

## 計測の条件（確認済みの事実）

- plasma-bench `ee9701b` の `scripts/hpc/lib/ssrfb_sweep.sh`。NoFlush を `numactl --physcpubind=1 --membind=0` で1コアに固定。ノードを専有し、ほかのコアは空いている
- size 4096、nb 32〜512・ib 8〜nb/2（刻み 4）、3963 点、N_IT = 50、5回（r1〜r5）を同じジョブ（PBS 112117.jobm）で順に流した。1回約 25 分
- CSV の列：`threads,size,nb,ib,Time_sec,GFlops`。5 本とも 3963 行
- `_clock.txt`：固定したコアのクロック（MHz）を 60 秒ごとに記録（約 3745〜3756 MHz）
- tileQR_data 0.23.0 で `derived/ssrfb.parquet` にノード `t1205` として取り込み済み。`io.load_ssrfb()` で読んでよい（CSV を直接読むのと同じ値）
- 取り込み時に見つけたこと：最初の点（nb 32, ib 8）は5回とも遅い（0.05〜4.24 GFlops。起動直後の1点目の現象）。ほかに1回だけ外れた点が2つ（r1 の nb 52/ib 24、r5 の nb 372/ib 8）。`docs/CHANGELOG.md` の 0.23.0。除外はしていないので、使うときに扱いを決めて書く

## すること

1. **データの確認**
   - 5 本の `_meta.txt` の条件の行（`CORE=… SIZE=…`、`numactl …`）が上と同じか。NoFlush の ldd が自前の OpenBLAS を指しているか。違っていたら、解析の前に報告する
   - 回ごとのばらつき：点ごとの (最大 − 最小)/中央値の分布。外れた回や点があるか。前半と後半の回で傾向があるか（`_clock.txt` も見る）
2. **β と A**
   - `beta_from_ssrfb()` と同じ手続きで β と A を出す（`kurzak.ib_rule_slice` と `kurzak.fit_E`）
   - 5 回の平均への当てはめに加えて、回ごとの当てはめも示す（β のばらつき）。MRE も示す
   - ib = nb/8 の断面だけでなく、nb ごとに ib について最大（MaxIB）を取った曲線でも当てはめ、β がどれだけ変わるかを示す（手続きを変える提案ではなく、感度を見るため）
   - 8 の倍数の nb が速いギザギザ（他機種で見えている）が出ているか。出ているなら、当てはめへの影響
3. **他の機種との比較**
   - EPYC 7543（`raw/ssrfb/epyc/`、size 4096 の r1〜r5）の β・A を同じ手続きで出して並べる。2つの違いを1〜2行で（原因は推定と明記）
4. **不老・弐の QR との比較**
   - 2. の A・β で `p · A · E(nb) · η理論(nb)`（p = 192、c = √7.5、k = 2）を size 1024〜8192 について計算し、QR の実測と比べる。η理論とその計算は `analysis/2026-10-27_gen4-kernel-term/scripts/eta_eff.py` と同じものを使う
   - QR の実測は `add_baseline` の集計を主に使う。5回の平均でも計算し、結論が変わるなら両方示す
   - 見る量：η_eff / η理論 の nb 依存、予測の最適 nb と実測の最適 nb の差、予測の最適 nb での性能比。EPYC 7543 で見えた「小さい nb で落ちる」傾向（`analysis/2026-11-10_serial-task-cost/README.md`）が不老・弐でも出ているかを1〜2行で
   - A は1コアのクロック（約 3.75 GHz）で取った値で、192 コア同時のクロックは低いはず。QR の `_meta.txt`（`/home/ryo/Download/flow/benchmark/`）にクロックの記録があれば、その比で A を補正した場合も示す。記録がなければ「不明」と書き、補正しない

## 読むもの

- データ：`/home/ryo/Download/flow/ssrfb/` の 15 ファイル（`flow2-t1_s1_smt-off_core1_ssrfb_size4096_nb32-512_th1_r{1..5}{.csv,_meta.txt,_clock.txt}`）
- 不老・弐の QR の検証：`/home/ryo/Workspace/tileQR_data/analysis/2026-11-10_flow2-sweep-check/report.md`（集計の方法の節だけ）
- `spec/machines.yaml` の `flow2-t1_s1_smt-off`（430 行目あたり）

## 決まり

- `/home/ryo/Download/` のファイルは読むだけにする。変更・移動・削除しない。`raw_data/` への取り込みもしない（別に行う）
- 出力はこのディレクトリ（`/home/ryo/Workspace/tileQR_data/analysis/2026-11-11_flow2-dtsmqr-1core/`）に置く：`RESULT.md`（80 行以内）、`scripts/`、`data/`（集計した CSV）、図は必要なものだけ2枚まで（`fig_*.png`）
- Vault（`~/Documents/tileQR_research`）と `spec/` は変更しない。git の commit・push はしない
- 計測しない。追加の計測が要るなら `RESULT.md` に「次に確かめること」として書く。不老・弐は有償でゼミの許可が要るので、挙げるなら「ゼミで相談する案」と明記し、ノード時間の見積もりを付ける（今回の実績：3963 点 × 1回 ≈ 25 分）
- CSV を cat しない。python で集計する（`/home/ryo/Workspace/tileQR_data/.venv/bin/python -I`）。標準出力は1回 30 行程度に抑える
- 使っていない数値を書かない。推定と実測を書き分ける。確かめていない仮説を「原因」と書かない
- サブエージェントは使わない

## 出力（`RESULT.md`）

1. **結論（3行）**
2. **データの確認**：問題の有無と、回ごとのばらつき
3. **β と A の表**：手続き（ib = nb/8 / MaxIB）× 対象（5回の平均 / 回ごとの範囲）。MRE つき。EPYC 7543 の行も並べる
4. **QR との比較**：size ごとの表（予測の最適 nb / 実測の最適 nb / 予測の nb での性能比）と、η_eff / η理論 の傾向
5. **ゼミで言ってよい表現と、言ってはいけない表現**（それぞれ数行）
6. **次に確かめること**（優先順、最大3つ）

終わったら、チャットには結論の3行とファイルのパスだけを返す。
