"""analysis/2026-11-11_flow2-dtsmqr-1core/fig_kernel_fit.png の左半分（不老・弐）だけを切り出す（11-11 のスライド p.10 用）。
右半分の EPYC 7543 の size 4096（7月）は MRE 11.5% で β の手続きから除かれる曲線なので、スライドには載せない。
出力：../fig_kernel_fit_flow2.png
"""
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parents[1]
im = Image.open(OUT.parent / "2026-11-11_flow2-dtsmqr-1core/fig_kernel_fit.png")
w, h = im.size
im.crop((0, 0, w // 2, h)).save(OUT / "fig_kernel_fit_flow2.png")
print(w, h, "->", w // 2, h)
