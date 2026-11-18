# plasmatest・PLASMA のスレッドの立ち上げと、不老・弐の CPU の割り当て（2026-11-17）

計測も接続もしていない。コード、ジョブスクリプト、手元にある既存のログだけを読んだ。

略記：
- `P/` = `~/Download/build_plasma/plasma`（PLASMA のソース。`git log -1` は `548e0bd`、版は 25.5.27。`~/Library/plasma` にはインストールされた `bin`・`lib`・`include` だけがあり、ソースは無い）
- `B/` = `~/Workspace/plasma-bench`（ブランチ `feat/tau-campaign`、HEAD `ee9701b`）
- `F/` = `~/Download/flow`（不老・弐のログ）

## 1. 結論

### 1.1 スレッドを作る場所とタイミング

**スレッドのチーム（191 本の新しいスレッド）は、計時区間の中の `plasma_workspace_create` で、プロセスごとに毎回作られる。** 計時区間の前に OpenMP の並列領域は1つもない。

| 順番 | 場所 | 何が起きるか | 計時区間 |
|---|---|---|---|
| 1 | OpenBLAS の constructor `gotoblas_init`（`~/Download/build_openblas/OpenBLAS-0.3.28/driver/others/memory.c:1508`）→ `blas_thread_init`（`driver/others/blas_server_omp.c:127-147`） | `USE_OPENMP=1` の版（`~/Workspace/plasma-workspace/setup/install_openblas.sh:58-60`）は `omp_get_max_threads()` を読み、バッファを用意するだけ。スレッドは作らない | 前 |
| 2 | `P/test/test.c:537` `print_header` → `run_routine(name, pval, false)`（`test.c:671`）→ `test_dgeqrf(param, false)` | 使う引数の印を付けて `P/test/test_dgeqrf.c:48-49` で戻る。並列領域なし。`omp_get_max_threads()`（`test.c:677`）は ICV を読むだけ | 前 |
| 3 | `P/test/test.c:540` `plasma_init` → `P/control/context.c:30-47`、`plasma_context_init`（`context.c:165-180`） | 既定値を入れるだけ。並列領域なし（`omp_get_max_threads()` は `context.c:175`、`P/control/tuning.c:95`） | 前 |
| 4 | `P/test/test_dgeqrf.c:76-92` | 行列 A の `malloc` と `LAPACKE_dlarnv`（主スレッドだけで初期化。A のページはここで主スレッドが触る）、検算用の `Aref` の複製 | 前 |
| — | **`P/test/test_dgeqrf.c:102` `start = omp_get_wtime()`** | 計時の開始 | |
| 5 | `P/compute/dgeqrf.c:114-126` | タイル形式の A と T の記述子を `malloc`（`P/control/descriptor.c:41`）。中身はまだ触らない | 中 |
| 6 | `P/compute/dgeqrf.c:131` → **`P/control/workspace.c:20-24`（`#pragma omp parallel` + `master`）** | **プロセスで最初の並列領域。ここで libgomp が 191 本のスレッドを作る**（固定ありなら各スレッドを自分の place に置く） | **中** |
| 7 | `P/control/workspace.c:37-43`（2つ目の `#pragma omp parallel`） | 各スレッドが自分の作業領域を `malloc`（`nb + ib*nb` 個の double）。スレッドは 6 で作ったものを使い回す | 中 |
| 8 | `P/compute/dgeqrf.c:146-157`（3つ目の `#pragma omp parallel` + `master`） | 主スレッドだけがタスクを作る：タイル形式への写し（`P/compute/pdge2desc.c:49` の `dlacpy` タスク）、分解（`P/compute/pdgeqrf.c:43-74`、各カーネルは `#pragma omp task depend(...)`、例 `P/core_blas/core_dgeqrt.c:178`）、元の形式への写し。他のスレッドは暗黙のバリアでタスクを取って実行する。**タイル形式の A と T のページは、ここでタスクを実行したスレッドが初めて触る** | 中 |
| 9 | `P/compute/dgeqrf.c:160-163` | 作業領域とタイル形式の A を `free` | 中 |
| — | **`P/test/test_dgeqrf.c:104` `stop = omp_get_wtime()`** | 計時の終わり | |
| 10 | `P/test/test_dgeqrf.c:113-190` | 検算（`--test` の既定は `y`、`P/test/test.c:919`）。`plasma_dorgqr`・`plasma_dormqr` で並列領域を使う（スレッドは使い回し） | 後 |

