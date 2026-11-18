#!/usr/bin/env bash
# =============================================================================
# 1_perf_breakdown.sh — EPYC 7543 で QR の時間の内訳を測る（c0 と τ の切り分け。2026-11-18）
#
#   同じ条件を、別々のプロセスで次の種類に分けて流す（計測自体が時間を変えるため、混ぜない）。
#     plain   素の実行（/usr/bin/time -v で page-faults・context switch・user/sys 時間も取る）
#     ref     plasmatest の既定（--test=y）。11-10・11-11 の計測と同じ形。--test=n で時間が変わらないかの確認
#     perf    perf record（cpu-clock）→ perf script を reduce_perf.py で区分けして CSV にする
#     strace  strace -f -c（システムコールの回数と時間）。遅くなるので別の実行（KINDS=strace）で流す
#   plasmatest は --test=n で流す（ref を除く）。検算（dorgqr・dormqr）が内訳に混ざらないように。
#   1点ごとに新しいプロセス。--repeat は付けない。スレッドは固定（libiomp5 なので KMP_AFFINITY）。
#
#   使い方（plasma-bench の直下で。ブランチ feat/tau-campaign。他の計測と同時に流さない）:
#       S=<このディレクトリ>
#       bash $S/0_preflight.sh            # 先に
#       SESSION=pb scripts/local/run_campaign.sh -- bash $S/1_perf_breakdown.sh    # plain/ref/perf
#       KINDS=strace ROUNDS=3 bash $S/1_perf_breakdown.sh                          # strace（あとで）
#
#   変数（既定）:
#       KINDS      "plain ref perf"
#       THREADS    "32 8"
#       SIZES      "4096 8192"     nb の並び NB_LIST "32 192"、IB_DIV 4（ib = nb/4。11-10・11-11 と同じ）
#       SMALL_SIZE 512             起動だけの条件（size 小・nb 32）。0 で省く
#       ROUNDS     5               TIMEOUT 600（1プロセスの上限秒）
#       MAX_OTHER_CPU 100          開始前に他のユーザーの CPU 使用率の合計がこれを超えたら中止
#       FORCE      0               1 で上の中止を無視（CSV には記録する）
#   結果: results/benchmark/<config>_perf-breakdown_<時刻>/
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MACHINE=epyc7543
PB="${PLASMA_BENCH:-$PWD}"
# shellcheck source=/dev/null
source "${PB}/scripts/hpc/lib/common.sh"

KINDS=${KINDS:-"plain ref perf"}
THREADS=${THREADS:-"32 8"}
SIZES=${SIZES:-"4096 8192"}
NB_LIST=${NB_LIST:-"32 192"}
IB_DIV=${IB_DIV:-4}
SMALL_SIZE=${SMALL_SIZE:-512}
ROUNDS=${ROUNDS:-5}
TIMEOUT=${TIMEOUT:-600}
MAX_OTHER_CPU=${MAX_OTHER_CPU:-100}
FORCE=${FORCE:-0}
PERF_EVENT=${PERF_EVENT:-cpu-clock}
read -r -a KIND_LIST <<< "${KINDS}"
read -r -a THREAD_LIST <<< "${THREADS}"

hpc_setup
other_cpu() { ps -eo user:20,pcpu | awk -v me="$(id -un)" 'NR>1 && $1!=me {s+=$2} END{printf "%.0f", s+0}'; }
oc=$(other_cpu)
if [ "${oc}" -gt "${MAX_OTHER_CPU}" ] && [ "${FORCE}" != 1 ]; then
    echo "[ERROR] 他のユーザーの CPU 使用率の合計が ${oc}%（上限 ${MAX_OTHER_CPU}%）。共用機なので中止。FORCE=1 で無視できる"
    ps -eo user:20,pcpu,etime,args --sort=-pcpu | head -6
    exit 1
fi
for k in "${KIND_LIST[@]}"; do
    case "${k}" in
        plain|ref) [ -x /usr/bin/time ] || { echo "[ERROR] /usr/bin/time が無い"; exit 1; } ;;
        perf)      command -v perf   > /dev/null || { echo "[ERROR] perf が無い。0_preflight.sh の結果を司令塔に渡す"; exit 1; } ;;
        strace)    command -v strace > /dev/null || { echo "[ERROR] strace が無い"; exit 1; } ;;
        *) echo "[ERROR] unknown kind: ${k}"; exit 1 ;;
    esac
