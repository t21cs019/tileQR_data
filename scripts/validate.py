#!/usr/bin/env python3
"""
raw/ 配下の健全性を検証する。push 前に走らせる。

検査項目:
  1. ファイル名が命名規則に沿っているか
  2. 必須列が揃っているか
  3. 1ファイルに threads / size が単一値か（混在は分割が必要）
  4. ファイル名の threads / size が中身と一致するか
     （旧命名で t1 がスレッド数でなかった事故の再発防止）
  5. ib <= nb か
  6. config ディレクトリが machines.yaml の configs にあるか
  7. node が machines.yaml の nodes にあるか
  8. 同一条件の重複がないか
  9. curation.yaml で除外したデータが raw/ に残っていないか
 10. running.yaml が読めるか / 済んだ計測が残っていないか

使い方:
    python scripts/validate.py          # 問題があれば終了コード 1
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import console, curation, io, paths, plan  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble  # noqa: E402  SRC_RE を共有する（命名規約の定義を二重に持たない）

console.use_utf8()


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def dump(self) -> int:
        if self.errors:
            print(f"\n=== エラー ({len(self.errors)}) ===")
            for e in self.errors:
                print(f"  x {e}")
        if self.warnings:
            print(f"\n=== 警告 ({len(self.warnings)}) ===")
            for w in self.warnings:
                print(f"  ! {w}")
        if not self.errors and not self.warnings:
            print("問題なし。")
        return 1 if self.errors else 0


def check_file(
    csv: Path, config: str | None, rep: Report, schema: list[str] | None = None
) -> dict | None:
    meta = io.parse_filename(csv.name)
    if meta is None:
        rep.error(f"{csv.name}: 命名規則に沿っていない")
        return None

    try:
        df = pd.read_csv(csv)
    except Exception as exc:  # noqa: BLE001
        rep.error(f"{csv.name}: 読めない — {exc}")
        return None

    missing = [c for c in (schema or io.SCHEMA) if c not in df.columns]
    if missing:
        rep.error(f"{csv.name}: 必須列が無い {missing}")
        return None

    threads = sorted(df["threads"].unique())
    sizes = sorted(df["size"].unique())

    if len(threads) != 1:
        rep.error(f"{csv.name}: threads が混在 {threads}。分割が必要")
        return None
    if len(sizes) != 1:
        rep.error(f"{csv.name}: size が混在 {sizes}。分割が必要")
        return None

    if threads[0] != meta["threads"]:
        rep.error(
            f"{csv.name}: ファイル名の threads={meta['threads']} と "
            f"中身の {threads[0]} が不一致"
        )
    if sizes[0] != meta["size"]:
        rep.error(
            f"{csv.name}: ファイル名の size={meta['size']} と "
            f"中身の {sizes[0]} が不一致"
        )

    nb_lo, nb_hi = int(df["nb"].min()), int(df["nb"].max())
    if (nb_lo, nb_hi) != (meta["nb_lo"], meta["nb_hi"]):
        rep.warn(
            f"{csv.name}: ファイル名の nb {meta['nb_lo']}-{meta['nb_hi']} と "
            f"実データ {nb_lo}-{nb_hi} が不一致"
        )

    bad = df[df["ib"] > df["nb"]]
    if not bad.empty:
        rep.error(f"{csv.name}: ib > nb の行が {len(bad)} 件ある")

    if df["GFlops"].isna().any():
        rep.warn(f"{csv.name}: GFlops に欠損値がある")
    if (df["GFlops"] <= 0).any():
        rep.warn(f"{csv.name}: GFlops が 0 以下の行がある")

    if meta["stamp"] == "nodate":
        rep.warn(f"{csv.name}: 計測日時が不明（nodate）")

    return {"config": config, "node": meta["node"], "rep": meta["rep"],
            "stamp": meta["stamp"],
            "threads": threads[0], "size": sizes[0], "file": csv.name}


NODE_NAME_RE = re.compile(r"^[A-Za-z0-9\-]+$")


def check_machines(machines: dict, rep: Report) -> None:
    """
    machines.yaml 自体の整合を検査する。

    諸元の食い違いは計測が全部終わってから気づくと手遅れなので、
    push のたびに見る。特に L3 の共有単位は shared-tile cache model の
    C_unit そのものなので、ここがずれるとモデルの当てはめが狂う。
    """
    archs = machines.get("architectures") or {}
    nodes = machines.get("nodes") or {}
    configs = machines.get("configs") or {}

    for name, node in nodes.items():
        # ファイル名の node 部分は [A-Za-z0-9-]+ しか通らない。
        # sources.toml のキー（アンダースコア）をそのまま持ち込む事故を防ぐ。
        if not NODE_NAME_RE.match(name):
            rep.error(
                f"node `{name}`: ファイル名に使えない文字がある。"
                "ハイフンに直し、sources.toml のキーは source_key に書くこと"
            )
        if (node or {}).get("arch") not in archs:
            rep.error(f"node `{name}`: architecture `{(node or {}).get('arch')}` が未定義")

    for name, cfg in configs.items():
        if (cfg or {}).get("arch") not in archs:
            rep.error(f"config `{name}`: architecture `{(cfg or {}).get('arch')}` が未定義")

    for name, a in archs.items():
        per_ccx = a.get("l3_mb_per_ccx")
        cores_per_ccx = a.get("cores_per_ccx")
        per_socket = a.get("l3_mb_per_socket")
        cores_per_socket = a.get("physical_cores_per_socket") or a.get(
            "physical_cores_total"
        )
        if per_ccx and cores_per_ccx and per_socket and cores_per_socket:
            expect = (cores_per_socket // cores_per_ccx) * per_ccx
            if expect != per_socket:
                rep.error(
                    f"architecture `{name}`: L3 が矛盾。"
                    f"{cores_per_socket}コア / {cores_per_ccx}コア per CCX "
                    f"x {per_ccx}MB = {expect}MB だが l3_mb_per_socket={per_socket}MB"
                )


def check_raw_data(machines: dict, rep: Report) -> None:
    """
    raw_data/{config}/ のディレクトリ名と、中のファイルの整合。

    ディレクトリが計測構成の唯一の宣言になったので、ここが間違っていると
    そのまま raw/ の置き場所が間違う。スレッド数からの推測をやめた代わりに、
    宣言が正しいことは検査で担保する。

    実際に起きた事故: dogwood（i7-6900K）のファイルが benchmark_epyc/ に
    置かれていた。ディレクトリ名を誰も見ていなかったので誰も気づかなかった。
    """
    if not paths.RAW_DATA.is_dir():
        return

    configs = machines.get("configs") or {}
    nodes = machines.get("nodes") or {}
    plan_threads = {
        t["config"]: t["threads"] for t in plan.targets_for("qr_sweep") if t.get("config")
    }

    for config_dir in sorted(p for p in paths.RAW_DATA.glob("*") if p.is_dir()):
        config = configs.get(config_dir.name)
        if config is None:
            rep.error(
                f"raw_data/{config_dir.name}/: machines.yaml の configs に無い。"
                "ディレクトリ名は計測構成の宣言なので、configs のキーと一致させること"
            )
            continue

        for csv in sorted(config_dir.glob("*.csv")):
            m = assemble.SRC_RE.match(csv.name)
            if not m:
                continue  # 命名規約外は assemble も読まない（migrate.py の管轄）
            node = m.group("node")

            # ノードとディレクトリが同じ CPU を指しているか。
            entry = nodes.get(node)
            if entry is None:
                rep.error(
                    f"raw_data/{config_dir.name}/{csv.name}: "
                    f"node `{node}` が machines.yaml の nodes に無い"
                )
            elif entry.get("arch") != config.get("arch"):
                rep.error(
                    f"raw_data/{config_dir.name}/{csv.name}: "
                    f"node `{node}` は {entry.get('arch')} だが、"
                    f"ディレクトリは {config.get('arch')} の構成。置き場所が違う"
                )

            # qr_sweep なら、その構成で回すはずのスレッド数と合っているか。
            # ssrfb は th=1 で構成に依存しないので見ない。
            if m.group("ssrfb"):
                continue
            want = plan_threads.get(config_dir.name)
            th = int(m.group("th")) if m.group("th") else None
            if want and th and th != want:
                rep.warn(
                    f"raw_data/{config_dir.name}/{csv.name}: "
                    f"threads={th} だが、この構成の計画は threads={want}。"
                    "置き場所か計測条件のどちらかが違う"
                )


def check_curation(placed: list[dict], rep: Report) -> None:
    """
    除外したはずのデータが raw/ に残っていないか。

    curation.yaml にルールを足す前に assemble した、あるいは raw/ へ手で
    コピーしたファイルは、次の `make assemble --clean` まで残り続ける。
    その間 ingest は普通に読んでしまうので、push 前に必ず弾く。
    """
    try:
        rules = curation.load()
    except curation.CurationError as exc:
        rep.error(f"curation.yaml が読めない — {exc}")
        return

    for info in placed:
        rule = curation.excluding_rule(rules, info)
        if rule is None:
            continue
        rep.error(
            f"{info['file']}: `{rule.id}` で除外したはずのデータが raw/ にある。"
            "`make assemble` を回して作り直すこと"
        )


def check_running(placed: list[dict], rep: Report) -> None:
    """
    running.yaml の書式と、済んだ計測の消し忘れ。

    「データが1本でもある」で警告してはいけない。計測中の条件は途中まで
    データが入っているのが普通で（epyc size16384 は 5本のうち3本目を走らせて
    いる最中）、それを毎回「終わったのでは」と言われると警告が信用されなくなる。

    計画の反復数に届いたときだけ言う。届いているのに走らせ続けているなら、
    終わったのを消し忘れているか、計画の分母がその計測を捉えていないかの
    どちらかで、どちらも知りたい。
    """
    try:
        entries = plan.load_running()
    except plan.RunningError as exc:
        rep.error(f"running.yaml が読めない — {exc}")
        return

    counts: dict[tuple, int] = defaultdict(int)
    for i in placed:
        counts[(i["kind"], i.get("config") or i["node"], i["threads"], i["size"])] += 1

    targets = {
        (kind, t.get("config") or t.get("node"), t["threads"], t["size"]): t
        for kind in ("qr_sweep", "ssrfb", "kernel_dtsmqr")
        for t in plan.targets_for(kind)
    }

    for key, entry in plan.running_keys(entries).items():
        want = targets.get(key)
        got = counts.get(key, 0)
        if not want or got < want["trials"]:
            continue
        kind, machine, threads, size = key
        rep.warn(
            f"running.yaml: {kind} `{machine}` t{threads} size{size} は "
            f"raw/ に {got}/{want['trials']} 本あり計画に届いている"
            f"（{entry.get('since', '?')} 開始）。終わったなら running から消す。"
            "走らせ続けているなら、計画の分母がその計測を捉えていない"
        )


def main() -> int:
    rep = Report()
    machines = io.load_machines()
    check_machines(machines, rep)
    check_raw_data(machines, rep)
    known_configs = set((machines.get("configs") or {}).keys())
    known_nodes = set((machines.get("nodes") or {}).keys())

    seen: dict[tuple, list[str]] = defaultdict(list)
    by_condition: dict[tuple, list[dict]] = defaultdict(list)
    # raw/ に実際に置かれているもの。curation / running の照合に使う。
    placed: list[dict] = []
    n_files = 0

    # --- qr_sweep ---
    for config_dir in sorted(p for p in paths.RAW_SWEEP.glob("*") if p.is_dir()):
        config = config_dir.name
        if config not in known_configs:
            rep.error(
                f"config `{config}` が machines.yaml の configs に無い。"
                "計測条件が記録されないまま埋もれる"
            )
        for csv in sorted(config_dir.glob("*.csv")):
            n_files += 1
            info = check_file(csv, config, rep)
            if info is None:
                continue
            if info["node"] not in known_nodes:
                rep.error(f"node `{info['node']}` が machines.yaml の nodes に無い")
            key = (config, info["node"], info["threads"], info["size"])
            seen[key].append(info["file"])
            by_condition[key].append(info)
            placed.append(dict(info, kind="qr_sweep"))

    # --- ノード直下に置く測定種別（kernel_dtsmqr, ssrfb） ---
    for root, kind, schema in ((paths.RAW_KERNEL, "kernel_dtsmqr", io.SCHEMA),
                               (paths.RAW_SSRFB, "ssrfb", io.SSRFB_SCHEMA)):
        if not root.exists():
            continue
        for node_dir in sorted(p for p in root.glob("*") if p.is_dir()):
            if node_dir.name not in known_nodes:
                rep.error(f"node `{node_dir.name}` が machines.yaml の nodes に無い")
            for csv in sorted(node_dir.glob("*.csv")):
                n_files += 1
                info = check_file(csv, None, rep, schema)
                if info is None:
                    continue
                if info["node"] != node_dir.name:
                    rep.error(
                        f"{csv.name}: ファイル名のノード `{info['node']}` と "
                        f"ディレクトリ `{node_dir.name}` が不一致"
                    )
                placed.append(dict(info, kind=kind))

    check_curation(placed, rep)
    check_running(placed, rep)

    # --- 反復数を計画と突き合わせる ---
    #
    # 1ファイル1トライアルにしたので、同一条件に複数ファイルあるのは
    # 「反復して計測した」という意図どおりの状態。数が並んでいること自体は
    # 異常ではない。異常なのは (a) 計画より多い、(b) 同じ周が二重にある、の2つ。
    # 鍵に node を入れてはいけない。qr_sweep の計画は config 単位で書くので
    # plan 側の node は常に None になり、実測側の鍵（node 入り）と噛み合わない。
    # そのせいでこの検査は一度も発火していなかった。
    targets = {
        (t["config"], t["threads"], t["size"]): t
        for t in plan.targets_for("qr_sweep")
    }
    by_plan_key: dict[tuple, list[str]] = defaultdict(list)
    for (config, _node, threads, size), files in seen.items():
        by_plan_key[(config, threads, size)] += files

    for key, files in sorted(by_plan_key.items(), key=lambda kv: str(kv[0])):
        target = targets.get(key)
        if target and len(files) > target["trials"]:
            config, threads, size = key
            rep.warn(
                f"同一条件 `{config}` t{threads} size{size} に {len(files)} ファイル。"
                f"計画は trials={target['trials']} なので多い"
            )

    for key, infos in sorted(by_condition.items()):
        stamps = [(i["stamp"], i["rep"]) for i in infos]
        dupes = {s for s in stamps if stamps.count(s) > 1}
        if dupes:
            rep.error(
                f"同一条件 {key} に同じ (計測日時, 周) が重複: {sorted(dupes)}。"
                "同じ計測を二重に取り込んでいる"
            )

    print(f"検査したファイル: {n_files}")
    return rep.dump()


if __name__ == "__main__":
    raise SystemExit(main())
