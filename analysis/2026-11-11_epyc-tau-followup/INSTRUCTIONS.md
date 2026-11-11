# EPYC 7543 の τ の追加確認（2026-11-11）

11-10 の τ の検証（`../2026-11-10_epyc-tau-campaign/VERIFICATION.md` の5節）で挙がった、結論を変える確認のうち3つを行う。

| # | 内容 | 分かること |
|---|---|---|
| A | libplasma のビルドを確かめる（計測なし） | 計測に使ってきた libplasma がどれか |
| B | p = 1, 2 の QR（nb 32, 64） | τ が p によらず一定か、p に比例するか |
| C | 空タスクの中身を実タスクの長さ（20000・100000 ns）にする | τ が直列の時間か、各コアが払う並列の時間か |

11-10 に分かったこと：plasmatest の QR は **OpenBLAS と libiomp5** で動いている（`LD_DEBUG=bindings`）。libplasma は `/usr/local/lib` から読まれている。

- **第1部**：ユーザーが EPYC 7543 で実行する（devbox-lab からは EPYC に接続できない）
- **第2部**：結果を `~/Download/epyc/` に置いたあと、devbox-lab の別のチャットに渡す依頼

---

# 第1部：EPYC 7543 で実行すること

所要時間の見積もり：A は1分、B は約30分、C は約30分。B と C は続けて流し、**流している間に発表の準備ができる**。見積もりは 11-10 の結果からの概算。

## 0. 準備

```bash
cd ~/Workspace/plasma-bench && source ../plasma-workspace/setup/config.sh
git status -s | head; git log --oneline -1      # feat/tau-campaign の 6ae6556 以降であること
tmux ls                                          # ほかの計測が流れていないこと
uptime                                           # load average が 1 未満であること
C=scripts/hpc/epyc7543/campaigns/2026-11-11_tau
```

## A. libplasma のビルドを確かめる（計測なし）

```bash
md5sum /usr/local/lib/libplasma.so.25.5.27 ~/Library/plasma/lib/libplasma.so.25.5.27 \
       /usr/local/lib/libplasma_core_blas.so.25.5.27 ~/Library/plasma/lib/libplasma_core_blas.so.25.5.27
readelf -d $PLASMA_TEST | grep -i -E 'rpath|runpath'
echo "$LD_LIBRARY_PATH" | tr ':' '\n'
```

出力をそのまま `~/Download/epyc/2026-11-11_libplasma_check.txt` に保存する（下の「結果の持ち帰り」）。

- 2つの md5sum が同じ → 同じビルド。どちらが読まれていても計測には影響しない
- 違う → これまでの計測は `/usr/local/lib` の版（2025-07-28、root 所有）で取ったことになる。どちらを使うべきかは、ゼミの後で決める（すぐには直さない）

## B と C を続けて流す

条件は環境変数で上書きする（スクリプトは 11-10 と同じものを使う）。tmux の中で、B → C の順に1行でつなぐ。

```bash
SESSION=tau2 scripts/local/run_campaign.sh -- bash -c "\
THREADS='1 2 4' SIZES='4096 8192' NB_LIST='32 64' IB_DIV=4 REPS=5 bash $C/1_thread_scaling.sh && \
THREADS='4 8 16 32' TILES='64 128' WORK_NS='0 20000 100000' REPS=5 ITERS=3 bash $C/2_task_overhead.sh && \
RUNTIMES=gomp THREADS=32 TILES=128 WORK_NS=0 REPS=20 ITERS=3 bash $C/2_task_overhead.sh"
```

進み具合は `tmux attach -t tau2` で見る（`Ctrl-b d` で離脱）。

| 段 | 条件 | ねらい |
|---|---|---|
| B | p = 1, 2, 4 / size 4096, 8192 / nb 32, 64 / ib = nb/4 / 5回 / 固定あり | p = 1, 2 が本題。p = 4 は 11-10 の結果と同じ日の比較用（11-10 と大きく違えば、日による差がある） |
| C1 | p = 4, 8, 16, 32 / タイル 64, 128 / 中身 0, 20000, 100000 ns / libgomp, libiomp5 / 5プロセス × 3回 | 中身 0 は同じ日の対照。タイル 256 は 100000 ns だと時間がかかりすぎるので外した |
| C2 | libgomp・p = 32・タイル 128・中身 0 / 20プロセス × 3回 | 11-10 に libgomp の p = 32 が2つの値（約 3.8 と 5.6〜6.2 µs）に分かれた。その割合を数える |