done

# 条件（size nb p）の一覧。起動だけの条件（SMALL_SIZE）を最後に足す
CONDS=()
for p in "${THREAD_LIST[@]}"; do
    for s in ${SIZES}; do for nb in ${NB_LIST}; do CONDS+=("${s} ${nb} ${p}"); done; done
    [ "${SMALL_SIZE}" != 0 ] && CONDS+=("${SMALL_SIZE} 32 ${p}")
done

OUTDIR="results/benchmark/${CONFIG}_perf-breakdown_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${OUTDIR}/raw" "${OUTDIR}/perf"
CSV="${OUTDIR}/runs.csv"
echo "round,kind,threads,size,nb,ib,Time_sec,GFlops,freq,other_cpu_before,load1_before,exit,minflt,majflt,vcsw,ivcsw,maxrss_kb,utime,stime,elapsed" > "${CSV}"

echo "===== preflight ====="
MAX_P=$(printf '%s\n' "${THREAD_LIST[@]}" | sort -n | tail -n 1)
hpc_select_nodes "${MAX_P}"
hpc_meta > "${OUTDIR}/meta.txt"
{
    echo
    echo "# === 計測条件 ==="
    echo "KINDS=${KINDS} THREADS=${THREADS} SIZES=${SIZES} NB_LIST=${NB_LIST} IB_DIV=${IB_DIV} SMALL_SIZE=${SMALL_SIZE} ROUNDS=${ROUNDS} TIMEOUT=${TIMEOUT}"
    echo "PERF_EVENT=${PERF_EVENT} other_cpu_at_start=${oc}"
    echo "perf: $(perf --version 2>&1 | head -1)   strace: $(strace -V 2>&1 | head -1)"
    echo "perf_event_paranoid=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null) kptr_restrict=$(cat /proc/sys/kernel/kptr_restrict 2>/dev/null)"
    echo "THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)"
    echo "governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo ?)"
    echo "libplasma md5:"
    for f in $(ldd "${PLASMA_TEST}" | awk '/libplasma/ {print $3}'); do md5sum "${f}"; done
} >> "${OUTDIR}/meta.txt"
for P in "${THREAD_LIST[@]}"; do
    hpc_select_nodes "${P}"
    hpc_set_cond close bind
    hpc_check_cores "${P}"
    hpc_check_affinity "${P}" close "${OUTDIR}/affinity_p${P}.txt"
done
echo "output: ${OUTDIR}"
hpc_snapshot "開始" | tee -a "${OUTDIR}/meta.txt"

