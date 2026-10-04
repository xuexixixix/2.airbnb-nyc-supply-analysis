"""
03_import_to_mysql.py — 把数据导入 MySQL

做什么
    建表 + 写入数据。支持三张表：
        listings   30,259 行      原始 CSV（已清洗）
        calendar   11,152,576 行  原始 CSV（已排序，无长文本）
        reviews    990,170 行     原始 CSV（只取需要的列）

用法
    python scripts/03_import_to_mysql.py            # 全部导入
    python scripts/03_import_to_mysql.py listings   # 只导某一张

设计要点
    1. 大表必须分批写。MySQL 的 max_allowed_packet（默认 64MB）限制了
       单次发送的数据量，一次提交 1100 万行会让服务器直接掐断连接。
    2. 索引在数据写完之后再建，比写入过程中维护索引快得多。
    3. reviews 只导入需要的列 —— comments 有 99 万条正文，本次分析用不到。
"""

import sys
from pathlib import Path
from urllib.parse import quote_plus

# 项目根目录：当前脚本 → scripts/ → 再上一层
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 把项目根目录加进 Python 的「模块搜索路径」。
# 不加这一行，脚本就找不到根目录下的 config.py —— 因为 Python
# 默认只在【脚本自己所在的文件夹】里找模块，而 config.py 在上一层。
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

PROCESSED = PROJECT_ROOT / "data" / "processed"
RAW = PROJECT_ROOT / "data" / "raw"

# ============================================================
#  建表规则
# ============================================================

# 日期字段：CSV 里是 "2026-06-14" 文本，MySQL 里存成 DATE
DATE_COLS = {
    "last_scraped", "first_review", "last_review", "calendar_last_scraped",
    "price_quote_checkin_date", "price_quote_checkout_date", "date",
}

# t/f 字段：CSV 里是单个字母
BOOL_COLS = {"host_is_superhost", "host_has_profile_pic", "host_identity_verified", "has_availability"}

# 金额字段：用 DECIMAL 而非 DOUBLE，金额不允许精度丢失
DECIMAL_COLS = {
    "price": "DECIMAL(12,2)",
    "price_quote_total_price": "DECIMAL(14,2)",
    "price_quote_price_per_night": "DECIMAL(12,2)",
    "estimated_revenue_l365d": "DECIMAL(14,2)",
}

# 写入批次大小：每次提交多少行
BATCH = 5000

# ============================================================
#  各表的导入配置
# ============================================================

TABLES = {
    "listings": {
        "csv": PROCESSED / "listings_clean.csv",
        "read_kwargs": {},          # 全列读取
        "indexes": [
            ("idx_listings_host", "host_id"),
            ("idx_listings_area", "neighbourhood_group_cleansed"),
            ("idx_listings_geo", "latitude, longitude"),
        ],
    },
    "calendar": {
        "csv": RAW / "calendar.csv.gz",
        # 关键：分批读，峰值内存只取决于单块大小，与总行数无关
        "read_kwargs": {"chunksize": 1_000_000},
        "indexes": [
            ("idx_calendar_listing", "listing_id"),
            # 复合索引：按房源查 + 按日期排序，是 Join 与时间分析的主力
            ("idx_calendar_listing_date", "listing_id, date"),
        ],
    },
    "reviews": {
        "csv": RAW / "reviews.csv.gz",
        # 只取需要的列：comments 有 99 万条正文，本次分析用不到，
        # 不读它可以省下大量内存和导入时间。
        "read_kwargs": {"usecols": ["listing_id", "id", "date", "reviewer_id"]},
        "indexes": [
            ("idx_reviews_listing", "listing_id"),
            ("idx_reviews_date", "date"),
        ],
    },
}


def build_dsn() -> str:
    """拼出 SQLAlchemy 的连接字符串"""
    c = config.DB_CONFIG
    return (
        f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}"
        f"@{c['host']}:{c['port']}/{c['database']}?charset={c['charset']}"
    )


def mysql_type(col: str, series: pd.Series) -> str:
    """根据 pandas 的类型，决定 MySQL 里该用什么类型"""
    if col in DECIMAL_COLS:
        return DECIMAL_COLS[col]
    if col in DATE_COLS:
        return "DATE"
    if col in BOOL_COLS:
        return "CHAR(1)"

    dtype = series.dtype
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "DOUBLE"

    maxlen = series.astype("string").str.len().max()
    if pd.notna(maxlen) and maxlen > 255:
        return "TEXT"
    return "VARCHAR(255)"


def build_ddl(table: str, df: pd.DataFrame) -> str:
    """生成建表语句"""
    lines = [f"  `{c}` {mysql_type(c, df[c])}" for c in df.columns]
    return (
        f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
        + ",\n".join(lines)
        + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
    )


def import_table(engine, table: str, spec: dict) -> None:
    csv_path = spec["csv"]
    read_kwargs = spec["read_kwargs"]

    print(f"\n{'='*60}")
    print(f"导入 {table}   ← {csv_path.name}")
    print(f"{'='*60}")

    # ---------- 1. 取样本看结构，建表 ----------
    if "chunksize" in read_kwargs:
        sample = pd.read_csv(csv_path, nrows=200, **{k: v for k, v in read_kwargs.items()
                                                     if k != "chunksize"})
        print("模式：分块读取（大表）")
    else:
        sample = pd.read_csv(csv_path, **read_kwargs)

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text(build_ddl(table, sample)))
    print(f"建表完成：{len(sample.columns)} 个字段")

    # ---------- 2. 写数据 ----------
    #
    # ⚠️ 必须分批写！
    #   MySQL 的 max_allowed_packet（默认 64MB）限制单次发送的数据量，
    #   超了服务器会直接掐断连接。
    #
    if "chunksize" in read_kwargs:
        total, first = 0, True
        for chunk in pd.read_csv(csv_path, **read_kwargs):
            chunk.to_sql(table, engine, if_exists="append", index=False,
                         method="multi", chunksize=BATCH)
            total += len(chunk)
            print(f"  已写入 {total:>12,} 行", end="\r")
            first = False
        print(f"  已写入 {total:>12,} 行  ✅")
    else:
        sample.to_sql(table, engine, if_exists="append", index=False,
                      method="multi", chunksize=BATCH)
        print(f"写入完成：{len(sample):,} 行")

    # ---------- 3. 建索引 ----------
    # 索引在数据写完之后再建，比边写边维护快得多
    for idx_name, cols in spec["indexes"]:
        print(f"  建索引 {idx_name} ({cols}) ...", end=" ")
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX `{idx_name}` ON `{table}` ({cols})"))
        print("完成")

    # ---------- 4. 验证 ----------
    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
    print(f"✅ MySQL 中实际行数：{n:,}")


def main() -> None:
    engine = create_engine(build_dsn())

    with engine.connect() as conn:
        v = conn.execute(text("SELECT VERSION()")).scalar()
    print(f"已连接 MySQL {v} → 数据库 {config.DB_CONFIG['database']}")

    targets = sys.argv[1:] or list(TABLES)
    for t in targets:
        if t not in TABLES:
            print(f"⚠️ 未知的表名：{t}（可选：{', '.join(TABLES)}）")
            continue
        import_table(engine, t, TABLES[t])

    engine.dispose()
    print("\n全部完成。")


if __name__ == "__main__":
    main()
