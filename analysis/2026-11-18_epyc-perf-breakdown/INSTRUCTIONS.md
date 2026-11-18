# EPYC 7543 で QR の時間の内訳を測る：c0 と τ の切り分け（2026-11-18）

指示書：`~/Documents/tileQR_research/chats/2026-11-18_epyc-perf-breakdown_brief.md`

目的：11-17 の DAG の見積もり（不老・弐）で、並列度の不足では説明できない「残り」が「size ごとの一定の時間 c0 ＋ τ·タスク数」で合うと分かった。c0 と τ の中身（タイル形式への写し、ページフォルト、スレッドの生成、ランタイムの中、カーネルの遅れ）を、EPYC 7543（p = 32、無償）の `perf`・`strace -f -c` で直接測って切り分ける。

**この結果は EPYC 7543 のものである。** 不老・弐（p = 192、libgomp）の c0・τ とは直接比べない。

- **第1部**：ユーザーが EPYC 7543 で実行する（devbox-lab から EPYC には接続できない）
- **第2部**：結果を `~/Download/epyc/epyc_20261118/` に置いたあと、devbox-lab で解析する

---

# 第1部：EPYC 7543 で実行すること

## 1. 条件

1点 ＝ 新しいプロセス。`--repeat` は付けない。スレッドは固定あり（libiomp5 なので `KMP_AFFINITY=granularity=core,compact`。`common.sh` の `hpc_set_cond close` が設定する）。ib = nb/4（11-10・11-11 の計測と同じ）。

| 軸 | 値 | 理由 |
|---|---|---|
| size | 4096、8192 | 不老・弐で c0 が 48・169 ms と目立つ size（DAG の RESULT.md 表C） |
| nb | 32、192 | 32：タスクが最も多い（4096 で 707,264、8192 で 5,625,216）＝ τ·タスク数が効く側。192：DAG の最適 nb 付近でタスクが少ない（3,795、27,434）＝ c0 が残る側 |
| p | 32、8 | 32：EPYC 7543 の全コア。8：p を変えて c0・τ が p に依るかを見る |
| 起動だけ | size 512、nb 32（p = 32、8） | 行列が小さいので、スレッドの生成・`plasma_workspace_create` など size によらない固定の時間が分かる。タスク 1,496 |
| 実行の種類 | plain、ref、perf、strace | 下の表 |

| 種類 | 何をするか | 取れるもの | 回数 |
|---|---|---|---|
| plain | `/usr/bin/time -v` だけ（`--test=n`） | 素の時間。page-faults、context switch、user・sys 時間、最大 RSS | 5 |
| ref | `--test=y`（plasmatest の既定。11-10・11-11 と同じ） | `--test=n` で時間が変わらないかの確認（p = 32 の大きい条件だけ） | 5 |
| perf | `perf record -e cpu-clock`（`-g` なし）→ `perf script` を `reduce_perf.py` で区分け | ライブラリごと・カーネルの区分ごとの時間（計時区間の中） | 5 |
| strace | `strace -f -c` | システムコールの回数と時間（mmap・munmap・futex・clone など） | 3 |

- 大きい条件は 2 サイズ × 2 nb × 2 p ＝ 8 点、起動だけが 2 点。1 round ＝ 10 点 × 種類
- perf・strace は plain と**別の実行**。perf・strace の時間は素の時間として使わない。plain との差（perf・strace による遅れ）も `runs.csv` から出す
- 計測の順番は、round ごとに条件の中の種類の順をずらす（時間による変動を種類の間でそろえる）
- `--test=n` にする理由：検算（`plasma_dorgqr`・`plasma_dormqr`、`Aref` の複製）が perf の内訳に混ざらないように。計時区間の外だが、プロセスの試料に入る

## 2. 所要時間の見積もり

11-10・11-11 の GFlops（`b_per_task.csv`）から、1点の QR の時間は 4096 で 0.4〜3 秒、8192 で 2〜23 秒。これに行列の初期化（`dlarnv`、主スレッドだけ、8192 で 1〜2 秒）と起動が加わる。

| 実行 | 見積もり |
|---|---|
| plain・ref・perf（5 round） | 約 25〜35 分（perf は試料の処理が 1 点あたり 数秒〜数十秒加わる） |
| strace（3 round、別の実行） | 5〜30 分。`strace -f` はスレッドが多いと遅くなる。1 プロセス 600 秒で打ち切る（`TIMEOUT`）。長すぎたら Ctrl-C してよい（取れた分だけ使う） |

合計は 1〜1.5 時間以内の見込み。流している間に発表の準備ができる。

## 3. 共用機への配慮

- **流す前に `0_preflight.sh`**：他のユーザーの CPU 使用率の合計を出す。100% を超えていれば流さない（`1_perf_breakdown.sh` も開始前に同じ確認をして中止する。`MAX_OTHER_CPU`、`FORCE=1` で無視できる）
- 実行ごとに「他のユーザーの CPU 使用率」と load average を `runs.csv`（`other_cpu_before`、`load1_before`）に記録する。round ごとにも `run.log` に `uptime` を残す。解析で、重なった点を除く
- 研究室のもう1人が使い始めたら中断してよい。1 round の途中で止めても、それまでの行は使える
- tmux の中で流す（SSH が切れても続く）。ほかの計測と同時に流さない

## 4. 流し方

### 4.1 持っていく

devbox-lab で作ったこのディレクトリを EPYC に持っていく（`scp -r` で、`scripts/` だけでよい）。以下 `S=<EPYC 上の置き場所>/scripts`。

```bash
cd ~/Workspace/plasma-bench      # ブランチ feat/tau-campaign（scripts/hpc/lib/ がある）
git branch --show-current
S=<EPYC 上の置き場所>/scripts
```

### 4.2 事前の確認（1分）

