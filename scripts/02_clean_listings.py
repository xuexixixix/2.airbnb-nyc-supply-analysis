"""
02_clean_listings.py — listings 表清洗

做什么
    把原始数据洗成「可以直接拿来分析」的版本。
    原始文件保持不动，清洗结果另存一份。

输入
    data/raw/listings.csv.gz          原始数据（只读不改）
输出
    data/processed/listings_clean.csv 清洗后的数据

用法
    python scripts/02_clean_listings.py
"""

from pathlib import Path

import pandas as pd

# 项目根目录：当前脚本 → scripts/ → 再上一层
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw" / "listings.csv.gz"
OUT = PROJECT_ROOT / "data" / "processed" / "listings_clean.csv"

# 全空的 12 个字段（我们之前验证过：30,259 行全是空值）
EMPTY_COLS = [
    "neighborhood_overview",
    "host_since",
    "host_response_time",
    "host_response_rate",
    "host_acceptance_rate",
    "host_thumbnail_url",
    "host_verifications",
    "neighbourhood",
    "host_total_listings_count",
    "host_neighbourhood",
    "calendar_updated",
    "instant_bookable",
]


def main() -> None:
    # ========================================
    # 第 1 步：读原始数据
    # ========================================
    df = pd.read_csv(RAW)
    print(f"读入原始数据：{df.shape[0]:,} 行 × {df.shape[1]} 列")

    # ========================================
    # 第 2 步：删掉全空列
    # ========================================
    # 先确认这些列真的存在，再删。
    # 万一以后换了数据快照、字段名变了，也不至于直接报错。
    exist = [c for c in EMPTY_COLS if c in df.columns]
    missing = [c for c in EMPTY_COLS if c not in df.columns]
    if missing:
        print(f"⚠️ 以下列不在数据中，跳过：{missing}")

    df = df.drop(columns=exist)
    print(f"删除 {len(exist)} 个全空列后，还剩 {df.shape[1]} 列")

    # ========================================
    # 第 3 步：price 文本转数字
    # ========================================
    # 原始长相："$113.97"     目标：113.97
    # 三步走：去掉 $ 和逗号 → 转数字
    before_na = int(df["price"].isna().sum())

    df["price"] = pd.to_numeric(
        df["price"].astype("string").str.replace(r"[$,]", "", regex=True),
        errors="coerce",
    )

    after_na = int(df["price"].isna().sum())
    print(f"\nprice 转换完成：")
    print(f"  转换前缺失 : {before_na:,}")
    print(f"  转换后缺失 : {after_na:,}")
    print(f"  新增缺失   : {after_na - before_na:,}  ← 原本就写得不规范的脏数据")
    print(f"  价格范围   : ${df['price'].min():.2f} ~ ${df['price'].max():,.2f}")

    # ========================================
    # 第 4 步：存文件
    # ========================================
    # parents=True  ：如果 processed/ 文件夹不存在，自动建
    # exist_ok=True ：如果已经存在，不报错
    OUT.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUT,
        index=False,              # 不把行号写进文件
        encoding="utf-8-sig",     # 带 BOM，Excel 打开不乱码
    )

    print(f"\n已保存：{OUT}")
    print(f"最终：{df.shape[0]:,} 行 × {df.shape[1]} 列")


if __name__ == "__main__":
    main()