- ib = nb/4 は 11-10 と同じ（nb 32 は ib 8、nb 64 は ib 16）。VERIFICATION.md の比較が ib = nb/4 の中で行われているため
- p = 1 の size 8192・nb 32 が一番長く、1点 2 分前後の見込み。1点の上限（TIMEOUT）は 1800 秒のまま
- 途中で止まったら、`run.log` の最後を見て、止まった段から流し直す

## 結果の持ち帰り

`results/benchmark/` に、段ごとに `epyc_s1_smt-off_<実験名>_<時刻>/` が1つずつ（計3つ）できる。11-10 と同じ方法で devbox-lab の `~/Download/epyc/` に送る。

```bash
ls -d results/benchmark/epyc_s1_smt-off_*_20261111_*
```

A の出力は、テキストに貼って `~/Download/epyc/2026-11-11_libplasma_check.txt` に置く。

---

# 第2部：解析の依頼（devbox-lab の別のチャットに渡す）

あなたの仕事は、EPYC 7543 の追加計測（2026-11-11）の結果から、11-10 の τ の検証で「判定不能」または「一部支持」だった点がどう変わるかを判定することです。**反証するつもりで**読んでください。新しい計測はしません。

## 背景（これ以上の背景資料は読まなくてよい）

tile QR（PLASMA）で、コア数が多いと小さい nb の性能が理論モデルより落ちる。次の式の第2項が欠けている、と推定している。

```
時間 = W / (r0 · p · A_k · E_k(nb) · η(nb)) + タスク数 · τ      W = 4/3·size³
```

11-10 の検証（`/home/ryo/Workspace/tileQR_data/analysis/2026-11-10_epyc-tau-campaign/VERIFICATION.md`、56 行。**最初に全部読む**）の要点：

- nb ≤ 96 の QR の余分な時間はタスク数に比例する（p = 32 で 2.7〜3.2 µs/タスク、推定）。ただし「τ = a·p」と「τ = 一定（約 3 µs）」のどちらでも同じくらい合う
- 空のタスクの τ：libgomp は p にほぼ比例（a ≈ 0.17）、libiomp5 は頭打ち（p = 32 で 2.64 µs）
- 直列か並列かは判定不能
- 11-10 の後に分かったこと：**plasmatest の QR は libiomp5 と OpenBLAS で動いている**（`LD_DEBUG=bindings`）。したがって QR と比べる空タスクの τ は libiomp5 の値

## 判定すること

各項目を「支持 / 一部支持 / 反証 / 判定不能」で判定し、根拠の数値を示す。

1. **τ は p によらず一定か、p に比例するか**（計測 B）
   - VERIFICATION.md 5節の推定：size 4096・nb 32・p = 1 で、一定なら約 11.5 µs/タスク、a·p なら約 20 µs/タスク。この推定の作り方（p = 4 を基準に、p·η理論（c = √7.5）で理想的に速くなると仮定した差）を VERIFICATION.md から読み取り、同じ方法で p = 1, 2 の余分な時間を出す
   - p = 1 では並列の取り合いがないので、p = 1 の「1タスクあたりの全時間」をカーネルの時間の基準にする方法も考える。p = 4 基準と p = 1 基準で結論が変わるなら、両方を示す
   - nb 64 でも同じ結論になるか
   - p = 4 が 11-10 の値と何 % 違うか（日による差の大きさ）
