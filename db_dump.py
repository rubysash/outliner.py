import sqlite3

def dump_database(db_path):
    """Dump the schema and records of the SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n--- Database Schema ---")
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    schema = cursor.fetchall()
    for table in schema:
        print(table[0])

    print("\n--- Table Records ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Columns: {', '.join(columns)}")
        cursor.execute(f"SELECT * FROM {table_name}")
        records = cursor.fetchall()
        for record in records:
            print(record)

    conn.close()

if __name__ == "__main__":
    db_path = "outline.db"  # Update this to the path of your database
    dump_database(db_path)
