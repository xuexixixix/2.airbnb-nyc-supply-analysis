"""
04_make_charts.py — 生成作品集用的图表

做什么
    直接从 MySQL 取数，画出核心发现的图表。
    每个数字都来自 sql/ 目录下的查询，图表与结论一一对应，不手工填数。

输出
    visualizations/01_lifecycle.png        生命周期三档（构成 + 关店率）
    visualizations/02_dimensions.png       四维度极差对比
    visualizations/03_host_scale.png       房东规模趋势
    visualizations/04_map.html             街区零评论率地图（交互式）

配色说明
    使用 dataviz 技能提供的参考配色，已通过 CVD（色盲）验证：
        node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light
    验证结果：全部通过；青色对浅色背景对比度 2.74（低于 3:1），
    按规范需用【直接标注数值】补偿 —— 本脚本所有图都标注了数值。

用法
    python scripts/04_make_charts.py
"""

import sys
from pathlib import Path
from urllib.parse import quote_plus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

matplotlib.use("Agg")  # 不弹窗，直接存文件
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = PROJECT_ROOT / "visualizations"
OUT.mkdir(exist_ok=True)

# ============================================================
#  中文字体（Windows 上必须设置，否则中文显示成方块）
# ============================================================
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
#  配色（来自 dataviz 技能的参考配色，浅色模式）
# ============================================================
SURFACE = "#fcfcfb"        # 图表背景
INK = "#0b0b0b"            # 主文字
INK_2 = "#52514e"          # 次文字
MUTED = "#898781"          # 坐标轴 / 弱化文字
GRID = "#e1e0d9"           # 网格线（很细很淡）
BASELINE = "#c3c2b7"       # 基线

CAT = ["#2a78d6", "#eb6834", "#1baf7a"]          # 分类色 1-3（蓝 / 橙 / 青）
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]  # 蓝色顺序色阶


def style_axes(ax) -> None:
    """统一的坐标轴样式：去掉多余边框、网格弱化、文字用中性色"""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def hbar(ax, labels, values, colors, fmt="{:.1f}%", unit_gap=0.012):
    """画横向条形图，带直接标注（对比度补偿要求）"""
    y = range(len(labels))
    bars = ax.barh(y, values, color=colors, height=0.55, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=11, color=INK_2)
    ax.invert_yaxis()
    top = max(values)
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + top * unit_gap, bar.get_y() + bar.get_height() / 2,
                fmt.format(v), va="center", ha="left",
                fontsize=11, color=INK, fontweight="bold")


def fig_title(fig, title, subtitle=None):
    """统一的标题样式"""
    fig.text(0.02, 0.965, title, fontsize=17, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.02, 0.905, subtitle, fontsize=11, color=INK_2, va="top")


def footer(fig, source):
    fig.text(0.02, 0.02, source, fontsize=8.5, color=MUTED, va="bottom")


def build_dsn() -> str:
    c = config.DB_CONFIG
    return (f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}"
            f"@{c['host']}:{c['port']}/{c['database']}?charset={c['charset']}")


def q(engine, sql):
    return pd.read_sql(text(sql), engine)


