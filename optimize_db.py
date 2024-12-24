"""
Optimizes the outline.db database focusing on tree operations and deletions
"""
import sqlite3
import sys

def optimize_database(db_path):
    """Add performance optimizations to an existing database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Set PRAGMA settings outside transaction
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        cursor.execute("BEGIN")
        
        # Create composite index for tree operations
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sections_tree 
        ON sections(parent_id, placement, type)
        WHERE parent_id IS NOT NULL
        """)
        
        # Create index for root level items
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sections_root
        ON sections(placement, type)
        WHERE parent_id IS NULL
        """)
        
        # Add trigger for efficient deletion and reordering
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS maintain_placement_delete
        BEFORE DELETE ON sections
        FOR EACH ROW
        BEGIN
            UPDATE sections 
            SET placement = placement - 1 
            WHERE parent_id IS OLD.parent_id 
            AND placement > OLD.placement;
        END;
        """)
        
        cursor.execute("ANALYZE")
        cursor.execute("COMMIT")
        
        print(f"Successfully optimized database: {db_path}")
        
        # Verify optimizations
        cursor.execute("PRAGMA journal_mode")
        print(f"\nJournal mode: {cursor.fetchone()[0]}")
        
        cursor.execute("PRAGMA index_list('sections')")
        indices = cursor.fetchall()
        print("\nCreated indices:")
        for idx in indices:
            print(f"- {idx[1]}")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        cursor.execute("ROLLBACK")
    except Exception as e:
        print(f"Error: {e}")
        cursor.execute("ROLLBACK")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python db_optimize.py <path_to_database>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    optimize_database(db_path)