"""
00_check_schema.py — 数据画像与 Schema 核对

用途
    在执行任何分析之前，先摸清数据的真实形状。
    输出结果用于核对 docs/数据字典.md 中的假设 —— 文档说有什么列，数据里就真有吗？

用法
    python scripts/00_check_schema.py

输出
    1. 每张表的 shape（行数 × 列数）
    2. 每张表的列名与数据类型
    3. 每张表各列的缺失率（降序）
    4. calendar 表的日期范围
    5. listings 表中完全不可订的房源数量
    6. 三个关键字段的取值分布（抽样）
"""

from pathlib import Path

import pandas as pd

# ============================================================
#  路径配置
#  Path(__file__) 是当前脚本文件；.resolve() 转为绝对路径；
#  .parent 取上一级目录。连用两次 = 项目根目录。
#  这样写的好处：无论从哪个目录执行脚本，路径都对，且不含本机用户名。
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

LISTINGS = RAW_DIR / "listings.csv.gz"
CALENDAR = RAW_DIR / "calendar.csv.gz"
REVIEWS = RAW_DIR / "reviews.csv.gz"

SEP = "=" * 70


def section(title: str) -> None:
    """打印一个带分隔线的标题，让控制台输出可读"""
    print(f"\n{SEP}\n{title}\n{SEP}")


# ============================================================
#  工具函数 1：适合能一次性读进内存的表
# ============================================================
def profile(df: pd.DataFrame, name: str, top_missing: int = 15) -> None:
    """打印一张表的完整画像"""
    section(f"[{name}]  {df.shape[0]:,} 行 × {df.shape[1]} 列")

    print("\n--- 列名与数据类型 ---")
    print(df.dtypes.to_string())

    # isna() 把每个格子变成 True/False，.mean() 求均值 = 缺失占比
    miss = (df.isna().mean() * 100).sort_values(ascending=False)
    miss = miss[miss > 0]  # 只保留有缺失的列

    if miss.empty:
        print("\n--- 缺失率 ---\n无缺失值")
    else:
        # ⚠️ 不要 round(2)：99.996% 会被抹成 100.00%，
        #    而"几乎全空"和"完全全空"是两件不同的事。
        #    同时输出非空数，便于人工确认。
        tbl = pd.DataFrame({
            "非空数": df.notna().sum()[miss.index].astype(int),
            "缺失率%": miss.round(4),
        })
        print(f"\n--- 缺失率（共 {len(miss)} 列有缺失）---")
        print(tbl.head(top_missing).to_string())
        if len(miss) > top_missing:
            print(f"... 另有 {len(miss) - top_missing} 列有缺失，未显示")

    # 单列独立提示：完全无数据的字段（极易被忽视，却影响分析可行性判断）
    empty_cols = [c for c in df.columns if df[c].notna().sum() == 0]
    if empty_cols:
        print(f"\n🚨 共 {len(empty_cols)} 个字段【完全无数据】，相关分析须调整或放弃：")
        for c in empty_cols:
            print(f"   - {c}")


# ============================================================
#  工具函数 2：适合超出内存的大表 —— 分块读取
# ============================================================
def profile_chunked(path: Path, name: str, chunksize: int = 1_000_000) -> None:
    """
    分块统计大表。

    pandas 的 chunksize 参数会把文件切成若干块依次返回，
    每块用完即释放，因此峰值内存只取决于单块大小，与文件总行数无关。
    """
    n_rows = 0
    na_total = None
    dtypes = None
    dates = []  # 只保留每块的最小/最大日期，不保留原始数据

    for chunk in pd.read_csv(path, chunksize=chunksize):
        if dtypes is None:
            dtypes = chunk.dtypes  # 类型只取第一块即可，全表一致
            na_total = chunk.isna().sum()
        else:
            na_total = na_total + chunk.isna().sum()

        n_rows += len(chunk)

        if "date" in chunk.columns:
            # ISO 格式 (YYYY-MM-DD) 的字符串按字典序排序结果与按日期排序一致，
            # 所以这里不必转成 datetime，省一次全表转换的开销。
            dates.append((chunk["date"].min(), chunk["date"].max()))

    section(f"[{name}]  {n_rows:,} 行（分块读取）")

    print("\n--- 列名与数据类型 ---")
    print(dtypes.to_string())

    miss = (na_total / n_rows * 100).sort_values(ascending=False)
    miss = miss[miss > 0]
    if miss.empty:
        print("\n--- 缺失率 ---\n无缺失值")
    else:
        print(f"\n--- 缺失率（共 {len(miss)} 列有缺失）---")
        print(miss.round(2).to_string())

    if dates:
        print(f"\n--- 日期范围 ---")
        print(f"{min(d[0] for d in dates)}  ~  {max(d[1] for d in dates)}")


# ============================================================
#  主流程
# ============================================================
def main() -> None:
    # ---------- 1. listings ----------
    listings = pd.read_csv(LISTINGS)
    profile(listings, "listings")

    # ---------- 任务 5：完全不可订的房源 ----------
    section("[listings] 供给有效性初筛")
    total = len(listings)
    dead = int((listings["availability_365"] == 0).sum())
    print(f"房源总数                     : {total:,}")
    print(f"未来 365 天完全不可订的房源   : {dead:,}  ({dead / total * 100:.1f}%)")
    print("\n⚠️ 这只是初筛：availability_365 == 0 也可能是房东临时关闭，")
    print("   需结合 has_availability、number_of_reviews_ltm 等字段进一步判断。")

    # ---------- 任务 6：关键字段取值分布 ----------
    section("[listings] 关键字段取值分布")
    for col in ["room_type", "neighbourhood_group_cleansed", "license"]:
        if col in listings.columns:
            print(f"\n--- {col} （前 5）---")
            print(listings[col].value_counts(dropna=False).head(5).to_string())
        else:
            print(f"\n--- {col} --- 字段不存在，需核对数据字典")

    # ---------- 2. reviews ----------
    # 只读需要的列：省内存，也省掉解析 100 万条评论正文的时间
    reviews = pd.read_csv(REVIEWS, usecols=["listing_id", "date"])
    profile(reviews, "reviews")

    # ---------- 3. calendar（1115 万行，必须分块）----------
    profile_chunked(CALENDAR, "calendar")

    print(f"\n{SEP}\n完成。请将结果与 docs/数据字典.md 核对，差异记入「本地核对记录」。\n{SEP}")


if __name__ == "__main__":
    main()