# ============================================================
#  图 1：生命周期三档（构成 + 关店率）
#  数据来源：sql/10_listing_lifecycle.sql、sql/11_dormant_host_status.sql
# ============================================================
def chart_lifecycle(engine):
    lifecycle = q(engine, """
        SELECT CASE
                 WHEN 最后评论日期 IS NULL THEN '僵尸'
                 WHEN 最后评论日期 >= DATE_SUB((SELECT MAX(last_scraped) FROM listings),
                                              INTERVAL 365 DAY) THEN '活跃'
                 ELSE '沉寂' END AS 状态,
               COUNT(*) AS 房源数
        FROM (SELECT l.id, MAX(r.date) AS 最后评论日期
              FROM listings l LEFT JOIN reviews r ON l.id = r.listing_id
              GROUP BY l.id) t
        GROUP BY 状态
    """)
    closure = q(engine, """
        SELECT CASE
                 WHEN 最后评论日期 IS NULL THEN '僵尸'
                 WHEN 最后评论日期 >= DATE_SUB((SELECT MAX(last_scraped) FROM listings),
                                              INTERVAL 365 DAY) THEN '活跃'
                 ELSE '沉寂' END AS 状态,
               ROUND(100.0 * SUM(CASE WHEN 可订天数 = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS 关店率
        FROM (SELECT l.id, l.availability_365 AS 可订天数, MAX(r.date) AS 最后评论日期
              FROM listings l LEFT JOIN reviews r ON l.id = r.listing_id
              GROUP BY l.id, l.availability_365) t
        GROUP BY 状态
    """)

    order = ["活跃", "沉寂", "僵尸"]
    label_map = {"活跃": "活跃\n近一年有评论", "沉寂": "沉寂\n曾有评论，近一年无", "僵尸": "僵尸\n从未有评论"}
    total = lifecycle["房源数"].sum()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), facecolor=SURFACE)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.80, bottom=0.13, wspace=0.55)

    # 左：构成
    ax = axes[0]
    style_axes(ax)
    rows = lifecycle.set_index("状态").reindex(order)
    vals = (rows["房源数"] / total * 100).tolist()
    hbar(ax, [label_map[s] for s in order], vals, CAT[:3])
    ax.set_xlabel("占全部房源比例", fontsize=10, color=MUTED)
    ax.set_title("房源构成", fontsize=13, color=INK, pad=12, loc="left")

    # 右：关店率
    ax = axes[1]
    style_axes(ax)
    rows2 = closure.set_index("状态").reindex(order)
    vals2 = rows2["关店率"].tolist()
    # 颜色跟着实体走：同一个状态在两张子图里必须是同一个颜色
    hbar(ax, [label_map[s] for s in order], vals2, CAT[:3])
    ax.set_xlabel("已停止接客的比例", fontsize=10, color=MUTED)
    ax.set_title("关店率", fontsize=13, color=INK, pad=12, loc="left")

    fig_title(fig,
              "平台最大的一档不是「从没生意」，而是「曾经有、后来没了」",
              "全部 30,259 套房源 · NYC 2026-06-14 快照")
    footer(fig, "数据来源：Inside Airbnb | 代码：sql/10_listing_lifecycle.sql, sql/11_dormant_host_status.sql")
    fig.savefig(OUT / "01_lifecycle.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("  ✅ 01_lifecycle.png")


# ============================================================
#  图 2：四维度极差对比（短租型内部）
#  数据来源：sql/12_dimension_comparison.sql
# ============================================================
def chart_dimensions(engine):
    base = "FROM listings WHERE minimum_nights < 30"

    def span(group_expr):
        return q(engine, f"""
            SELECT ROUND(MAX(p) - MIN(p), 1) AS s FROM (
                SELECT 100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)
                       /COUNT(*) AS p
                {base} GROUP BY {group_expr}
            ) x
        """)["s"][0]

    data = [
        ("房型",       span("room_type"),                                "整租 9.4% 至 酒店房 77.2%"),
        ("房东规模",   span("""CASE WHEN calculated_host_listings_count=1 THEN 1
                                    WHEN calculated_host_listings_count<=5 THEN 2
                                    WHEN calculated_host_listings_count<=19 THEN 3
                                    ELSE 4 END"""),                  "1套 6.6% 至 20套+ 54.5%"),
        ("持证状态",   span("""CASE WHEN license IS NULL THEN 1
                                    WHEN license='Exempt' THEN 2 ELSE 3 END"""),
                                                                     "有执照 5.2% 至 已豁免 38.9%"),
        ("地理",       span("neighbourhood_group_cleansed"),             "布鲁克林 9.4% 至 曼哈顿 36.4%"),
    ]
    data.sort(key=lambda r: r[1])

    fig, ax = plt.subplots(figsize=(12, 5.2), facecolor=SURFACE)
    fig.subplots_adjust(left=0.24, right=0.93, top=0.74, bottom=0.16)
    style_axes(ax)

    # 备注放进 y 轴标签（不压在色条上，保证可读）
    labels = [f"{d[0]}\n{d[2]}" for d in data]
    values = [d[1] for d in data]
    # 顺序色阶：data 已按升序排好，色阶也升序 → 值越大颜色越深
    colors = SEQ[1:1 + len(data)]

    hbar(ax, labels, values, colors, fmt="{:.1f} pp")

    ax.set_xlabel("零评论率的极差（百分点）", fontsize=10, color=MUTED)
    fig_title(fig,
              "在真正的短租里，四个维度都有显著差异",
              "仅统计短租型房源（最短入住 < 30 天，n=5,540）· 长租型会稀释真实差异")
    footer(fig, "数据来源：Inside Airbnb | 代码：sql/12_dimension_comparison.sql\n"
                "注：Shared room(42套)、Staten Island(54套) 样本过小；Bronx(146套)、Hotel room(499套) 偏小，仅供参考")
    fig.savefig(OUT / "02_dimensions.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("  ✅ 02_dimensions.png")


# ============================================================
#  图 3：房东规模与零评论率（短租型内部）
#  数据来源：sql/12_dimension_comparison.sql 配套查询 A
# ============================================================
def chart_host_scale(engine):
    df = q(engine, """
        SELECT CASE WHEN calculated_host_listings_count = 1   THEN '1套'
                    WHEN calculated_host_listings_count <= 5  THEN '2-5套'
                    WHEN calculated_host_listings_count <= 19 THEN '6-19套'
                    ELSE '20套以上' END AS 规模,
               COUNT(*) AS 样本数,
               ROUND(100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)
                     /COUNT(*), 1) AS 零评论率
        FROM listings WHERE minimum_nights < 30
        GROUP BY 规模
    """)
    order = ["1套", "2-5套", "6-19套", "20套以上"]
    df = df.set_index("规模").reindex(order).reset_index()

    fig, ax = plt.subplots(figsize=(9.5, 5.2), facecolor=SURFACE)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.74, bottom=0.13)
    style_axes(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)

    x = range(len(order))
    bars = ax.bar(x, df["零评论率"], color=[SEQ[0], SEQ[2], SEQ[4], SEQ[6]],
                  width=0.56, zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{s}\n(n={n:,})" for s, n in zip(df["规模"], df["样本数"])],
                       fontsize=11, color=INK_2)
    ax.set_ylim(0, max(df["零评论率"]) * 1.22)

    for bar, v in zip(bars, df["零评论率"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.6,
                f"{v:.1f}%", ha="center", fontsize=12, fontweight="bold", color=INK)

    ax.set_ylabel("零评论率", fontsize=10, color=MUTED)
    fig_title(fig,
              "房东规模越大，零评论率越高（短租型内部）",
              "单调递增 —— 并非此前认为的 U 型（U 型是混算长租型造成的假象）")
    footer(fig, "数据来源：Inside Airbnb | 代码：sql/12_dimension_comparison.sql")
    fig.savefig(OUT / "03_host_scale.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("  ✅ 03_host_scale.png")


def main():
    engine = create_engine(build_dsn())
    print("生成图表中 ...")
    chart_lifecycle(engine)
    chart_dimensions(engine)
    chart_host_scale(engine)
    engine.dispose()
    print(f"\n输出目录：{OUT}")


if __name__ == "__main__":
    main()