- **1点ごとに新しいプロセス。** plasma-bench は1点ごとに `plasmatest dgeqrf --dim=SxS --nb=.. --ib=..` を1回起動する（`B/src/plasma_perf/benchmarks/tileqr/runner.py:50-57`、`B/src/plasma_perf/core/process.py:48`）。`--repeat` は付けない（既定 1、`P/test/test.c:916`）。不老・弐のスイープは `--trials 1`（`B/scripts/hpc/lib/tileqr_sweep.sh:80`）、A/B テストも同じ（`B/scripts/hpc/lib/bind_ab.sh:64-71`）。したがって **計測したすべての点で、スレッドの生成（6）、各スレッドの最初の `malloc`（7）、タイル形式の行列の最初のページフォルト（8）が計時区間に入っている**
- 同じプロセスで2回目以降（`--repeat`、`P/test/test.c:543-546`）はスレッドを作らない（libgomp・libiomp5 ともスレッドを使い回すため。ランタイムのソースは手元に無く、一般的な実装の知識）。ただし 5・7・8 の `malloc` とページフォルトは2回目にも起きる（glibc が解放した領域を使い回せば、ページフォルトは減る）。**`--repeat` の1回目と2回目の差は「スレッドの生成」だけでなく「メモリの最初の確保」も含む**
- 参考（既存の結果）：EPYC 7543（p = 32、libiomp5）で、同じプロセスの1回目は2・3回目より約 6.0 ms 長い。固定ありで 5.9 ms、なしで 6.1 ms（`analysis/2026-11-10_epyc-tau-campaign/VERIFICATION.md:21`）。立ち上げの時間は 32 コアでもあり、固定によらない

### 1.2 不老・弐のジョブで OMP_PLACES・OMP_PROC_BIND がどう効くはずか

ジョブは `numactl` で Python（plasma_perf）を包み、plasmatest はそれを受け継ぐ（`B/scripts/hpc/lib/tileqr_sweep.sh:76-82`）。環境変数は `os.environ` を写して `OMP_NUM_THREADS` だけ上書きする（`B/src/plasma_perf/core/env.py:16-17`）ので、シェルで export した `OMP_*` もそのまま渡る。

