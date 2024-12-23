"""
--- Database Schema ---
CREATE TABLE sections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,    (red)
    parent_id  INTEGER,                              (orange)
    title      TEXT DEFAULT '',                      (yellow)
    type       TEXT, -- 'header', 'category', ...    (green)
    questions  TEXT DEFAULT '[]', -- JSON array ...  (blue)
    placement  INTEGER NOT NULL CHECK(placement > 0) -- Ensure ... (magenta)
)
CREATE TABLE sqlite_sequence(name,seq)
CREATE TABLE settings (
    key    TEXT PRIMARY KEY,                         (red)
    value  TEXT                                      (orange)
)
"""
import sqlite3
import argparse
import os
import sys
from colorama import Fore, Style

def truncate_string(s, max_length=20):
    """Truncate a string to a specified length and add ellipsis if needed."""
    if isinstance(s, str):
        return s if len(s) <= max_length else s[:max_length] + "..."
    return s  # Non-string values are returned as-is

def colorize(text, color):
    """Apply color to the text using colorama."""
    return f"{color}{text}{Style.RESET_ALL}"

def dump_database(db_name):
    if not os.path.exists(db_name):
        print(f"{Fore.RED}Error: Database file '{db_name}' not found.{Style.RESET_ALL}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Color palette for headers and content
    colors = [Fore.RED, Fore.LIGHTRED_EX, Fore.YELLOW, Fore.GREEN, Fore.BLUE, Fore.MAGENTA, Fore.CYAN]

    # Keep track of column names and their assigned colors
    column_colors = {}

    # First pass to gather column names and assign colors
    for table_info in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        table_name = table_info[0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        for idx, column_info in enumerate(cursor.fetchall()):
            column_name = column_info[1]
            if column_name not in column_colors:
                column_colors[column_name] = colors[idx % len(colors)]

    # Dump the schema
    print(colorize("--- Database Schema ---", Fore.CYAN))
    for row in cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'"):
        schema_sql = row[0]
        schema_lines = schema_sql.splitlines()

        for line in schema_lines:
            stripped_line = line.strip()
            if "CREATE TABLE" in stripped_line or stripped_line == ")":
                # Print the CREATE TABLE and closing ')' lines without colorization
                print(line)
            elif any(char in stripped_line for char in [',', '--', ')', 'CHECK']):  # Column definition lines
                # Find the column name
                parts = line.split()
                if parts:
                    col_name = parts[0].strip()
                    if col_name in column_colors:
                        # Colorize just the column name, keep the rest of the line as is
                        colored_line = line.replace(col_name, colorize(col_name, column_colors[col_name]), 1)
                        print(colored_line)
                    else:
                        print(line)
                else:
                    print(line)
            else:
                print(line)

    # Dump the data
    print(colorize("\n--- Table Records ---\n", Fore.CYAN))
    for table_info in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        table_name = table_info[0]
        print(colorize(f"Table: {table_name}", Fore.CYAN))
        
        # Fetch and colorize headers
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column_info[1] for column_info in cursor.fetchall()]
        header_row = [colorize(col, column_colors.get(col, Fore.WHITE)) for col in columns]
        print("Columns:", ", ".join(header_row))
        
        # Fetch and colorize rows
        cursor.execute(f"SELECT * FROM {table_name}")
        for row in cursor.fetchall():
            colored_row = []
            for idx, col in enumerate(row):
                col = truncate_string(col, 20)
                color = column_colors.get(columns[idx], Fore.WHITE)
                colored_row.append(colorize(str(col), color))
            print(", ".join(colored_row))

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dump the contents of an SQLite database file with colorized output.",
        epilog="Example: python db_dump.py -f outline.db"
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        help="Path to the SQLite database file (e.g., outline.db)."
    )
    args = parser.parse_args()

    dump_database(args.file)