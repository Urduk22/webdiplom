import sqlite3
conn = sqlite3.connect("surveys.db")
try:
    conn.execute("ALTER TABLE surveys ADD COLUMN public_id VARCHAR(10)")
    print("Колонка добавлена")
except sqlite3.OperationalError:
    print("Колонка уже существует")
conn.close()