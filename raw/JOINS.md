# JOINS

`scripts/assemble.py` が自動生成する。手で編集しない。

分割されていた走査を連結した記録。CSV の列には出所を書けないので、
どのノードのどのファイルが1本にまとまったかはここだけが持つ。

注意: ('qr_sweep', 'epyc_s1_smt-off', 32, 2048) の nb 32-500 は より広い走査の部分集合。走査が途中で切れた周とみなし、連結せず単独で残す (1 本)
注意: ('qr_sweep', 'i7-7700_s1_smt-on', 8, 16384) の nb 32-296 は より広い走査の部分集合。走査が途中で切れた周とみなし、連結せず単独で残す (1 本)
- `i5-8500` size4096 t1 nb 32-768: i5-8500(32-512) + i5-8500(516-768)

## 取り込み時の注意

- aoba_s2_smt-off_ssrfb_size1024_nb32-512_t1.csv: 命名にマッチせず スキップ
- aoba_s2_smt-off_ssrfb_size2048_nb32-512_t1.csv: 命名にマッチせず スキップ
- aoba_s2_smt-off_ssrfb_size4096_nb32-512_t1.csv: 命名にマッチせず スキップ
- aoba_s2_smt-off_ssrfb_size8192_nb32-512_t1.csv: 命名にマッチせず スキップ
- par007_size4096_nb128-128_t1_20260607_231854.csv: nb が1点のみ（128）。プローブとみなし除外
- par007_size4096_nb256-256_t1_20260607_225907.csv: nb が1点のみ（256）。プローブとみなし除外
- par009_size16384_nb256-256_t1_20260615_070514.csv: nb が1点のみ（256）。プローブとみなし除外
- par009_size8192_nb256-256_t1_20260615_061027.csv: nb が1点のみ（256）。プローブとみなし除外
- i3-10100_ssrfb_size4096_nb32-512_th1_t1_20260829_171442 copy.csv: 命名にマッチせず スキップ
- i7-7700_manual_ssrfb_nb32_ib8.csv: 命名にマッチせず スキップ
- i7-7700_size16384_nb32-512_t5_20260728_215809.csv: 名前は t5 だが 2 周を検出（行数 5253）。検出結果を採用
- Ryzen7-5800X-16_benchmark_dtsmqr-trial2.csv: 命名にマッチせず スキップ
- Ryzen7-5800X-16_benchmark_dtsmqr-trial3.csv: 命名にマッチせず スキップ
- Ryzen7-5800X-16_benchmark_dtsmqr-trial4.csv: 命名にマッチせず スキップ
- Ryzen7-5800X-16_benchmark_dtsmqr-trial5.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_2048_trial1.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_2048_trial2.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_2048_trial3.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_2048_trial4.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_2048_trial5.csv: 命名にマッチせず スキップ
- Ryzen7-5800X_16_benchmark_dtsmqr-trial1_4-512.csv: 命名にマッチせず スキップ
- ryzen_manual_ssrfb_nb32_ib8.csv: 命名にマッチせず スキップ
