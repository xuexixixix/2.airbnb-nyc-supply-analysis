# ============================================================
#  数据库连接配置模板
#
#  使用方法：
#      1. 复制本文件为 config.py
#      2. 填入你本地的真实配置
#      3. config.py 已在 .gitignore 中排除，不会被提交
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "YOUR_PASSWORD_HERE",   # ← 换成你自己的密码
    "database": "airbnb_nyc",
    "charset": "utf8mb4",
}

# SQLAlchemy 连接串（如需 ORM 方式）
# from urllib.parse import quote_plus
# DB_URL = (
#     f"mysql+pymysql://{DB_CONFIG['user']}:{quote_plus(DB_CONFIG['password'])}"
#     f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
#     f"?charset={DB_CONFIG['charset']}"
# )
