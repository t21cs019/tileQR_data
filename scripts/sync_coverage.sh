#!/usr/bin/env bash
# =============================================================================
# sync_coverage.sh — COVERAGE.md を Obsidian vault にミラーする
#
# 置き場所: tileQR_data/scripts/sync_coverage.sh
#
# 生成元は tileQR_data。vault 側は読むだけ。編集しても次回上書きされる。
# 先頭に生成元のコミットハッシュと時刻を埋めるので、
# tileQR_data の HEAD と比べれば古いかどうかが一目で分かる。
#
# 使い方:
#   bash scripts/sync_coverage.sh
#   bash scripts/sync_coverage.sh /path/to/tileQR_research   # vault を明示
# =============================================================================
set -euo pipefail

DATA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${DATA_ROOT}/COVERAGE.md"

# vault の場所。引数 > 環境変数 > 隣のディレクトリ の順で解決する
VAULT="${1:-${TILEQR_VAULT:-${DATA_ROOT}/../tileQR_research}}"
DST_DIR="${VAULT}/generated"
DST="${DST_DIR}/COVERAGE.md"

if [ ! -f "${SRC}" ]; then
    echo "[ERROR] 生成元が見つかりません: ${SRC}"
    echo "        先に COVERAGE.md を生成してください。"
    exit 1
fi

if [ ! -d "${VAULT}" ]; then
    echo "[ERROR] vault が見つかりません: ${VAULT}"
    echo "        引数か TILEQR_VAULT で場所を指定してください。"
    exit 1
fi

COMMIT="$(git -C "${DATA_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
DIRTY=""
if ! git -C "${DATA_ROOT}" diff --quiet 2>/dev/null; then
    DIRTY="（未コミットの変更あり）"
fi
NOW="$(date '+%Y-%m-%d %H:%M')"

mkdir -p "${DST_DIR}"

{
    cat <<EOF
---
title: 計測カバレッジ（自動生成）
generated_at: ${NOW}
source_repo: tileQR_data
source_commit: ${COMMIT}
tags: [generated, coverage]
---

> [!warning] このファイルは自動生成です
> 編集しないでください。次回の \`sync_coverage.sh\` 実行で上書きされます。
> 生成元は \`tileQR_data/COVERAGE.md\`。
>
> **生成元コミット: \`${COMMIT}\`${DIRTY}　生成時刻: ${NOW}**
>
> 古いかどうかは \`git -C ~/research/tileQR_data rev-parse --short HEAD\` と
> 上のハッシュを比べれば分かります。違っていれば作り直してください。

---

EOF
    cat "${SRC}"
} > "${DST}"

echo "[OK] ${DST}"
echo "     生成元コミット: ${COMMIT}${DIRTY}"
