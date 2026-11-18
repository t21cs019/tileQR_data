#!/usr/bin/env bash
# 0_preflight.sh — EPYC 7543 で、perf・strace が使えるかと、他のジョブが走っていないかを確かめる（計測はしない、1分）
#
#   使い方（plasma-bench のリポジトリの直下で）:
#       bash <このディレクトリ>/0_preflight.sh 2>&1 | tee preflight_$(date +%Y%m%d_%H%M%S).txt
#   出力をそのまま devbox-lab のチャットに渡す。
set -uo pipefail
PB="${PLASMA_BENCH:-$PWD}"
echo "# preflight $(date '+%F %T') host=$(hostname) user=$(id -un) kernel=$(uname -r)"

echo; echo "## 1. 他のジョブ（共用機。他のユーザーの CPU 使用率の合計が 100% を超えていたら流さない）"
uptime
ps -eo user:20,pcpu,etime,args --sort=-pcpu | head -8
other=$(ps -eo user:20,pcpu | awk -v me="$(id -un)" 'NR>1 && $1!=me {s+=$2} END{printf "%.0f", s}')
echo "other_users_cpu_pct=${other}"
who | head

echo; echo "## 2. perf・strace・time"
for c in perf strace; do printf '%-8s ' "$c"; command -v "$c" || echo "なし"; done
[ -x /usr/bin/time ] && /usr/bin/time -V 2>&1 | head -1 || echo "/usr/bin/time なし（GNU time が要る）"
perf --version 2>&1 | head -1; strace -V 2>&1 | head -1
echo "perf_event_paranoid=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null)"
echo "kptr_restrict=$(cat /proc/sys/kernel/kptr_restrict 2>/dev/null)"
echo "ptrace_scope=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null || echo なし)"
echo "perf_event_max_sample_rate=$(cat /proc/sys/kernel/perf_event_max_sample_rate 2>/dev/null)"
echo "THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)"
echo "governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo ?)"
printf 'sudo -n: '; sudo -n true 2>/dev/null && echo "使える" || echo "使えない"

echo; echo "## 3. perf の試し打ち（cpu-clock。カーネルのサンプルが取れるか）"
tmp=$(mktemp -d)
perf record -e cpu-clock -F 999 -o "${tmp}/p.data" -- sh -c 'i=0; while [ $i -lt 200000 ]; do i=$((i+1)); done' > "${tmp}/rec.txt" 2>&1
echo "perf record exit=$?"; head -5 "${tmp}/rec.txt"
perf script -i "${tmp}/p.data" -F comm,tid,time,ip,sym,dso 2>/dev/null | head -3
echo "kernel samples: $(perf script -i "${tmp}/p.data" -F ip,sym,dso 2>/dev/null | grep -c 'kernel')"
perf script -i "${tmp}/p.data" --show-task-events -F comm,tid,time 2>/dev/null | grep -m2 PERF_RECORD
echo "strace -f -c の試し打ち:"; strace -f -c -o "${tmp}/s.txt" true 2>&1 | head -2; head -4 "${tmp}/s.txt" 2>/dev/null
rm -rf "${tmp}"

echo; echo "## 4. plasmatest（--test=n のときの出力の形と、どのライブラリが使われるか）"
export MACHINE=epyc7543
# shellcheck source=/dev/null
source "${PB}/scripts/hpc/lib/common.sh"
hpc_setup
hpc_select_nodes 8
hpc_set_cond close bind
echo "PLASMA_TEST=${PLASMA_TEST}"
ldd "${PLASMA_TEST}" | grep -E 'plasma|openblas|mkl|gomp|iomp'
echo "git: $(git -C "${PB}" rev-parse --short HEAD) $(git -C "${PB}" branch --show-current)"
OMP_NUM_THREADS=8 numactl "${NUMACTL_ARGS[@]}" "${PLASMA_TEST}" dgeqrf --dim=1024x1024 --nb=64 --ib=16 --test=n
echo "（上の行の3列目が Time、4列目が Gflop/s であること）"
echo; echo "# preflight 終わり"
