import sqlite3
from config import Config

databases = [
    Config.DATABASE_PATH
]

for db in databases:
    print()
    print("==============================")
    print("DATABASE:", db)
    print("==============================")

    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)

        tables = cursor.fetchall()

        if tables:
            for table in tables:
                print(table[0])
        else:
            print("NO TABLES FOUND")

        conn.close()

    except Exception as e:
        print("ERROR:", e)