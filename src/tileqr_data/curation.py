"""
raw_data → raw で「機械には判断できない取捨選択」を宣言的に持つ層。

--- なぜ raw/ を手で消すのではいけないか -------------------------------

`assemble.py` が既に持っている除外（nb が1点だけのプローブ、より広い走査の
部分集合になっている周）は、**データの形から決まる**。同じ入力を与えれば
同じ結果になるので、コードに書ける。

一方こちらが扱うのは、データを見ても分からない種類の判断である。

  - サーマルスロットリングで汚染された（計測中の室温は CSV に残らない）
  - スレッド数が計画と違う条件で回してしまった
  - この1点だけ後日ノイズに気づいて手で測り直した
  - 古い計測のうち、この nb 区間だけは使える

これらを「`raw/` から該当ファイルを消す」で表現すると、次の `make assemble`
で黙って元に戻る。`raw/` は `raw_data/` から再生成できることが前提の
ディレクトリなので、判断もまた**再生成の入力側**に無ければ保たない。
それが `curation.yaml` で、このモジュールはその読み込みと適用を持つ。

`TODO_REMEASURE.md` は散文（なぜ・どう測り直すか）を持ち、`curation.yaml` は
それを機械が守れる形にしたもの。両方が要る。片方だけだと、
理由の分からない除外か、誰も守らない約束のどちらかになる。

--- match の書き方 ---------------------------------------------------

トライアル単位の絞り込み:

    kind     qr_sweep | ssrfb
    node     ノード名。リスト可
    config   計測構成（qr_sweep のみ）。リスト可
    threads  スレッド数。リスト可
    size     行列サイズ。リスト可
    src      raw_data 側のファイル名。glob 可（`i5-7400_*.csv`）
    trial    ファイル内の何周目か（1 始まり）。リスト可

行単位の絞り込み（これを書くと、トライアル全体ではなく該当行だけに効く）:

    nb       値・リスト・[lo, hi] の区間
    ib       値・リスト・[lo, hi] の区間

指定したキーの **すべて** に一致したものが対象。`match` が空のルールは
全件に当たってしまうので読み込み時に弾く。未知のキーも弾く
（`kinds:` と書き間違えたルールが黙って全件除外するのが一番こわい）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import pandas as pd
import yaml

from . import paths

# トライアル単位で絞るキー
TRIAL_KEYS = ("kind", "node", "config", "threads", "size", "src", "trial")
# 行単位で絞るキー。1つでもあると、そのルールは行に効く
ROW_KEYS = ("nb", "ib")
KNOWN_KEYS = TRIAL_KEYS + ROW_KEYS

# 置換で書き換えてよい列。条件を表す列（threads/size/nb/ib）は書き換えない。
VALUE_COLS = ("Time_sec", "GFlops")


@dataclass
class Rule:
    id: str
    action: str                       # "exclude" | "replace"
    match: dict
    reason: str = ""
    since: str = ""
    remeasure: str = ""
    source: dict = field(default_factory=dict)   # replace の from
    hits: int = 0                     # 当たったトライアル数
    rows: int = 0                     # 当たった行数

    @property
    def row_scoped(self) -> bool:
        """nb / ib が書いてあるルールは、トライアル全体ではなく行に効く。"""
        return any(k in self.match for k in ROW_KEYS)

    def describe(self) -> str:
        parts = [f"{k}={self.match[k]}" for k in KNOWN_KEYS if k in self.match]
        return ", ".join(parts)


class CurationError(ValueError):
    """curation.yaml の書き方が壊れている。黙って進むと全件除外になりうる。"""


def load(path: Path | None = None) -> list[Rule]:
    """curation.yaml を読む。無ければ空（従来どおりの挙動）。"""
    path = path or paths.CURATION_YAML
    if not path.exists():
        return []

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []

    for action in ("exclude", "replace"):
        for i, entry in enumerate(doc.get(action) or []):
            rid = entry.get("id") or f"{action}[{i}]"
            match = entry.get("match") or {}

            unknown = sorted(set(match) - set(KNOWN_KEYS))
            if unknown:
                raise CurationError(
                    f"`{rid}`: match に未知のキー {unknown}。"
                    f"使えるのは {list(KNOWN_KEYS)}"
                )
            if not match:
                raise CurationError(
                    f"`{rid}`: match が空。全トライアルに当たってしまう"
                )

            source = entry.get("from") or {}
            if action == "replace":
                if not source.get("file"):
                    raise CurationError(f"`{rid}`: replace には from.file が要る")
                if not any(k in match for k in ROW_KEYS):
                    raise CurationError(
                        f"`{rid}`: replace の match には nb / ib が要る。"
                        "トライアル丸ごとの置換は連結の出所が追えなくなる"
                    )
                agg = source.get("agg", "mean")
                if agg not in ("mean", "median", "min", "max"):
                    raise CurationError(f"`{rid}`: 未知の agg `{agg}`")

            rules.append(
                Rule(
                    id=rid,
                    action=action,
                    match=match,
                    reason=str(entry.get("reason", "")).strip(),
                    since=str(entry.get("since", "")),
                    remeasure=str(entry.get("remeasure", "")).strip(),
                    source=source,
                )
            )

    ids = [r.id for r in rules]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise CurationError(f"id が重複している: {dupes}")

    return rules


def _values(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _match_trial(match: dict, trial: dict) -> bool:
    """トライアル単位のキーがすべて一致するか。行単位のキーはここでは見ない。"""
    for key in TRIAL_KEYS:
        if key not in match:
            continue
        got = trial.get(key)
        if key == "src":
            if not any(fnmatch(str(got), p) for p in _values(match[key])):
                return False
            continue
        if got not in _values(match[key]):
            return False
    return True


def _row_mask(match: dict, df: pd.DataFrame) -> pd.Series:
    """
    行単位のキーで行を選ぶ。

    `[lo, hi]` は区間、それ以外の並びは値の集合として扱う。区間で書きたい
    ことの方が多いので2要素は区間に倒す。1点だけ落としたいときは `nb: 32` と
    スカラで書く（`[32, 32]` でも同じ結果になる）。
    """
    mask = pd.Series(True, index=df.index)
    for key in ROW_KEYS:
        if key not in match or key not in df.columns:
            continue
        want = match[key]
        if isinstance(want, (list, tuple)) and len(want) == 2:
            mask &= df[key].between(want[0], want[1])
        else:
            mask &= df[key].isin(_values(want))
    return mask


def _replacement_row(rule: Rule, src_dir: Path, columns) -> dict:
    """
    置換元ファイルを読み、書き戻す値を作る。

    「1回目の呼び出しだけコールドスタートで跳ねる」ため先頭を捨てる、という
    判断が実際に要った（ryzen の手動再計測）。何行捨てたかは drop_first に
    書き、集約は agg に書く。数値そのものを yaml に直書きしないのは、
    「どのファイルの何行をどう畳んだ値か」が失われるため。
    """
    path = src_dir / rule.source["file"]
    if not path.is_file():
        raise CurationError(f"`{rule.id}`: 置換元が見つからない — {path}")

    rep = pd.read_csv(path)
    # 置換先と同じ (nb, ib, threads, size) の行だけを使う。
    # 置換元が複数点を含んでいても取り違えない。
    sel = _row_mask(rule.match, rep)
    for key in ("threads", "size"):
        if key in rule.match and key in rep.columns:
            sel &= rep[key].isin(_values(rule.match[key]))
    rep = rep[sel]

    drop = int(rule.source.get("drop_first", 0))
    if drop:
        rep = rep.iloc[drop:]
    if rep.empty:
        raise CurationError(
            f"`{rule.id}`: 置換元 {path.name} に該当行が残らない"
            f"（drop_first={drop}）"
        )

    agg = rule.source.get("agg", "mean")
    cols = [c for c in VALUE_COLS if c in rep.columns and c in columns]
    if not cols:
        raise CurationError(f"`{rule.id}`: 置換できる列が無い（{list(VALUE_COLS)}）")
    return {c: float(getattr(rep[c], agg)()) for c in cols}


def apply(
    trial: dict, rules: list[Rule], src_dir: Path
) -> tuple[pd.DataFrame | None, list[str]]:
    """
    1トライアルに curation.yaml を適用する。

    戻り値は (残った DataFrame, 記録用メッセージ)。DataFrame が None なら
    「このトライアルは raw/ に上げない」。

    除外を先に、置換を後に適用する。除外された行を置換しても意味がないため。
    """
    df = trial["df"].copy()
    log: list[str] = []
    where = f"{trial['src']} r{trial.get('trial', 1)}"

    for rule in rules:
        if rule.action != "exclude" or not _match_trial(rule.match, trial):
            continue

        if not rule.row_scoped:
            rule.hits += 1
            rule.rows += len(df)
            log.append(f"[{rule.id}] {where}: 除外（{len(df):,} 行）")
            return None, log

        mask = _row_mask(rule.match, df)
        n = int(mask.sum())
        if not n:
            continue
        rule.hits += 1
        rule.rows += n
        df = df[~mask].reset_index(drop=True)
        log.append(f"[{rule.id}] {where}: {n:,} 行を除外（残り {len(df):,} 行）")
        if df.empty:
            log.append(f"[{rule.id}] {where}: 全行が除外されたのでファイルごと落とす")
            return None, log

    for rule in rules:
        if rule.action != "replace" or not _match_trial(rule.match, trial):
            continue
        mask = _row_mask(rule.match, df)
        n = int(mask.sum())
        if not n:
            continue
        for col, value in _replacement_row(rule, src_dir, df.columns).items():
            df.loc[mask, col] = value
        rule.hits += 1
        rule.rows += n
        log.append(
            f"[{rule.id}] {where}: {n} 行を "
            f"{Path(rule.source['file']).name} の値で置換"
        )

    return df, log


def excluding_rule(rules: list[Rule], placed: dict) -> Rule | None:
    """
    `raw/` に既に置かれているファイルが、除外すべきものかどうか。

    assemble を通さず手で置いた、あるいはルールを足す前に assemble した
    ファイルを見つけるために validate.py が使う。raw/ のファイル名からは
    `src` と `trial` が復元できないので、それらに依存するルールは判定しない
    （キーを落とすと match が広がってしまうため）。
    """
    for rule in rules:
        if rule.action != "exclude" or rule.row_scoped:
            continue
        if "src" in rule.match or "trial" in rule.match:
            continue
        if _match_trial(rule.match, placed):
            return rule
    return None


def unused(rules: list[Rule]) -> list[Rule]:
    """
    1件も当たらなかったルール。

    再計測が済んで元データを差し替えたのにルールを消し忘れると、次の計測が
    黙って除外され続ける。当たらないルールは消し忘れとみなして必ず報告する。
    """
    return [r for r in rules if r.hits == 0]
