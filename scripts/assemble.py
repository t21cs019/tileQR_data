#!/usr/bin/env python3
"""
raw_data/（手持ちの生ファイル）を raw/ の規約へ組み直す。

やること:
  1. 測定種別の判定   Time_sec 列があれば ssrfb、無ければ qr_sweep
  2. トライアルの分割 1ファイルに複数周ぶん入っているものを1周1ファイルに
  3. curation の適用  curation.yaml に書いた除外・置換を効かせる
  4. セグメントの連結 計測が途中で切れて分かれたものを1本の走査に戻す
  5. プローブの除外   nb が1点しかない試し撃ちを捨てる
  6. 命名と配置       {node}_size{N}_t{threads}_nb{lo}-{hi}_{stamp}[_r{k}].csv

--- 除外が2種類あるのはなぜか ----------------------------------------

このスクリプトが自前で持つ除外（プローブ、部分集合の周）は**データの形から
決まる**。同じ入力なら同じ結果になるのでコードに書ける。

対して「サーマルスロットリングで汚染された」「スレッド数が計画と違う」
「この1点だけ手で測り直した」はデータを見ても分からない。人間の判断が要る。
それは curation.yaml に宣言的に置き、ここは適用するだけにする。

raw/ を手で消して除外を表現すると、次の `make assemble` で黙って元に戻る。
raw/ は raw_data/ から再生成できることが前提のディレクトリなので、
判断もまた再生成の入力側に無ければ保たない。

--- なぜ「等分割」ではなくパターン検出でトライアルを切るか -------------

旧ファイル名の `t5` は**スレッド数ではなくトライアル数**で、グリッドを5周
したぶんが1ファイルに縦に積まれている（行 3963 ごとに同じ (nb,ib) が再出現）。
ところが 5 周ぶん揃っていないファイルがある（epyc size2048 は 19,628 行で
3963 の倍数にならない＝最後の周が途中で切れている）。
行数を周回数で割る実装だと、この手のファイルで境界がずれて全周が壊れる。
そこで (nb,ib) の再出現を境界として検出する。

--- セグメント連結のルール -------------------------------------------

同じ (config, threads, size) に nb 区間の違うグループが複数あるとき、
それらは1本の走査が分割されたものとして連結する。

重複する nb では **nb 区間が広い方のファイルの値を採用する**。
AOBA はバッチ計算機なので、走査を再開すると別のノード割り当てになる。
つまり連結は物理ノードをまたぐ。重複区間で実測 2.7% の差が出ているので、
どちらを採るかは恣意的になりうる。広い方を優先するのは、
主要部分を1ノードで通した測定を基準に据えるという意味。

連結の出所は raw/JOINS.md に記録する。CSV の列には出所を書く場所が
無いため、これが無いと「どのノードのどのファイルが混ざったか」が失われる。

使い方:
    python scripts/assemble.py raw_data            # dry-run
    python scripts/assemble.py raw_data --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import console, curation, paths  # noqa: E402

console.use_utf8()

# raw_data のファイル名。node は _size / _ssrfb の手前まで。
SRC_RE = re.compile(
    r"^(?P<node>[A-Za-z0-9\-]+?)"
    r"(?P<ssrfb>_ssrfb)?"
    r"_size(?P<size>\d+)"
    r"_nb(?P<nb_lo>\d+)-(?P<nb_hi>\d+)"
    r"(?:_th(?P<th>\d+))?"
    r"_t(?P<trials>\d+)"
    r"_(?P<date>\d{8})_(?P<time>\d{6})\.csv$"
)

# ノードごとの計測構成。{短縮名}_s{使用ソケット数}_smt-{on|off}
# smt は plasma-perf の cpus.toml の threads_per_core が根拠
# （1 なら off、2 なら on）。
CONFIG_RULES = {
    # AOBA-B は 64 スレッドなら片ソケット固定、128 なら両ソケット
    "aoba": lambda th: f"aoba-b_s{2 if th > 64 else 1}_smt-off",
    # Xeon Silver 4214, HT off。物理12コア/ソケットなので th<=12 は片ソケット固定。
    "calc": lambda th: f"calc_s{2 if th > 12 else 1}_smt-off",
    "epyc": lambda th: "epyc_s1_smt-on",            # EPYC 7543, threads_per_core=2
    "i3-7100": lambda th: "i3-7100_s1_smt-on",
    "i3-8100": lambda th: "i3-8100_s1_smt-off",
    "i5-7400": lambda th: "i5-7400_s1_smt-off",
    "i5-8500": lambda th: "i5-8500_s1_smt-off",
    # Core i7-7700 は4コア。th<=4 なら SMT 無効。
    # smt-on 固定にしていると、BIOS で SMT を切って測った threads=4 の
    # ファイルが smt-on のディレクトリに紛れ込み、別条件が同じ config に混ざる。
    "i7-7700": lambda th: f"i7-7700_s1_smt-{'off' if th <= 4 else 'on'}",
    # Ryzen 7 5800X は8コア。th<=8 なら SMT 無効。
    # 学部時代のぶんは migrate.py が置いたが、いまの計測機は規約どおりの
    # ファイル名で出すので assemble も読む。
    "ryzen": lambda th: f"ryzen7-5800x_s1_smt-{'off' if th <= 8 else 'on'}",
    # Ryzen 5 7400F は6コア。th<=6 なら SMT 無効、th>6（=12）なら SMT 有効。
    "ryzen5-7400f": lambda th: f"ryzen5-7400f_s1_smt-{'off' if th <= 6 else 'on'}",
    # Core i3-10100 は4コア。th<=4 なら SMT 無効。
    "i3-10100": lambda th: f"i3-10100_s1_smt-{'off' if th <= 4 else 'on'}",
    # Core i7-6900K は8コア。th<=8 なら SMT 無効。
    "dogwood": lambda th: f"dogwood_s1_smt-{'off' if th <= 8 else 'on'}",
}


def config_for(node: str, threads: int) -> str:
    if node.startswith("par"):
        return CONFIG_RULES["aoba"](threads)
    rule = CONFIG_RULES.get(node)
    if rule is None:
        raise ValueError(f"config 規則が未定義のノード: {node}")
    return rule(threads)


def split_trials(df: pd.DataFrame) -> list[pd.DataFrame]:
    """
    1ファイルに積まれた複数周を、(nb,ib) の再出現で切り分ける。

    行数を周回数で割らないのは、最後の周が途中で切れているファイルが
    実在するため。
    """
    seen: set[tuple[int, int]] = set()
    bounds: list[int] = [0]
    for i, (nb, ib) in enumerate(zip(df["nb"].tolist(), df["ib"].tolist())):
        key = (nb, ib)
        if key in seen:
            bounds.append(i)
            seen = set()
        seen.add(key)
    bounds.append(len(df))
    return [
        df.iloc[a:b].reset_index(drop=True)
        for a, b in zip(bounds, bounds[1:])
        if b > a
    ]


def scan(
    src_dir: Path, rules: list[curation.Rule] | None = None
) -> tuple[list[dict], list[str], list[str]]:
    """
    raw_data を読み、トライアル単位に展開する。

    curation.yaml の適用はここで行う。連結（join_segments）より前に効かせるのが
    要点で、除外したトライアルが「セグメントの1本」として数えられると、
    連結の組み合わせ本数がずれて別の周まで巻き添えになる。
    """
    rules = rules if rules is not None else []
    trials: list[dict] = []
    notes: list[str] = []
    curated: list[str] = []

    for path in sorted(src_dir.glob("*/*.csv")):
        m = SRC_RE.match(path.name)
        if not m:
            notes.append(f"{path.name}: 命名にマッチせず スキップ")
            continue

        try:
            df = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{path.name}: 読めない — {exc}")
            continue
        if df.empty:
            notes.append(f"{path.name}: 空ファイル スキップ")
            continue

        kind = "ssrfb" if "Time_sec" in df.columns else "qr_sweep"

        if df["threads"].nunique() != 1 or df["size"].nunique() != 1:
            notes.append(f"{path.name}: threads/size が混在 スキップ")
            continue
        threads = int(df["threads"].iloc[0])
        size = int(df["size"].iloc[0])

        # 名前の th{N} は実データと一致するはず。ずれたら実データを採る。
        if m.group("th") and int(m.group("th")) != threads:
            notes.append(
                f"{path.name}: 名前の th{m.group('th')} と実データ {threads} が不一致。"
                "実データを採用"
            )

        if df["nb"].nunique() <= 1:
            notes.append(
                f"{path.name}: nb が1点のみ（{df['nb'].iloc[0]}）。"
                "プローブとみなし除外"
            )
            continue

        parts = split_trials(df)
        declared = int(m.group("trials"))
        if len(parts) != declared:
            notes.append(
                f"{path.name}: 名前は t{declared} だが {len(parts)} 周を検出"
                f"（行数 {len(df)}）。検出結果を採用"
            )

        node = m.group("node")
        # qr_sweep だけ config を持つ。curation.yaml から config 単位で
        # 指定できるように、ここで解決してトライアルに載せておく。
        config = config_for(node, threads) if kind == "qr_sweep" else None

        for k, part in enumerate(parts, start=1):
            trial = {
                "kind": kind,
                "node": node,
                "config": config,
                "threads": threads,
                "size": size,
                "stamp": f"{m.group('date')}-{m.group('time')}",
                "index": k,
                "trial": k,          # curation の match 用（index と同じ値）
                "of": len(parts),
                "src": path.name,
                "df": part,
            }

            kept, log = curation.apply(trial, rules, src_dir)
            curated += log
            if kept is None:
                continue

            nbs = sorted(kept["nb"].unique())
            trial["df"] = kept
            trial["nb_lo"] = int(nbs[0])
            trial["nb_hi"] = int(nbs[-1])
            trial["n_nb"] = len(nbs)
            trial["span"] = int(nbs[-1]) - int(nbs[0])
            trials.append(trial)

    return trials, notes, curated


def load_manifest() -> set[Path]:
    """前回 assemble.py が書き出したファイルの一覧。無ければ空。"""
    if not paths.ASSEMBLED_TXT.exists():
        return set()
    return {
        paths.ROOT / line.strip()
        for line in paths.ASSEMBLED_TXT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def write_manifest(writing: set[Path]) -> None:
    lines = [
        "# ASSEMBLED",
        "# scripts/assemble.py が書き出したファイルの台帳。手で編集しない。",
        "# 次回の --clean はこの一覧に載っていたファイルだけを掃除の対象にする。",
        "# ここに無いファイル（migrate.py の生成物など）には触らない。",
    ]
    lines += [str(p.relative_to(paths.ROOT)).replace("\\", "/")
              for p in sorted(writing, key=str)]
    paths.ASSEMBLED_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stale_files(previous: set[Path], writing: set[Path]) -> list[Path]:
    """
    前回 assemble.py が書き出したが、今回は書かないファイル。

    --- なぜ「自分が前に置いたもの」しか消さないか -----------------------

    raw/qr_sweep には assemble.py の管轄でないものが混ざっている。
    `ryzen7-5800x_s1_smt-on` には、学部時代のファイルを migrate.py が成形した
    `..._nodate_r{k}.csv` と、いまの計測機が規約どおりの名前で出したものが
    同居している。元ファイル（`Ryzen7-5800X_16_2048_trial1.csv` 等）は
    SRC_RE に合わないので assemble.py は読まない。

    ディレクトリ単位で持ち物を決めると、この構成のように**生成元が2つある
    ディレクトリ**で migrate.py のぶんを巻き添えに消してしまう
    （`rm -rf raw/qr_sweep` していた頃と同じ壊れ方）。

    そこで台帳（raw/ASSEMBLED.txt）に載っていたものだけを掃除の対象にする。
    curation で落ちるようになった条件は前回の台帳に載っているので消えるし、
    自分が置いた覚えのないファイルには触らない。
    """
    return [p for p in sorted(previous - writing, key=str) if p.is_file()]


def group_key(t: dict) -> tuple:
    if t["kind"] == "qr_sweep":
        return (t["kind"], config_for(t["node"], t["threads"]), t["threads"], t["size"])
    return (t["kind"], t["node"], t["threads"], t["size"])


def join_segments(trials: list[dict]) -> tuple[list[dict], list[str]]:
    """
    同じ (種別, config, threads, size) の中で nb 区間が違うものを連結する。

    区間グループが1つだけなら、それぞれが独立したトライアル。複数あるなら
    走査が分割されたものとみなし、グループ横断で1本ずつ組み合わせる。
    """
    out: list[dict] = []
    joins: list[str] = []

    for key, group in sorted(
        _by(trials, group_key).items(), key=lambda kv: tuple(map(str, kv[0]))
    ):
        segments = _by(group, lambda t: (t["nb_lo"], t["nb_hi"]))

        if len(segments) == 1:
            out.extend(group)
            continue

        # 幅の広いセグメントから順に並べる。重複 nb はこの順で先勝ち。
        candidates = sorted(segments.values(), key=lambda ts: -ts[0]["span"])

        # 走査が途中で切れただけの周は「別セグメント」ではない。
        # 既に採った nb の部分集合になっているものは連結せず単独で残す。
        # （例: t5 のうち最後の1周だけ nb 500 で切れているファイル。
        #   これを連結すると、完走した周に切れた周を混ぜることになる）
        ordered: list[list[dict]] = []
        covered: set[int] = set()
        for seg in candidates:
            nb_set = set(seg[0]["df"]["nb"].tolist())
            if ordered and nb_set <= covered:
                out.extend(seg)
                joins.append(
                    f"注意: {key} の nb {seg[0]['nb_lo']}-{seg[0]['nb_hi']} は "
                    f"より広い走査の部分集合。走査が途中で切れた周とみなし、"
                    f"連結せず単独で残す ({len(seg)} 本)"
                )
                continue
            ordered.append(seg)
            covered |= nb_set

        if len(ordered) < 2:
            out.extend(ordered[0] if ordered else [])
            continue

        for seg in ordered:
            seg.sort(key=lambda t: (t["stamp"], t["node"], t["index"]))

        n = min(len(seg) for seg in ordered)
        if any(len(seg) != n for seg in ordered):
            joins.append(
                f"注意: {key} はセグメントごとの本数が不揃い "
                f"({[len(s) for s in ordered]})。{n} 本ぶんだけ連結し、余りは単独で残す"
            )

        for i in range(n):
            pieces = [seg[i] for seg in ordered]
            base = pieces[0]  # 最も広いセグメント = 命名と出所の基準

            merged = pd.concat([p["df"] for p in pieces], ignore_index=True)
            before = len(merged)
            merged = merged.drop_duplicates(subset=["nb", "ib"], keep="first")
            merged = merged.sort_values(["nb", "ib"]).reset_index(drop=True)
            dropped = before - len(merged)

            nbs = sorted(merged["nb"].unique())
            joined = dict(base)
            joined.update(
                df=merged,
                nb_lo=int(nbs[0]),
                nb_hi=int(nbs[-1]),
                n_nb=len(nbs),
                joined_from=[p["src"] for p in pieces],
                joined_nodes=[p["node"] for p in pieces],
            )
            out.append(joined)

            joins.append(
                f"- `{joined['node']}` size{joined['size']} t{joined['threads']} "
                f"nb {nbs[0]}-{nbs[-1]}: "
                + " + ".join(
                    f"{p['node']}({p['nb_lo']}-{p['nb_hi']})" for p in pieces
                )
                + (f" — 重複 {dropped} 点は広い方を採用" if dropped else "")
            )

        # 余りは単独トライアルとして残す
        for seg in ordered:
            out.extend(seg[n:])

    return out, joins


def _by(items, keyfn):
    d = defaultdict(list)
    for it in items:
        d[keyfn(it)].append(it)
    return d


def destination_dir(kind: str, node: str, threads: int) -> Path:
    if kind == "qr_sweep":
        return paths.RAW_SWEEP / config_for(node, threads)
    return paths.RAW / kind / node


def destination(t: dict) -> Path:
    parent = destination_dir(t["kind"], t["node"], t["threads"])

    suffix = f"_r{t['index']}" if t["of"] > 1 else ""
    name = (
        f"{t['node']}_size{t['size']}_t{t['threads']}"
        f"_nb{t['nb_lo']}-{t['nb_hi']}_{t['stamp']}{suffix}.csv"
    )
    return parent / name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="raw_data のディレクトリ")
    ap.add_argument("--apply", action="store_true", help="実際に書き出す")
    ap.add_argument(
        "--clean-sweep",
        "--clean",
        dest="clean",
        action="store_true",
        help="今回書き出す先に残っている前回の名残を消す"
        "（改名・除外の取り残しを掃除する。読まなかった構成には触らない）",
    )
    args = ap.parse_args()

    if not args.src.is_dir():
        print(f"エラー: {args.src} がありません", file=sys.stderr)
        return 1

    try:
        rules = curation.load()
    except curation.CurationError as exc:
        print(f"エラー: curation.yaml — {exc}", file=sys.stderr)
        return 1

    try:
        trials, notes, curated = scan(args.src, rules)
    except curation.CurationError as exc:
        print(f"エラー: curation.yaml — {exc}", file=sys.stderr)
        return 1
    print(f"=== 読み込み: {len(trials)} トライアル ===")

    trials, joins = join_segments(trials)
    print(f"=== 連結後: {len(trials)} トライアル ===\n")

    by_dest = _by(trials, lambda t: destination(t).parent)
    for parent in sorted(by_dest, key=str):
        rel = parent.relative_to(paths.ROOT)
        print(f"{rel}  ({len(by_dest[parent])} ファイル)")

    collisions = _by(trials, destination)
    dup = {k: v for k, v in collisions.items() if len(v) > 1}
    if dup:
        print(f"\n=== 出力名の衝突 ({len(dup)}) ===")
        for k, v in dup.items():
            print(f"  ! {k.name}: {len(v)} 本 — {[t['src'] for t in v]}")

    if joins:
        print(f"\n=== 連結 ({len(joins)}) ===")
        for j in joins:
            print(f"  {j}")

    if curated:
        print(f"\n=== curation.yaml の適用 ({len(curated)}) ===")
        for c in curated:
            print(f"  {c}")

    stale = curation.unused(rules)
    if stale:
        print(f"\n=== 当たらなかった curation ルール ({len(stale)}) ===")
        for r in stale:
            print(f"  ! [{r.id}] {r.describe()}")
        print(
            "  再計測が済んで元データを差し替えたなら、ルールを消してください。"
            "残っていると新しい計測が黙って除外され続けます。"
        )

    if notes:
        print(f"\n=== 注意 ({len(notes)}) ===")
        for n in notes:
            print(f"  ! {n}")

    # 除外したファイルは「書き出さない」だけでは消えない。前回の assemble が
    # 残したものが raw/ に居座り、除外したつもりのデータが derived まで通る。
    stale = stale_files(load_manifest(), set(collisions))
    if stale:
        print(f"\n=== 前回の名残 ({len(stale)}) ===")
        for csv in stale:
            print(f"  - {csv.relative_to(paths.ROOT)}")
        if not args.clean:
            print("  消すには --clean を付けてください。")

    if not args.apply:
        print("\n(dry-run。書き出すには --apply)")
        return 1 if dup else 0

    if dup:
        print("\n衝突があるため中止。", file=sys.stderr)
        return 1

    if args.clean:
        emptied = {csv.parent for csv in stale}
        for csv in stale:
            csv.unlink()
        # 除外で空になったディレクトリは残さない。中身が無いのに
        # ディレクトリだけあると「測ったはずだが読めていない」に見える。
        for parent in sorted(emptied, key=str):
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()

    cols_of = {
        "qr_sweep": ["threads", "size", "nb", "ib", "GFlops"],
        "ssrfb": ["threads", "size", "nb", "ib", "Time_sec", "GFlops"],
    }
    for t in trials:
        dest = destination(t)
        dest.parent.mkdir(parents=True, exist_ok=True)
        t["df"][cols_of[t["kind"]]].to_csv(dest, index=False)

    manifest = ["# JOINS", "", "`scripts/assemble.py` が自動生成する。手で編集しない。",
                "", "分割されていた走査を連結した記録。CSV の列には出所を書けないので、",
                "どのノードのどのファイルが1本にまとまったかはここだけが持つ。", ""]
    manifest += joins if joins else ["- 連結なし"]
    if notes:
        manifest += ["", "## 取り込み時の注意", ""] + [f"- {n}" for n in notes]
    paths.JOINS_MD.write_text("\n".join(manifest) + "\n", encoding="utf-8")

    write_curation_md(rules, curated)
    write_manifest(set(collisions))

    print(f"\n{len(trials)} ファイルを書き出しました。")
    print(f"連結の記録:   {paths.JOINS_MD.relative_to(paths.ROOT)}")
    print(f"除外の記録:   {paths.CURATION_MD.relative_to(paths.ROOT)}")
    print(f"置いたものの台帳: {paths.ASSEMBLED_TXT.relative_to(paths.ROOT)}")
    return 0


def write_curation_md(rules: list[curation.Rule], applied: list[str]) -> None:
    """
    curation.yaml のどのルールが何件に効いたかを raw/ に残す。

    raw/ だけを見た人が「なぜ i5-7400 が無いのか」を辿れるようにするため。
    yaml を読めば理由は書いてあるが、実際に何件落ちたかは適用してみないと
    分からないので、結果はこちらに置く。
    """
    lines = [
        "# CURATION",
        "",
        "`scripts/assemble.py` が自動生成する。手で編集しない。",
        "",
        "`curation.yaml` に書いた「機械には判断できない取捨選択」を、",
        "raw_data → raw で実際に適用した結果。理由と再計測の方針は",
        "`curation.yaml` と `TODO_REMEASURE.md` にある。",
        "",
    ]

    for action, title in (("exclude", "raw/ に上げなかったもの"),
                          ("replace", "別ファイルの値で置き換えたもの")):
        subset = [r for r in rules if r.action == action]
        lines += ["", f"## {title}", ""]
        if not subset:
            lines.append("- なし")
            continue
        lines += _table_header(["id", "対象", "当たり", "行数", "since"])
        for r in subset:
            lines.append(
                f"| `{r.id}` | {r.describe()} | {r.hits} | {r.rows:,} | "
                f"{r.since or '—'} |"
            )
        lines.append("")
        for r in subset:
            if r.reason:
                lines.append(f"- **`{r.id}`** — {' '.join(r.reason.split())}")

    stale = curation.unused(rules)
    if stale:
        lines += [
            "",
            "## 当たらなかったルール",
            "",
            "元データを差し替えたなら消すこと。残っていると新しい計測が",
            "黙って除外され続ける。",
            "",
        ]
        lines += [f"- `{r.id}` — {r.describe()}" for r in stale]

    lines += ["", "## 適用のログ", ""]
    lines += [f"- {a}" for a in applied] if applied else ["- なし"]

    paths.CURATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _table_header(cols: list[str]) -> list[str]:
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]


if __name__ == "__main__":
    raise SystemExit(main())