| | 固定なし（none） | 固定あり（close。本番のスイープの既定、`tileqr_sweep.sh:36`） |
|---|---|---|
| 設定 | `OMP_PLACES`・`OMP_PROC_BIND`・`KMP_AFFINITY` を unset（`B/scripts/hpc/lib/common.sh:105`）。サイトの既定値が入っていても消える | `OMP_PLACES=cores OMP_PROC_BIND=close`（`common.sh:111`。libiomp5 をリンクしていれば `KMP_AFFINITY`、`common.sh:108-109`。不老・弐は libgomp なのでこちら） |
| numactl | `--cpunodebind=0,1,2,3 --membind=0,1,2,3`（`common.sh:118`、`hpc_select_nodes` が P = 192 からソケット 0 の NUMA ノード 0〜3 を選ぶ、`common.sh:64-93`） | 同じ |
| プロセスが動ける CPU | CPU 0〜191（NUMA ノード 0〜3、各 48 コア、SMT 無効。`F/flow_bind-ab_20261031_082853/meta.txt` の lscpu） | 同じ |
| libgomp のふるまい（はず） | bind-var が false なので、スレッドに affinity を設定しない。192 本とも 0〜191 のどこでも動け、Linux のスケジューラが置き場所を決め、動かす | `cores` で、プロセスが動ける CPU（0〜191）から物理コアごとの place を作る。SMT 無効なので 1 place = 1 CPU で 192 個。`close` で 192 本を 192 個の place に先頭から1本ずつ置く。スレッドは作られた時からその CPU にとどまる |
| ログで確かめた結果 | 192 本とも `cpus=0-191`（`F/flow_bind-ab_20261031_082853/affinity_bind-none.txt`） | スレッド i が CPU i（`affinity_bind-close.txt`。本番のスイープ 21 個も同じ、`analysis/2026-11-10_flow2-sweep-check/report.md:62`） |
| L3 との関係 | 決まらない | CPU 0〜15、16〜31、… が同じ L3（`meta.txt` の `lscpu -e` の CACHE 列。16 CPU ずつ連続）なので、スレッド 0〜15 が1つ目の L3、…と 12 個の L3 に 16 本ずつ入る |
| メモリ | `--membind=0-3`。複数のノードを指定した MPOL_BIND では、ページはそのページに触った CPU に近いノードから取られる（Linux の `set_mempolicy(2)` の説明。不老・弐の kernel では未確認） | 同じ。ただしスレッドが動かないので、タイル形式の A・T のページの置き場所（1.1 の 8）と、それを後で使うスレッドの位置の関係が実行中に変わらない |

効き方について、コードから言えること：
- **PLASMA のタスクはどのスレッドにも固定されていない。** `#pragma omp task depend(...)` のタスクは、空いたスレッドが取って実行する（`P/core_blas/core_dgeqrt.c:178` など）。固定しても「タイル ↔ コア」の対応は決まらない。**固定が変えるのは「スレッド ↔ コア」と、スレッドを作るときの置き場所だけ**
- 固定ありでは、スレッドは作られた時点で自分のコアに置かれる（libgomp はスレッドを作るときに affinity を指定する。libgomp の実装の知識で、ソースは手元に無く未確認）。固定なしでは、191 本を作ったあとの置き場所と移動は Linux のスケジューラ次第で、それが計時区間（1.1 の 6〜8）の中で起きる
- 主スレッドの位置：固定ありでは主スレッドは CPU 0（ログ）。libgomp は初期化の時点で主スレッドを place 0 に固定する実装なので（未確認）、A の初期化（1.1 の 4）も CPU 0、つまり NUMA ノード 0 で行われ、A のページはノード 0 に集まるはず。固定なしでは、主スレッドがそのとき居たノードに置かれる

### 1.3 「不老・弐だけで固定が効く」理由の候補

**確かめられたこと（コード・ログで確認）**

