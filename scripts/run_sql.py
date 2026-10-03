"""
run_sql.py — 执行 sql/ 目录下的查询文件

用途
    把 SQL 写进文件（方便存档 / 复用 / 给面试官看），用这个脚本执行。

用法
    python scripts/run_sql.py sql/01_zero_review_by_area.sql

    # 不带参数时，列出所有可用的查询文件
    python scripts/run_sql.py
"""

import sys
from pathlib import Path
from urllib.parse import quote_plus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

# 让 pandas 输出时按中文宽度对齐表头
pd.set_option("display.unicode.east_asian_width", True)
pd.set_option("display.max_rows", 100)
pd.set_option("display.width", 200)


def build_dsn() -> str:
    c = config.DB_CONFIG
    return (
        f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}"
        f"@{c['host']}:{c['port']}/{c['database']}?charset={c['charset']}"
    )


def list_available() -> None:
    print("可用的查询文件：\n")
    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        print("  （sql/ 目录下还没有 .sql 文件）")
        return
    for f in files:
        # 取文件第一行非空注释作为说明
        desc = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("--"):
                desc = line.lstrip("- ").strip()
                break
        print(f"  {f.relative_to(PROJECT_ROOT)}")
        if desc:
            print(f"      {desc}")
    print(f"\n用法：python scripts/run_sql.py sql/<文件名>.sql")


def main() -> None:
    if len(sys.argv) < 2:
        list_available()
        return

    sql_file = Path(sys.argv[1])
    if not sql_file.is_absolute():
        sql_file = PROJECT_ROOT / sql_file

    if not sql_file.exists():
        print(f"❌ 找不到文件：{sql_file}")
        list_available()
        sys.exit(1)

    sql = sql_file.read_text(encoding="utf-8")

    print("=" * 70)
    print(f"执行：{sql_file.relative_to(PROJECT_ROOT)}")
    print("=" * 70)

    engine = create_engine(build_dsn())

    # ⚠️ 这里刻意【不用】pd.read_sql(sql, engine)
    #
    # 原因：pandas 会对传入的 SQL 字符串做 % 参数替换。
    # 一旦 SQL 或注释里出现百分号（比如注释写「44% 的房源」），
    # pandas 就会把 % 后面的字当成格式符号，抛出
    #   ValueError: unsupported format character '的'
    #
    # 改成自己执行 + 自己拼 DataFrame，绕开这个坑。
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())
        df = pd.DataFrame(rows, columns=columns)
    except Exception as e:
        print(f"\n❌ 执行失败\n")
        print(f"{type(e).__name__}: {e}")
        print("\n💡 常见原因：")
        print("   - SQL 语法错误（少了逗号、括号不配对、引号用了中文引号）")
        print("   - 字段名写错（可用 SHOW COLUMNS FROM listings; 查看）")
        print("   - 表名写错")
        engine.dispose()
        sys.exit(1)

    print(f"\n返回 {len(df):,} 行 × {len(df.columns)} 列\n")
    print(df.to_string(index=False))
    print()

    engine.dispose()


if __name__ == "__main__":
    main()
