"""共通：データの場所と、QR のタスク数・η理論。/home/ryo/Download/epyc は読むだけ。"""
from pathlib import Path
import math

EPYC = Path("/home/ryo/Download/epyc")
D11 = EPYC / "epyc_20261111"
B_CSV = D11 / "epyc_s1_smt-off_thread-scaling_20261111_001012" / "thread_scaling.csv"
C1_CSV = D11 / "epyc_s1_smt-off_task-overhead_20261111_014423" / "task_overhead.csv"
C2_CSV = D11 / "epyc_s1_smt-off_task-overhead_20261111_021347" / "task_overhead.csv"
B10_CSV = EPYC / "epyc_s1_smt-off_thread-scaling_20261110_190457" / "thread_scaling.csv"
C10_CSV = EPYC / "epyc_s1_smt-off_task-overhead_20261110_201904" / "task_overhead.csv"
OUT = Path(__file__).resolve().parent.parent / "data"


def ntasks(size, nb):
    n = math.ceil(size / nb)
    return n * (n + 1) * (2 * n + 1) // 6


def eta(nb, size, p):
    """η理論（c = √7.5, k = 2）"""
    x = math.sqrt(7.5 * p) * nb / size
    return 1.0 / (1.0 + x * x)


def qr_time(size, gflops):
    return 4.0 / 3.0 * size**3 / (gflops * 1e9)