```bash
bash $S/0_preflight.sh 2>&1 | tee preflight_$(date +%Y%m%d_%H%M%S).txt
```

見るもの（出力ごと devbox-lab のチャットに貼る）：

1. `other_users_cpu_pct` が 100 以下
2. `perf`・`strace`・`/usr/bin/time` がある。`perf_event_paranoid`、`kptr_restrict`
3. 「perf の試し打ち」で `perf record exit=0`、`kernel samples:` が 0 でない（0 ならカーネルの試料が取れない。perf はユーザー空間だけになる）、`PERF_RECORD_FORK` の行が出る
4. 最後の plasmatest の行の 3 列目が Time、4 列目が Gflop/s
5. `ldd` の行：カーネルが OpenBLAS か MKL か（11-10 は OpenBLAS と libiomp5）

**perf が使えない・カーネルの試料が取れないとき**：`1_perf_breakdown.sh` は `perf` が無ければ止まる。そのときは次の順で代わりに進める（ユーザーはここで止めて devbox-lab に戻ってよい）。

| 代わり | 取れるもの | 取れないもの |
|---|---|---|
| `KINDS="plain ref"` と `KINDS=strace`（perf なしで流せる） | page-faults、user・sys 時間、システムコールの回数・時間 | libiomp5 / OpenBLAS / libplasma_core_blas の割合、`plasma_workspace_create`・dlacpy の割合。**「分けられなかった」と書くことになる** |
| `sudo -n` が使えるなら `sudo sysctl kernel.perf_event_paranoid=1`（共用機なので、元の値に戻すこと。管理者の許可を取る） | カーネルの試料 | — |
| `ltrace` は、OpenMP のタスクの数だけ呼び出しがあり遅すぎるので使わない | — | — |

### 4.3 本番（perf と素の実行）

```bash
SESSION=pb scripts/local/run_campaign.sh -- bash $S/1_perf_breakdown.sh
```

（`scripts/local/run_campaign.sh` が無ければ `tmux new -s pb` の中で `bash $S/1_perf_breakdown.sh`。）
進み具合は `tmux attach -t pb`。1 行ごとに種類・条件・時間・他のユーザーの CPU 使用率が出る。

### 4.4 strace（別の実行。perf の後）

```bash
KINDS=strace ROUNDS=3 bash $S/1_perf_breakdown.sh
```

### 4.5 持ち帰る

`results/benchmark/epyc_s1_smt-off_perf-breakdown_<時刻>/` が 2 つできる（perf 側と strace 側）。それぞれを `~/Download/epyc/epyc_20261118/` に置く。**`perf/*.script.gz`（round 1 の perf script の生の出力）も入れる**（区分けの規則を直すときに使う）。`perf.data` は消してある。

---

# 第2部：devbox-lab で解析すること（結果が届いてから）

1. `scripts/` に解析を足す（`common.py` は `2026-11-11_epyc-tau-followup/scripts/common.py` の読み込みを使い回す）
   - `a_runs.py`：`runs.csv` から、種類ごとの時間（5 回の中央値と範囲）、perf・strace による遅れ（plain との比）、`--test=n` と ref の差、page-faults（A の初期化分 `size²·8/4096` と起動の分を引いて、計時区間の分を出す）、他のユーザーの CPU 使用率が高かった点の除外
   - `b_window.py`：perf の区間の推定（M1・M2）と plasmatest の Time を比べ、Time に合う区間を選ぶ。合わない点は「区間が決められない」と書く
   - `c_breakdown.py`：区分ごとのオンCPU の秒数（試料数 / freq）を、size・nb・p ごとの表にする。残り（p × 区間 − オンCPU）は「眠っている・待っている」
   - `d_c0_tau.py`：区分ごとに、size 一定で nb 32 と 192 の 2 点から「nb によらない側（c0 側）」と「タスク数に比例する側（τ 側）」を出し、size 4096 と 8192 の比（行列の大きさに比例するか）と、起動だけの条件の固定の時間と比べる
2. 結果は `RESULT.md`（表・判定）と `fig_*.png`。図の表記は η でなく E_カーネル・E_並列
3. 判定は、c0 の候補（スレッドの生成、`plasma_workspace_create`、ページフォルト、munmap、dlacpy）ごとに「何割を占めるか」「占めると言えない」「分からない」に分ける。τ（EPYC 7543 の 2.0〜3.4 µs）の中身は、ランタイムの中（libiomp5）かカーネルの遅れ（カーネル・OpenBLAS の遅れ）かを同じ形で書く

## 解析で気を付けること（手順書を作る段階で分かっていること）

- 試料は `cpu-clock`（オンCPU の時間）。眠っている時間は出ない。libiomp5 は既定で約 200 ms 回り続ける（`KMP_BLOCKTIME`）ので、待ちは試料に出る（`omp_wait`）。タスクの取り合いと待ちは、symbol の名前で分けるため、完全には分けられない
- 計時区間の推定（M1）は、最初の `#pragma omp parallel` の前にもスレッドが作られる場合（MKL の `dlarnv` が libiomp5 を使う場合など）に狂う。M2 と Time で確かめる。`plasma_workspace_create` の中でスレッドが作られること自体は、`perf script` の FORK の時刻と区間の始まりが合うかで確かめられる
- 区分けの規則（カーネルの symbol の正規表現）は推定。`*_top.csv` の上位の symbol と `k_other` の大きさで確かめる
- c0 ＝ 2 点（nb 32・192）から出した「nb によらない側」であって、「size に比例する側」とは限らない。size 4096 と 8192 の比で確かめる（6 点は少ない）
- 「c0 はタイル形式への写しやページフォルトの時間」「τ はタスクの生成」は、まだ言えない。この計測の結果で言えるようになった範囲だけを書く
