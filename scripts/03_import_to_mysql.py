"""
03_import_to_mysql.py — 把清洗后的数据导入 MySQL

做什么
    读取 data/processed/ 下的 CSV，在 MySQL 里建表并写入数据。

    本脚本先导入 listings（3 万行，很快）。
    calendar（1115 万行）单独处理，因为要特殊优化。

用法
    python scripts/03_import_to_mysql.py
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

import config  # noqa: E402  （必须放在 sys.path 设置之后）
import pandas as pd
from sqlalchemy import create_engine, text

PROCESSED = PROJECT_ROOT / "data" / "processed"

# ============================================================
#  特殊字段的类型指定
#  —— 不加这些的话，pandas 的类型推断会把数字都变成 DOUBLE、日期都变成字符串
# ============================================================

# 日期字段：CSV 里是 "2026-06-14" 这种文本，MySQL 里应该存成真正的 DATE
DATE_COLS = {
    "last_scraped",
    "first_review",
    "last_review",
    "calendar_last_scraped",
    "price_quote_checkin_date",
    "price_quote_checkout_date",
}

# t/f 字段：CSV 里是单个字母，MySQL 用 CHAR(1)
BOOL_COLS = {
    "host_is_superhost",
    "host_has_profile_pic",
    "host_identity_verified",
    "has_availability",
}

# 金额字段：用 DECIMAL 而不是 DOUBLE —— 金额不允许精度丢失
DECIMAL_COLS = {
    "price": "DECIMAL(12,2)",
    "price_quote_total_price": "DECIMAL(14,2)",
    "price_quote_price_per_night": "DECIMAL(12,2)",
    "estimated_revenue_l365d": "DECIMAL(14,2)",
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
    # 1) 有特殊指定的，优先用指定的
    if col in DECIMAL_COLS:
        return DECIMAL_COLS[col]
    if col in DATE_COLS:
        return "DATE"
    if col in BOOL_COLS:
        return "CHAR(1)"

    # 2) 没指定的，按 pandas 类型推断
    dtype = series.dtype
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    if pd.api.types.is_float_dtype(dtype):
        return "DOUBLE"

    # 3) 文本字段：太长的用 TEXT，其余用 VARCHAR
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


def import_table(engine, table: str, csv_path: Path, chunksize: int | None = None) -> None:
    """把一个 CSV 导入 MySQL"""
    print(f"\n{'='*60}")
    print(f"导入 {table}")
    print(f"{'='*60}")

    if chunksize:
        df = pd.read_csv(csv_path, nrows=200)  # 只读一小段，用来看结构
        print(f"（大表模式，将分块写入）")
    else:
        df = pd.read_csv(csv_path)

    # --- 建表 ---
    ddl = build_ddl(table, df)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text(ddl))
    print(f"建表完成：{len(df.columns)} 个字段")

    # --- 写入数据 ---
    #
    # ⚠️ 必须分批写！
    #   MySQL 有个参数叫 max_allowed_packet（默认 64MB），意思是
    #   「一次发送的数据不能超过 64MB」。超了服务器会直接掐断连接。
    #   3 万行 × 78 列（含长文本）一次发过去远超这个限制。
    #
    #   解法：chunksize=1000 → 每 1000 行发一次，单次体量很小。
    #
    BATCH = 1000
    if chunksize:
        total = 0
        for chunk in pd.read_csv(csv_path, chunksize=chunksize):
            chunk.to_sql(table, engine, if_exists="append", index=False,
                         method="multi", chunksize=BATCH)
            total += len(chunk)
            print(f"  已写入 {total:,} 行", end="\r")
        print(f"\n写入完成：{total:,} 行")
    else:
        df.to_sql(table, engine, if_exists="append", index=False,
                  method="multi", chunksize=BATCH)
        print(f"写入完成：{len(df):,} 行")

    # --- 验证 ---
    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
    print(f"✅ MySQL 中实际行数：{n:,}")


def main() -> None:
    engine = create_engine(build_dsn())

    # 先测连接
    with engine.connect() as conn:
        v = conn.execute(text("SELECT VERSION()")).scalar()
    print(f"已连接 MySQL {v} → 数据库 {config.DB_CONFIG['database']}")

    # listings：3 万行，一次读完
    import_table(engine, "listings", PROCESSED / "listings_clean.csv")

    engine.dispose()
    print("\n完成。下一步：在 MySQL 里写 SQL 查询。")


if __name__ == "__main__":
    main()