2. **τ は直列か並列か**（計測 C1）
   - `tau_us = (total_sec − ntasks·work_ns/threads) / ntasks`（`native/task_overhead/task_overhead.c`）
   - 単純化した2つのモデルの予測：
     - 直列（投げる1本が律速）：全時間 ≈ max(タスク数 · τ₀, タスク数 · 中身 / p)。中身/p が τ₀ より大きくなると `tau_us` は 0 に近づく
     - 並列（各コアがタスクごとに o を払う）：全時間 ≈ タスク数 · (中身 + o) / p。`tau_us` は中身によらず一定
   - 例：p = 4 の中身 20000 ns は中身/p = 5 µs で τ₀（約 0.8 µs）より大きい。p = 32 の 100000 ns は中身/p = 3.1 µs で、libiomp5 の τ₀（2.64）とほぼ同じ、libgomp（5.59）より小さい
   - この2つのモデルは単純化しすぎかもしれない。どちらにも合わないなら、合わないことをそのまま書き、データに合う別の形を1つ挙げる
   - libgomp と libiomp5 で結論が違ってよい。QR の解釈に使うのは libiomp5
3. **libgomp の p = 32 の2つの値**（計測 C2 と C1 の中身 0）
   - 20 プロセスのうち何本がどちらの値か。同じプロセスの3回は同じ値か（11-10 はそうだった）
   - 原因の候補を1行で（調べなくてよい）
4. **libplasma のビルド**（`2026-11-11_libplasma_check.txt`）
   - 2つが同じか。違う場合、これまでの EPYC 7543 のデータの解釈に影響しうるかを1行で

最後に、11-10 の VERIFICATION.md の判定表（主張 1〜5）のうち、今回のデータで判定が変わるものを挙げる。

## 読むもの

データ：`/home/ryo/Download/epyc/` のうち、時刻が `20261111_` で始まる3つのディレクトリと `2026-11-11_libplasma_check.txt`。

| 計測 | ディレクトリ（`epyc_s1_smt-off_` の後） | CSV の列 |
|---|---|---|
| B | `thread-scaling_20261111_*` | threads,size,nb,ib,GFlops |
| C1 | `task-overhead_20261111_*`（早いほう） | process,runtime,threads,tiles,ntasks,work_ns,iter,total_sec,submit_sec,tau_us |
| C2 | `task-overhead_20261111_*`（遅いほう） | 同上 |

- まず各ディレクトリの `summary.txt` と、`meta.txt` の条件の行（THREADS=… など）を読み、条件が上の表どおりかを確かめる。違っていたら、解析の前に報告する
- 11-10 の比較用データ：同じ場所の `*_20261110_190457`（thread-scaling）と `*_20261110_201904`（task-overhead）
- QR のタスク数：タイル数 N = ⌈size/nb⌉ として Σk² = N(N+1)(2N+1)/6
- A_k、E_k、η が必要になったときだけ `/home/ryo/Workspace/tileQR_data/analysis/2026-11-10_serial-task-cost/README.md` を読む

## 決まり

- `/home/ryo/Download/epyc/` のファイルは読むだけにする。変更・移動・削除しない
- 出力はこのディレクトリ（`/home/ryo/Workspace/tileQR_data/analysis/2026-11-11_epyc-tau-followup/`）に置く：`RESULT.md`（80 行以内）、`scripts/`、`data/`（集計した CSV）。図は作らない
- Vault（`~/Documents/tileQR_research`）は変更しない。git の commit・push はしない
- 研究室の機械やスパコンで計測しない。追加の計測が要るときは、`RESULT.md` に「次に確かめること」として書く。不老・弐（Flow）は有償で、ゼミの許可が要る。挙げるなら「ゼミで相談する案」と明記する
- `run.log` は読まない。CSV を cat せず、python で集計する（`/home/ryo/Workspace/tileQR_data/.venv/bin/python -I`）。標準出力は1回 30 行程度に抑える
- 使っていない数値を書かない。推定と実測を書き分ける。仮説を確かめずに「原因」と書かない
- サブエージェントは使わない

## 出力（`RESULT.md`）

1. **結論（3行）**
2. **判定表**：項目 / 判定 / 根拠の数値 / 残る不確かさ
3. **11-10 の判定表から変わるもの**（主張 1〜5 のうち変わるものだけ）
4. **ゼミで言ってよい表現と、言ってはいけない表現**（それぞれ数行。11-10 の VERIFICATION.md 4節に足す・消すものだけ）
5. **次に確かめること**（優先順、最大3つ）

終わったら、チャットには結論の3行とファイルのパスだけを返す。