| | 内容 | 根拠 |
|---|---|---|
| K1 | スレッドの生成と配置、各スレッドの最初の `malloc`、タイル形式の行列の最初のページフォルトは、どの機種でも全点で計時区間に入っている。固定が効くのは、この「起動直後」の部分に限られる可能性がある | 1.1 |
| K2 | 「スレッドの移動に制限がある」ことはない。不老・弐の固定なしでは、192 本とも CPU 0〜191 のどこでも動ける。ジョブに割り当てられた CPU は少なくとも NUMA ノード 0〜3 のすべて（`hpc_select_nodes` はノードの CPU がすべて割り当てられているノードだけを選ぶ、`common.sh:67-75`） | `affinity_bind-none.txt` |
| K3 | 不老・弐の固定なしは、AOBA の固定なしと同じ作り（libgomp、自前ビルドの PLASMA 25.5.27 と OpenBLAS 0.3.28、同じスクリプト、ソケット 0 の NUMA ノード 4 つ、各スレッドは全 CPU で動ける）。違うのは **p（192 対 64）**、CPU（EPYC 9965 Zen 5c と 7702 Zen 2）、L3 の組（16 コア対 4 コア）、OS と libgomp の版 | `F/flow_bind-ab_20261031_082853/meta.txt`、`~/Download/aoba/flow_bind-ab_20261101_163609/meta.txt`・`affinity_bind-none.txt`（64 本とも `cpus=0-63`、16 コア × 4 ノード） |
| K4 | AOBA（p = 64、libgomp、4 NUMA ノード）では固定の効果がない。nb 192 の平均で、close と none は 2048 で 178.6 と 175.4、4096 で 506.6 と 506.8、8192 で 754.1 と 741.3 GFlops。**「4 NUMA ノードにまたがって固定しない」だけでは効果は出ない** | `~/Download/aoba/flow_bind-ab_20261101_163609/summary.txt` |
| K5 | EPYC 7543 は条件がそろっていない（libiomp5、p = 32、NUMA ノード 1 つ）。不老・弐との比較から、ランタイムの違いと p の違いは分けられない | `chats/2026-10-31_flow2-bind-ab.md` §6、`~/Download/epyc/epyc_s1_smt-off_repeat-ab_20261110_190318/meta.txt` |
| K6 | 固定ありでも、不老・弐では約 13〜15 ms の遅れが4回に3回入る。固定は「起動直後の遅れ」を全部は消さない | `analysis/2026-11-10_flow2-sweep-check/report.md:17, 184` |
| K7 | 立ち上げの時間（同じプロセスの1回目だけ長い）は EPYC 7543 にもあり（約 6 ms）、固定の有無で変わらない | `analysis/2026-11-10_epyc-tau-campaign/VERIFICATION.md:21` |

**未確認の候補（どれもデータで決められていない）**

| | 候補 | 合う点 | 合わない点・弱い点 | 確かめ方（計測が要るものは司令塔で相談） |
|---|---|---|---|---|
| U1 | **p が大きいと、固定なしでスレッドを作った直後の配置・移動に時間がかかる。** 191 本を作って Linux のスケジューラが 192 CPU に散らすまでの時間や、待っていたスレッドが起きるときの置き場所。スケジューラが負荷を均す範囲と間隔は CPU 数とともに大きくなる（一般論） | 固定なしで増える時間は実行時間によらない一定の時間（`chats/2026-11-10_serial-task-cost.md` 2節）。AOBA（p = 64）では出ない（K4）。計時区間に生成が入っている（K1） | p と機種（Zen 5c、L3 の組）が同時に変わっていて分けられない（K3） | 手元のデータで：AOBA の固定なしに p 依存が無いか。計測なら EPYC 7543 で `--repeat` と p を変える（無償）。不老・弐で p = 48/96 の固定あり・なし（有償） |
| U2 | **libgomp の待ち方。** 既定（`OMP_WAIT_POLICY` なし）では、仕事の無いスレッドは短く回ったあと futex で眠る。起こされたときに別の CPU（別の L3・別の NUMA ノード）で再開しうる。libiomp5 は既定で約 200 ms 回り続けるので、EPYC 7543 では眠りにくい（どちらも一般的な既定値で、各機種の版では未確認） | EPYC 7543（libiomp5）で効かないことに合う。PLASMA のタスクの待ちはバリアでの待ち | AOBA も libgomp なのに効かない（K4）。p との組み合わせでしか説明できない | 不老・弐のジョブの環境で `OMP_WAIT_POLICY`・`GOMP_SPINCOUNT` が設定されていないか（meta.txt に記録が無い）。libgomp の版（`/lib64/libgomp.so.1`）も記録に無い |
| U3 | **NUMA とメモリの置き場所。** タイル形式の A・T は計時区間の中で、タスクを実行したスレッドが初めて触ったノードに置かれる（1.1 の 8）。固定なしではスレッドが後で別のノードに移り、遠いメモリを使う | 固定なしの cv が大きい（`chats/2026-10-31_flow2-bind-ab.md` §2） | AOBA も 4 NUMA ノードにまたがるが効かない（K4）。`--membind` と `--interleave` の差はばらつきの範囲（同 §2） | — |
| U4 | **1コアあたりの L3 が小さい（2 MB）。** スレッドが移ると L3 の中身を失う | 1コアあたりの L3 の並び（不老・弐 2 MB、AOBA 4 MB、7543 8 MB）と効果が合う（同 §8） | 効果は一定の時間で、小さい行列ほど大きい。L2 は不老・弐が最も大きい。L3 の組が 16 コアで、別の L3 へ移る確率はむしろ低い（同 §8） | 同じプロセスで2回目を測る（同 §8、`report.md:416-431`。不老・弐では許可されていない） |
| U5 | **休んでいるコアの立ち上がり・周波数。** 不老・弐は 1.2〜3.7 GHz の可変（`meta.txt` の lscpu、`CPU(s) scaling MHz: 55%`）。固定なしでは、休んでいたコアにスレッドが移るたびに立ち上がりを待つ | 固定ありにも残る 13〜15 ms（K6）の説明にもなりうる | 割合が点の間隔によらない（`report.md` C5 の補足） | — |
| U6 | **計時区間の中のメモリ操作が 192 スレッドで重くなる。** 各スレッドの最初の `malloc`（1.1 の 7、glibc はスレッドごとのアリーナを作る）、タイル形式の行列のページフォルトと `free`（munmap で全 CPU への TLB の消去） | p とともに増える。固定ありにも残る遅れ（K6）の候補にもなる | 固定の有無で差が出る理由にはならない（固定ありでも同じ処理） | `perf`・`strace -f -c` で起動直後の時間の内訳を見る（EPYC 7543 なら無償） |
| U7 | **PBS や OS が与える割り当て（cgroup の cpuset）やサイトの既定の環境変数。** | — | ログでは none のスレッドが 0〜191 で動け（K2）、`OMP_PLACES`・`OMP_PROC_BIND` はスクリプトが unset する（`common.sh:105`）ので、この2つの既定値は効いていない | ジョブの最初の `numactl --show`・`cat /proc/self/status`・`env | grep -E 'OMP|GOMP|KMP'` を meta.txt に残すようにする（スクリプトの変更。司令塔で相談） |

