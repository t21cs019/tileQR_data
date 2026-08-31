import subprocess
import re
import csv
import argparse

# コマンドを実行してGFLOPS値を取得
def run_time_dgeqrf(size, nb_value, ib_value):
    command = [
        '/home/kubota/Library/plasma-17.1/test/test',
        'dgeqrf',
        f'--m={size}',
        f'--n={size}',
        f'--nb={nb_value}',
        f'--ib={ib_value}'
    ]
    
    # subprocess.run()でコマンドを実行し、出力をキャプチャ
    result = subprocess.run(command, capture_output=True, text=True)
    
    # GFLOPSの値を正規表現で抽出
    match = re.search(
        r"pass\s+([-\d.e]+)\s+([-\d.e]+)\s+([\d.]+)\s+([\d]+)\s+([\d]+)\s+([\d]+)\s+([-\d]+)\s+([-\d]+)\s+([f])\s+([-\d.e]+)",
        result.stdout
    )
    
    if match:
        gflops_value = match.group(3)  # GFLOPSは3番目のグループにあります
        return float(gflops_value)  # floatに変換して返す
    else:
        print(f"nb={nb_value}, ib={ib_value} のGFLOPS値が見つかりませんでした")
        return 0.0  # デフォルト値を返す

# データをCSVに保存（追記モードで書き込み）
def save_to_csv(result_data, output_csv, write_header=False):
    with open(output_csv, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        # ヘッダーを書き込む（最初だけ）
        if write_header:
            csvwriter.writerow(['size', 'nb', 'ib', 'GFlops'])
        csvwriter.writerows(result_data)  # データを追記
    print(f"Data has been written to {output_csv}")

# メイン処理
if __name__ == "__main__":
    # コマンドライン引数の設定
    parser = argparse.ArgumentParser(description="Run dgeqrf benchmark with specified size")
    parser.add_argument(
        "size", 
        type=int, 
        nargs="?", 
        default=4096, 
        help="Matrix size for m and n (default: 4096)"
    )
    args = parser.parse_args()
    size = args.size  # コマンドライン引数で指定された値を取得

    # 動的に出力ファイル名を決定
    output_csv = f'benchmark_dtsmqr_{size}.csv'

    results = []
    write_header = True  # 最初の書き込み時だけヘッダーを書くフラグ

    # nbを2から257までの偶数でループ
    for nb in range(20, 512 + 1, 4):
        # ibを2からnb未満までの偶数でループ
        for ib in range(4, nb//2 + 1, 4):
            GFlops = run_time_dgeqrf(size, nb, ib)
            results.append([size, nb, ib, GFlops])

        # 100の倍数ごとにデータをCSVに保存
        if nb % 10 == 0:  # 十分な頻度で保存するため10の倍数で保存
            save_to_csv(results, output_csv, write_header)
            results.clear()  # 一時データをクリア
            write_header = False  # ヘッダーは最初だけ記録

            print(f"nb={nb} までのデータが記録されました。")

    # 残ったデータを保存（最後のグループ）
    if results:
        save_to_csv(results, output_csv, write_header)
