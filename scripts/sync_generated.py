#!/usr/bin/env python3
"""
COVERAGE.md / TODO_REMEASURE.md を Obsidian vault にミラーする。

生成元は tileQR_data。vault 側は読むだけ。編集しても次回上書きされる。
先頭に生成元のコミットハッシュと時刻を埋めるので、
tileQR_data の HEAD と比べれば古いかどうかが一目で分かる。

--- なぜ .sh ではなく .py か -------------------------------------------

元は scripts/sync_coverage.sh（bash）だった。Windows からは
`bash scripts/sync_coverage.sh` が WSL の bash.exe を呼ぶため、
WSL 側の systemd セッションが壊れていると `set -o pipefail` の時点で
落ちる。vault の同期は WSL 側でしか使えない状態だった。
Python にすれば Windows / WSL2 / Linux で同じコマンド
（`python scripts/sync_generated.py`）が同じように動く。

--- なぜ COVERAGE.md 専用から複数ファイル対応にしたか --------------------

TODO_REMEASURE.md（再計測が必要な項目。ingest.py の自動生成ではなく手書き）も
vault 側から参照したい要求が出た。ヘッダの生成ロジックと vault 解決は
COVERAGE.md と共通なので、ファイルごとに書き直すと片方だけ直し忘れる。
FILES に (ファイル名, タイトル, 自動生成か) を足すだけで増やせるようにした。

使い方:
    python scripts/sync_generated.py
    python scripts/sync_generated.py /path/to/tileQR_research   # vault を明示
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

# Windows のコンソールは既定で cp932 になり、日本語 print() が文字化けまたは
# UnicodeEncodeError で落ちる。出力先を明示的に UTF-8 へ固定する。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

DATA_ROOT = Path(__file__).resolve().parent.parent

# (ファイル名, タイトル, 生成元での作り方)
# 生成元での作り方が None のものは手書き（ingest.py 等の自動生成ではない）。
FILES = [
    ("COVERAGE.md", "計測カバレッジ", "scripts/ingest.py の自動生成"),
    ("TODO_REMEASURE.md", "再計測が必要な項目", None),
]


def git_short_head(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def git_is_dirty(repo: Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "diff", "--quiet"],
            capture_output=True,
        )
        return out.returncode != 0
    except FileNotFoundError:
        return False


def sync_one(name: str, title: str, how: str | None, dst_dir: Path, commit: str, dirty: str, now: str) -> bool:
    src = DATA_ROOT / name
    if not src.is_file():
        print(f"[ERROR] 生成元が見つかりません: {src}")
        return False

    dst = dst_dir / name
    origin = f"tileQR_data/{name}"
    made_by = f"{how}。" if how else "tileQR_data 側で手書き更新。"
    header = f"""---
title: {title}（ミラー）
generated_at: {now}
source_repo: tileQR_data
source_commit: {commit}
tags: [generated]
---

> [!warning] このファイルはミラーです
> 編集しないでください。次回の `sync_generated.py` 実行で上書きされます。
> 生成元は `{origin}`。{made_by}
>
> **生成元コミット: `{commit}`{dirty}　同期時刻: {now}**
>
> 古いかどうかは `git -C ~/research/tileQR_data rev-parse --short HEAD` と
> 上のハッシュを比べれば分かります。違っていれば作り直してください。

---

"""
    dst.write_text(header + src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[OK] {dst}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=None, help="tileQR_research の場所")
    args = ap.parse_args()

    # vault の場所。引数 > 環境変数 > 隣のディレクトリ の順で解決する
    vault_arg = args.vault or os.environ.get("TILEQR_VAULT") or str(DATA_ROOT.parent / "tileQR_research")
    vault = Path(vault_arg)
    if not vault.is_dir():
        print(f"[ERROR] vault が見つかりません: {vault}")
        print("        引数か TILEQR_VAULT で場所を指定してください。")
        return 1

    dst_dir = vault / "generated"
    dst_dir.mkdir(parents=True, exist_ok=True)

    commit = git_short_head(DATA_ROOT)
    dirty = "（未コミットの変更あり）" if git_is_dirty(DATA_ROOT) else ""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    ok = True
    for name, title, how in FILES:
        ok = sync_one(name, title, how, dst_dir, commit, dirty, now) and ok

    print(f"生成元コミット: {commit}{dirty}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