まとめ：**PLASMA と plasmatest には、不老・弐だけで働く仕組み（スレッドの移動の制限など）は見当たらない。** コードはどの機種でも同じで、どの点もスレッドの生成と最初のメモリ確保を計時区間に含む。不老・弐と、同じ libgomp・同じ 4 NUMA ノードで固定の効果が無い AOBA との違いは、p（192 対 64）とハードウェア（L3 の組、周波数）、OS と libgomp の版。いちばん合うのは U1（p が大きいと、固定なしで作った直後の配置・移動が遅い）だが、確かめていない。

## 2. データの確認

- 読んだもの
  - PLASMA のソース：`~/Download/build_plasma/plasma`（`548e0bd`）。指示では `~/Library/` 以下とあったが、`~/Library/plasma` はインストール先で、ソースは無かった。不老・弐でビルドしたソースがこれと同じかは、版の表示（`PLASMA 25.5.27`、`F/flow_bind-ab_20261031_082853/affinity_bind-none.txt` の1行目）が同じことまでしか確かめていない
  - OpenBLAS のソース：`~/Download/build_openblas/OpenBLAS-0.3.28`
  - plasma-bench：`B/scripts/hpc/lib/common.sh`、`tileqr_sweep.sh`、`bind_ab.sh`、`repeat_ab.sh`（冒頭）、`B/scripts/hpc/flow/job_sweep.sh`・`job_bind_ab.sh`・`machine.sh`、`B/src/plasma_perf/benchmarks/tileqr/runner.py`、`core/env.py`、`core/process.py`。指示の「flow/ 以下」は `scripts/hpc/flow/` と `scripts/hpc/lib/` にあった
  - ログ：`F/flow_bind-ab_20261031_082853/`（meta.txt、affinity_*.txt）、`F/benchmark/*_meta.txt`（本番のスイープ。`OMP_PLACES=cores OMP_PROC_BIND=close`、`numactl --cpunodebind=0,1,2,3 --membind=0,1,2,3` を記録）、`~/Download/aoba/flow_bind-ab_20261101_163609/`、`~/Download/epyc/epyc_s1_smt-off_repeat-ab_20261110_190318/`
  - 既存の検討：`chats/2026-10-31_flow2-bind-ab.md`、`chats/2026-11-10_epyc-flow-measurement.md`、`analysis/2026-11-10_flow2-sweep-check/report.md`、`analysis/2026-11-10_epyc-tau-campaign/VERIFICATION.md`、`weekly/2026-11-11.md:187`（指摘 14:21 の文面）