# 1 実行。$1=kind $2=round $3=size $4=nb $5=p
run_one() {
    local kind=$1 round=$2 size=$3 nb=$4 P=$5
    local ib=$(( nb / IB_DIV )) tag="${kind}_p${P}_s${size}_nb${nb}_r${round}"
    local raw="${OUTDIR}/raw/${tag}.txt" tv="${OUTDIR}/raw/${tag}.time" freq="" ex=0
    local oc1 ld1
    oc1=$(other_cpu); ld1=$(cut -d' ' -f1 /proc/loadavg)
    hpc_select_nodes "${P}"
    hpc_set_cond close bind
    local -a cmd=(numactl "${NUMACTL_ARGS[@]}" "${PLASMA_TEST}" dgeqrf --dim="${size}x${size}" --nb="${nb}" --ib="${ib}")
    [ "${kind}" != ref ] && cmd+=(--test=n)
    export OMP_NUM_THREADS="${P}"
    case "${kind}" in
        plain|ref)
            timeout "${TIMEOUT}" /usr/bin/time -v -o "${tv}" "${cmd[@]}" > "${raw}" 2>&1 || ex=$? ;;
        perf)
            # 試料の間隔：短い条件は細かく
            if   [ "${size}" -le 1024 ]; then freq=9999
            elif [ "${nb}" -le 64 ] && [ "${size}" -ge 8192 ]; then freq=499
            else freq=1999; fi
            local pd="${OUTDIR}/perf/${tag}.data"
            timeout "${TIMEOUT}" perf record -e "${PERF_EVENT}" -F "${freq}" -o "${pd}" -- "${cmd[@]}" \
                > "${raw}" 2> "${OUTDIR}/perf/${tag}.rec.txt" || ex=$?
            local t_sec
            t_sec=$(awk '$3 ~ /^[0-9]+\.[0-9]+$/ && $4 ~ /^[0-9]+\.[0-9]+$/ {print $3; exit}' "${raw}")
            perf script -i "${pd}" --show-task-events -F comm,tid,time,ip,sym,dso 2> "${OUTDIR}/perf/${tag}.script.err" \
                | tee >( [ "${round}" = 1 ] && gzip -c > "${OUTDIR}/perf/${tag}.script.gz" || cat > /dev/null ) \
                | python3 "${HERE}/reduce_perf.py" --threads "${P}" --time "${t_sec:-0}" --freq "${freq}" \
                      --out "${OUTDIR}/perf/${tag}" || echo "[warn] reduce 失敗: ${tag}" | tee -a "${OUTDIR}/run.log"
            rm -f "${pd}" ;;
        strace)
            timeout "${TIMEOUT}" strace -f -c -o "${OUTDIR}/raw/${tag}.strace.txt" "${cmd[@]}" > "${raw}" 2>&1 || ex=$? ;;
    esac
    [ "${ex}" -ne 0 ] && echo "[warn] 終了コード ${ex}: ${tag}" | tee -a "${OUTDIR}/run.log"
    local t gf
    read -r t gf < <(awk '$3 ~ /^[0-9]+\.[0-9]+$/ && $4 ~ /^[0-9]+\.[0-9]+$/ {print $3, $4; exit}' "${raw}" || true)
    local minflt="" majflt="" vcsw="" ivcsw="" rss="" ut="" st="" el=""
    if [ -f "${tv}" ]; then
        minflt=$(awk -F': ' '/Minor \(reclaiming/ {print $2}' "${tv}")
        majflt=$(awk -F': ' '/Major \(requiring/ {print $2}' "${tv}")
        vcsw=$(awk -F': ' '/Voluntary context/ {print $2}' "${tv}")
        ivcsw=$(awk -F': ' '/Involuntary context/ {print $2}' "${tv}")
        rss=$(awk -F': ' '/Maximum resident/ {print $2}' "${tv}")
        ut=$(awk -F': ' '/User time/ {print $2}' "${tv}")
        st=$(awk -F': ' '/System time/ {print $2}' "${tv}")
        el=$(awk '/Elapsed \(wall clock\)/ {print $NF}' "${tv}")
    fi
    echo "${round},${kind},${P},${size},${nb},${ib},${t:-},${gf:-},${freq},${oc1},${ld1},${ex},${minflt},${majflt},${vcsw},${ivcsw},${rss},${ut},${st},${el}" >> "${CSV}"
    printf "r%d %-6s p%-2d size %5d nb %3d  %8s s  %8s GFlops  other_cpu %s%%  (%d sec)\n" \
        "${round}" "${kind}" "${P}" "${size}" "${nb}" "${t:--}" "${gf:--}" "${oc1}" "${SECONDS}"
}

echo "===== start（条件 ${#CONDS[@]} × 種類 ${#KIND_LIST[@]} × ${ROUNDS} 回）====="
SECONDS=0
nk=${#KIND_LIST[@]}
for round in $(seq 1 "${ROUNDS}"); do
    for c in "${CONDS[@]}"; do
        read -r size nb P <<< "${c}"
        for i in $(seq 0 $(( nk - 1 ))); do
            kind=${KIND_LIST[$(( (i + round) % nk ))]}
            # ref は大きい条件だけ（起動だけの条件では不要）
            [ "${kind}" = ref ] && [ "${size}" = "${SMALL_SIZE}" ] && continue
            run_one "${kind}" "${round}" "${size}" "${nb}" "${P}"
        done
    done
    echo "--- round ${round} 終わり: $(uptime) / other_cpu=$(other_cpu)% ---" | tee -a "${OUTDIR}/run.log"
done
echo "===== end (${SECONDS} sec) ====="
hpc_snapshot "終了" | tee -a "${OUTDIR}/meta.txt"
echo "結果: ${OUTDIR}（これを ~/Download/epyc/ に持ち帰る。perf.data は消してある）"
