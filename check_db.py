import sqlite3, os
db = "flowmind.db"
print("DB exists:", os.path.exists(db))
conn = sqlite3.connect(db)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
conn.close()