- 数値はすべて既存の表・ノートから写した（AOBA の値は `summary.txt` のまま）。計算し直したものは無い
- libgomp・libiomp5・Linux カーネルのふるまい（スレッドを作るときの affinity、主スレッドの固定、待ち方の既定値、MPOL_BIND のノードの選び方）は、ソースや文書が手元に無く、一般的な知識として書いた。表では「はず」「未確認」と書き分けた
- 不老・弐のジョブに PBS が与えた cgroup の cpuset そのものは、どのログにも残っていない（meta.txt に `numactl --show` の出力が無い）。分かるのは「NUMA ノード 0〜3 の CPU はすべて使えた」まで

## 3. 手順

1. 指摘 14:21 の文面（`weekly/2026-11-11.md:187`）と、週次まとめの項目（`weekly/2026-11-18.md:49`）を読んだ
2. `plasmatest` の `main`（`P/test/test.c:502-560`）から `test_dgeqrf`、`plasma_dgeqrf`、`plasma_workspace_create` までをたどり、`omp parallel` と計時の位置を並べた（1.1）。PLASMA の `control/` で `omp parallel` を持つのは `workspace.c` だけ（grep）
3. OpenBLAS の初期化がスレッドを作らないことを確かめた（`blas_server_omp.c:127-147`）
4. plasma-bench の起動の経路（ジョブ → `tileqr_sweep.sh` → numactl → plasma_perf → plasmatest）と、`hpc_set_cond` の環境変数をたどった（1.2）
5. 不老・弐・AOBA の A/B テストの meta と affinity のログで、実際の CPU の集合と構成を確かめた（1.2、1.3 の K2〜K4）

## 気になる点・判断を保留したこと

- 指示の「PLASMA のソースは `~/Library/` 以下」は、実際には `~/Download/build_plasma/plasma`（`~/Library/plasma` はインストール先）。版は同じ `548e0bd`
- `B/scripts/hpc/lib/common.sh:178` のコメントは「AOBA の GCC 8.5 では `OMP_DISPLAY_AFFINITY` が出ない」とあるが、AOBA の A/B のログ（`affinity_bind-*.txt`）はスレッド番号 0〜63 の `OMP_DISPLAY_AFFINITY` の形で、`/proc` から読んだ形（スレッド ID）ではない。AOBA の `/usr/lib64/libgomp.so.1` は OpenMP 5.0 の表示に対応しているらしい。結論には効かないが、コメントは実態と違う
- `--repeat` の1回目と2回目の差は、スレッドの生成とメモリの最初の確保（ページフォルト、glibc のアリーナ）を分けられない（1.1）。「同じプロセスで2回目を測れば分けられる」（`report.md`、`chats/2026-10-31_flow2-bind-ab.md` §8）の「分けられる」の範囲は、L3 の説と起動直後の説の間に限られる
- 不老・弐の libgomp の版、サイトの既定の環境変数（`OMP_WAIT_POLICY`、`GOMP_SPINCOUNT` など）、PBS の cpuset はログに無い。次に不老・弐でジョブを流すとき（許可が出たとき）に meta.txt に残すよう `common.sh` の `hpc_meta` を直すかは、司令塔で相談（plasma-bench の変更は書いてよい場所の外）
- 結果は既存の結論（`report.md` の「スレッドの生成が計時区間に入っていることは確認、原因かは未確認」）と食い違わない
