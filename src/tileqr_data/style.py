"""
図のスタイル統一。

発表用（スライド）と論文用で要求が違うため、プリセットを分ける。
  slide … 游ゴシック系・線太め・文字大きめ・PNG 高DPI
  paper … セリフ寄り・線細め・PDF/SVG ベクタ

日本語フォントは環境によって入っているものが違うため、
候補を優先順で探して最初に見つかったものを使う。
見つからない場合は警告を出す（豆腐に気づかず発表資料を作るのを防ぐ）。
"""

from __future__ import annotations

import warnings

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 優先順。手元の Windows / mac / Linux サーバのいずれでも通るように並べる。
JP_FONT_CANDIDATES = [
    "Yu Gothic",          # 游ゴシック（発表テンプレートの指定）
    "YuGothic",
    "Hiragino Sans",
    "Noto Sans CJK JP",
    "IPAexGothic",
    "TakaoGothic",
    "MS Gothic",
]

# 研究で扱う軸の色。構成ごとに固定して、資料間で色が入れ替わらないようにする。
CONFIG_COLORS = {
    "aoba-b_s2_smt-off": "#AA4EFF",   # 発表テンプレートのアクセント色
    "aoba-b_s1_smt-off": "#1F77B4",
    "epyc_s1_smt-off": "#2CA02C",
    "i5-8500_s1_smt-off": "#D62728",
}


def _find_jp_font() -> str | None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in JP_FONT_CANDIDATES:
        if name in available:
            return name
    return None


def use(preset: str = "slide") -> None:
    """matplotlib の rcParams をプリセットで上書きする。"""
    if preset not in {"slide", "paper"}:
        raise ValueError(f"未知のプリセット: {preset}")

    jp = _find_jp_font()
    if jp is None:
        warnings.warn(
            "日本語フォントが見つかりません。ラベルが豆腐になります。"
            f" 候補: {JP_FONT_CANDIDATES}",
            stacklevel=2,
        )

    base = {
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "axes.axisbelow": True,
    }

    if preset == "slide":
        base |= {
            "font.family": [jp] if jp else ["sans-serif"],
            "font.size": 14,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "lines.linewidth": 2.2,
            "lines.markersize": 7,
            "figure.figsize": (8.0, 4.5),   # 16:9 に収まる比
        }
    else:  # paper
        base |= {
            "font.family": [jp] if jp else ["serif"],
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "lines.linewidth": 1.4,
            "lines.markersize": 4,
            "figure.figsize": (5.5, 3.4),
        }

    matplotlib.rcParams.update(base)


def color_for(config: str) -> str:
    """構成名から色を引く。未登録ならデフォルトのサイクルに任せる。"""
    return CONFIG_COLORS.get(config, None)


def save(fig, stem: str, outdir=None, preset: str = "slide") -> list:
    """
    スライド用は PNG、論文用は PDF + SVG で出す。
    出力パスのリストを返す。

    既定の出力先は figures/（Git 管理外の探索用）。確定版を作るときは
    outdir に figures_final/{発表単位}/ を渡す。ハードコードしないのは、
    同じスクリプトで探索用と確定版の両方を出せるようにするため。
    """
    from pathlib import Path

    from . import paths

    outdir = Path(outdir) if outdir is not None else paths.FIGURES
    outdir.mkdir(parents=True, exist_ok=True)

    exts = ["png"] if preset == "slide" else ["pdf", "svg"]
    paths = []
    for ext in exts:
        p = outdir / f"{stem}.{ext}"
        fig.savefig(p)
        paths.append(p)
    plt.close(fig)
    return paths
