"""
01_verify_metrics.py — 指标口径验证

用途
    在把字段写进指标体系之前，先验证它们的真实含义。
    本项目假定了 estimated_occupancy_l365d 的单位是「间夜数」，
    本脚本负责【证实或推翻】这个假设。

    为什么必须做这一步：
        如果该字段其实是「出租率×100」或「总天数」，那么整套指标树全错。
        而这类错误不会报错 —— 它会一路滑进报告里（silent failure）。

用法
    python scripts/01_verify_metrics.py
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LISTINGS = PROJECT_ROOT / "data" / "raw" / "listings.csv.gz"

SEP = "=" * 70

# 只读需要的列：原表 90 列，这里只要 6 列
COLS = [
    "id",
    "estimated_occupancy_l365d",   # 待验证：是否为间夜数
    "estimated_revenue_l365d",     # 待验证：是否为金额
    "availability_365",            # 对照用：未来可订天数
    "price",                       # 对照用：挂牌价（字符串，需清洗）
    "number_of_reviews_ltm",       # 对照用：近 12 月评论数
]


def section(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


def describe(s: pd.Series, label: str) -> None:
    """打印一个序列的分布，并顺带显示缺失数"""
    print(f"\n>>> {label}")
    print(f"    非空 {s.notna().sum():,} / 共 {len(s):,}   （缺失 {s.isna().sum():,}）")
    print(s.describe().round(2).to_string())


def main() -> None:
    df = pd.read_csv(LISTINGS, usecols=COLS)
    print(f"已载入 listings：{len(df):,} 行 × {len(df.columns)} 列")

    # ==========================================================
    # 验证 1：estimated_occupancy_l365d 的单位
    # ==========================================================
    section("验证 1 · estimated_occupancy_l365d 的单位是什么？")
    occ = df["estimated_occupancy_l365d"]
    describe(occ, "estimated_occupancy_l365d")

    occ_max = occ.max()
    print(f"\n    最大值 = {occ_max}")
    if occ_max <= 365:
        print("    ✅ 判定：上限 ≤ 365 → 单位是【间夜数】，假设成立")
    elif occ_max <= 100:
        print("    ❌ 判定：上限 ≤ 100 → 单位可能是【比率】，指标树需重写")
    else:
        print("    ❌ 判定：超过 365 → 单位存疑，需进一步排查")

    # ==========================================================
    # 验证 2：estimated_revenue_l365d 的量级
    # ==========================================================
    section("验证 2 · estimated_revenue_l365d 是什么量级？")
    rev = df["estimated_revenue_l365d"]
    describe(rev, "estimated_revenue_l365d")
    print(f"\n    中位数 = {rev.median():,.2f}")

    # ==========================================================
    # 验证 3：交叉验证 —— 两个字段相除，应该得到「每晚房价」
    # ==========================================================
    section("验证 3 · 交叉验证（最关键的一步）")

    # 分母为 0 会得到 inf，必须先过滤掉
    mask = occ > 0
    print(f"    occupancy > 0 的房源：{mask.sum():,} / {len(df):,}")

    implied_nightly = df.loc[mask, "estimated_revenue_l365d"] / df.loc[mask, "estimated_occupancy_l365d"]
    describe(implied_nightly, "隐含每晚房价 = revenue ÷ occupancy")

    # 对照：清洗后的挂牌价
    # price 是 "$150.00" 这类字符串，去掉 $ 和逗号后才能转数字
    # errors="coerce" 让无法解析的值变成 NaN，而不是报错中断
    price_clean = pd.to_numeric(
        df["price"].astype("string").str.replace(r"[$,]", "", regex=True),
        errors="coerce",
    )
    describe(price_clean, "对照 · 挂牌价 price（已清洗）")

    # --- 判定 ---
    med_implied = implied_nightly.median()
    med_price = price_clean.median()
    print(f"\n    隐含每晚房价 中位数 = {med_implied:,.2f}")
    print(f"    挂牌价       中位数 = {med_price:,.2f}")
    if med_price > 0:
        print(f"    比值 = {med_implied / med_price:.2f}")

    if 10 < med_implied < 10000:
        print("    ✅ 判定：量级符合【每晚房价】（几十~几千），两个字段的理解都成立")
    else:
        print("    ❌ 判定：量级不像每晚房价，需重新检查字段含义")

    # ==========================================================
    # 验证 4：出租率的分布是否合理
    # ==========================================================
    section("验证 4 · 出租率 = occupancy ÷ 365 的分布")

    occ_rate = occ / 365
    describe(occ_rate, "出租率（分母固定取 365）")

    over_100 = (occ_rate > 1).sum()
    print(f"\n    出租率 > 100% 的房源数：{over_100:,}")
    if over_100 == 0:
        print("    ✅ 判定：无超 100% 的情况，用 365 作分母在本数据上成立")
    else:
        print("    ⚠️ 判定：存在超 100% 的房源 → 分母不应固定为 365")
        print("       可能原因：房源并非全年可订，实际分母应小于 365")
        print("       候选口径：转为用 availability_365 修正，或直接采用官方口径")

    # ==========================================================
    # 汇总
    # ==========================================================
    section("结论汇总")
    print(f"""
    estimated_occupancy_l365d
        最大值 {occ_max}          中位数 {occ.median():.0f}
        → 单位判定：{'间夜数' if occ_max <= 365 else '存疑'}

    estimated_revenue_l365d
        最大值 {rev.max():,.0f}      中位数 {rev.median():,.0f}
        → 量级判定：{'金额' if rev.max() > 1000 else '存疑'}

    隐含每晚房价（revenue ÷ occupancy）
        中位数 {med_implied:,.2f}
        挂牌价中位数 {med_price:,.2f}
        → 交叉验证：{'通过' if 10 < med_implied < 10000 else '未通过'}

    出租率（occupancy ÷ 365）
        中位数 {occ_rate.median():.2%}      超 100% 的房源 {over_100:,} 个
        → 口径判定：{'可用' if over_100 == 0 else '需修正分母'}
    """)


if __name__ == "__main__":
    main()
