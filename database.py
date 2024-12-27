import sqlite3
import json
import hashlib

from typing import Dict, Set, Tuple
import time

from manager_encryption import EncryptionManager
from config import DB_NAME, PASSWORD_MIN_LENGTH
from utility import timer

class DatabaseHandler:
    def __init__(self, db_name=DB_NAME, encryption_manager=None):
        self.encryption_manager = encryption_manager
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self._numbering_cache = {}
        self._children_cache = {}
        self.setup_database()

        # search cache
        self._search_cache: Dict[str, Dict[str, str]] = {}
        self._last_cache_update = 0
        self._cache_lifetime = 300  # 5 minutes cache lifetime
        
        # Add indices for common queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_parent 
            ON sections(parent_id, placement)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_type 
            ON sections(type)
        """)

    @timer
    def get_section_level(self, section_id):
        """Get level by counting parents up to root."""
        level = 1
        current_id = section_id
        
        while current_id is not None:
            self.cursor.execute("SELECT parent_id FROM sections WHERE id = ?", (current_id,))
            result = self.cursor.fetchone()
            if result:
                current_id = result[0]
                level += 1
            else:
                break
                
        return level

    def get_section_title(self, section_id):
        """
        Retrieve and decrypt the title of a section by its ID.
        """
        self.cursor.execute("SELECT title FROM sections WHERE id = ?", (section_id,))
        result = self.cursor.fetchone()
        if result and result[0]:
            return self.decrypt_safely(result[0])
        return ""

    @timer
    def setup_database(self):
        """Initialize database schema with core optimizations."""
        
        # Set PRAGMA settings before any other operations
        self.cursor.execute("PRAGMA journal_mode=WAL")
        self.cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Begin transaction for schema changes
        self.cursor.execute("BEGIN")
        
        # Create sections table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT DEFAULT '',
                type TEXT,
                questions TEXT DEFAULT '[]',
                placement INTEGER NOT NULL CHECK(placement > 0)
            )
        """)
        
        # Create settings table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Create optimized indices
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_tree 
            ON sections(parent_id, placement, type)
            WHERE parent_id IS NOT NULL
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_root
            ON sections(placement, type)
            WHERE parent_id IS NULL
        """)
        
        # Add deletion trigger
        self.cursor.execute("""
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
        
        self.cursor.execute("COMMIT")

    @timer
    def set_password(self, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("password", hashed_password),
        )
        self.conn.commit()

    @timer
    def batch_has_children(self, section_ids):
        """Efficiently check multiple sections for children."""
        if not section_ids:
            return {}
        
        placeholders = ','.join('?' * len(section_ids))
        query = f"""
            SELECT DISTINCT parent_id 
            FROM sections 
            WHERE parent_id IN ({placeholders})
        """
        self.cursor.execute(query, section_ids)
        has_children = {id: False for id in section_ids}
        for (parent_id,) in self.cursor.fetchall():
            has_children[parent_id] = True
        return has_children

    @timer
    def invalidate_caches(self):
        """Clear caches when structure changes."""
        self._numbering_cache.clear()
        self._children_cache.clear()

    @timer
    def _get_structure_hash(self):
        """Generate a hash representing the current tree structure."""
        self.cursor.execute("""
            SELECT id, parent_id, placement 
            FROM sections 
            ORDER BY id
        """)
        structure = self.cursor.fetchall()
        return hash(str(structure))

    @timer
    def generate_numbering(self):
        """Generate numbering with caching."""
        cache_key = self._get_structure_hash()  # Hash of current structure
        if cache_key in self._numbering_cache:
            return self._numbering_cache[cache_key]

        numbering_dict = {}
        def recursive_numbering(parent_id=None, prefix=""):
            if parent_id in self._children_cache:
                children = self._children_cache[parent_id]
            else:
                self.cursor.execute("""
                    SELECT id, placement 
                    FROM sections 
                    WHERE parent_id IS ? 
                    ORDER BY placement, id
                """, (parent_id,))
                children = self.cursor.fetchall()
                self._children_cache[parent_id] = children

            for idx, (child_id, _) in enumerate(children, start=1):
                number = f"{prefix}{idx}"
                numbering_dict[child_id] = number
                recursive_numbering(child_id, f"{number}.")

        recursive_numbering()
        self._numbering_cache[cache_key] = numbering_dict
        return numbering_dict

    @timer
    def has_children(self, section_id):
        """
        Check if a section has child sections.
        """
        self.cursor.execute("SELECT 1 FROM sections WHERE parent_id = ? LIMIT 1", (section_id,))
        return self.cursor.fetchone() is not None

    @timer
    def load_children(self, parent_id=None):
        """
        Load child sections of a given parent ID from the database.
        Args:
            parent_id (int or None): The ID of the parent section. If None, load root-level sections.
        Returns:
            list of tuples: Each tuple contains (id, title, parent_id).
        """
        try:
            if parent_id is None:
                self.cursor.execute(
                    """
                    SELECT id, title, parent_id 
                    FROM sections 
                    WHERE parent_id IS NULL 
                    AND title IS NOT NULL 
                    AND title != ''
                    ORDER BY placement, id
                    """
                )
            else:
                self.cursor.execute(
                    """
                    SELECT id, title, parent_id 
                    FROM sections 
                    WHERE parent_id = ? 
                    AND title IS NOT NULL 
                    AND title != ''
                    ORDER BY placement, id
                    """,
                    (parent_id,),
                )
                
            results = self.cursor.fetchall()
            
            # Additional validation to ensure no empty records are returned
            validated_results = []
            for id, title, parent_id in results:
                if id is not None and title is not None:
                    # For encrypted titles, we need to check the content exists
                    if isinstance(title, str) and not title.strip():
                        continue
                    validated_results.append((id, title, parent_id))
                    
            return validated_results
            
        except Exception as e:
            print(f"Error in load_children: {e}")
            return []

    @timer
    def add_section(self, title, section_type, parent_id=None, placement=1):
        """
        Add a new section with encrypted title and default encrypted questions.
        """
        if not isinstance(placement, int) or placement <= 0:
            raise ValueError(f"Invalid placement value: {placement}")

        encrypted_title = self.encryption_manager.encrypt_string(title)
        encrypted_questions = self.encryption_manager.encrypt_string("[]")  # Default to empty JSON array

        self.cursor.execute(
            "INSERT INTO sections (title, type, parent_id, placement, questions) VALUES (?, ?, ?, ?, ?)",
            (encrypted_title, section_type, parent_id, placement, encrypted_questions),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    @timer
    def update_section(self, section_id, title, questions):
        encrypted_title = (
            self.encryption_manager.encrypt_string(title) if title else None
        )
        encrypted_questions = (
            self.encryption_manager.encrypt_string(questions) if questions else None
        )
        #print(f"Updating section ID {section_id} with:")
        #print(f"  Encrypted Title: {encrypted_title}")
        #print(f"  Encrypted Questions: {encrypted_questions}")
        self.cursor.execute(
            "UPDATE sections SET title = ?, questions = ? WHERE id = ?",
            (encrypted_title, encrypted_questions, section_id),
        )
        self.conn.commit()

    @timer
    def change_password(self, old_password, new_password):
        """Change the database encryption password with proper re-encryption."""
        if not self.validate_password(old_password):
            raise ValueError("Current password is incorrect.")
            
        if len(new_password) < PASSWORD_MIN_LENGTH:
            raise ValueError("New password must be at least 14 characters.")
            
        try:
            # Store old encryption manager
            old_encryption_manager = self.encryption_manager
            
            # Create new encryption manager
            new_encryption_manager = EncryptionManager(new_password)
            
            # Start a transaction
            self.cursor.execute("BEGIN TRANSACTION")
            
            # Re-encrypt all data
            self.cursor.execute("SELECT id, title, questions FROM sections")
            sections = self.cursor.fetchall()
            
            update_query = """
                UPDATE sections 
                SET title = ?, questions = ? 
                WHERE id = ?
            """
            
            for section_id, encrypted_title, encrypted_questions in sections:
                new_encrypted_title = None
                new_encrypted_questions = None
                
                try:
                    if encrypted_title:
                        decrypted_title = old_encryption_manager.decrypt_string(encrypted_title)
                        new_encrypted_title = new_encryption_manager.encrypt_string(decrypted_title)
                        
                    if encrypted_questions:
                        decrypted_questions = old_encryption_manager.decrypt_string(encrypted_questions)
                        new_encrypted_questions = new_encryption_manager.encrypt_string(decrypted_questions)
                        
                    self.cursor.execute(update_query, (
                        new_encrypted_title,
                        new_encrypted_questions,
                        section_id
                    ))
                except Exception as e:
                    print(f"Error re-encrypting section {section_id}: {e}")
                    self.conn.rollback()
                    raise RuntimeError(f"Failed to re-encrypt section {section_id}")
            
            # Update password hash in settings
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            self.cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("password", new_hash)
            )
            
            # Commit transaction
            self.conn.commit()
            
            # Update the encryption manager
            self.encryption_manager = new_encryption_manager
            
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to change password: {e}")

    @timer
    def count_descendants(self, section_id):
        """Count all descendants of a section."""
        self.cursor.execute("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM sections WHERE parent_id = ?
                UNION ALL
                SELECT s.id 
                FROM sections s
                INNER JOIN descendants d ON s.parent_id = d.id
            )
            SELECT COUNT(*) FROM descendants
        """, (section_id,))
        return self.cursor.fetchone()[0]

    def delete_section(self, section_id):
        """Delete a section and all its descendants."""
        self.cursor.execute("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM sections WHERE id = ?
                UNION ALL
                SELECT s.id 
                FROM sections s
                INNER JOIN descendants d ON s.parent_id = d.id
            )
            DELETE FROM sections WHERE id IN descendants
        """, (section_id,))
        self.conn.commit()

    def reset_database(self, new_db_name):
        """
        Reset the database connection and initialize a new database.
        """
        try:
            self.conn.close()
            self.db_name = new_db_name
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            self.setup_database()
            self.conn.commit()
        except Exception as e:
            raise RuntimeError(f"Failed to reset database: {e}")

    @timer
    def fix_all_placements(self):
        """Fix placement values to ensure they are consecutive within each level."""
        try:
            # Start transaction
            self.cursor.execute("BEGIN")
            
            # First fix root level sections to be consecutive
            self.cursor.execute(
                """
                WITH RankedSections AS (
                    SELECT id,
                           ROW_NUMBER() OVER (ORDER BY placement, id) as new_placement
                    FROM sections
                    WHERE parent_id IS NULL
                )
                UPDATE sections
                SET placement = (
                    SELECT new_placement
                    FROM RankedSections
                    WHERE RankedSections.id = sections.id
                )
                WHERE parent_id IS NULL
                """
            )
            
            # Then fix children for each parent to be consecutive
            self.cursor.execute(
                "SELECT DISTINCT parent_id FROM sections WHERE parent_id IS NOT NULL"
            )
            parent_ids = [row[0] for row in self.cursor.fetchall()]
            
            for parent_id in parent_ids:
                self.cursor.execute(
                    """
                    WITH RankedChildren AS (
                        SELECT id,
                               ROW_NUMBER() OVER (ORDER BY placement, id) as new_placement
                        FROM sections
                        WHERE parent_id = ?
                    )
                    UPDATE sections
                    SET placement = (
                        SELECT new_placement
                        FROM RankedChildren
                        WHERE RankedChildren.id = sections.id
                    )
                    WHERE parent_id = ?
                    """,
                    (parent_id, parent_id)
                )
            
            # Commit the transaction
            self.conn.commit()
            
            # Clear caches since we modified the structure
            self.invalidate_caches()
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error in fix_all_placements: {e}")
            raise

    @timer
    def fix_placement(self, parent_id):
        """Fix placement values for children of a specific parent."""
        try:
            self.cursor.execute(
                """
                WITH RankedChildren AS (
                    SELECT id,
                           ROW_NUMBER() OVER (ORDER BY placement, id) as new_placement
                    FROM sections
                    WHERE parent_id = ?
                )
                UPDATE sections
                SET placement = (
                    SELECT new_placement
                    FROM RankedChildren
                    WHERE RankedChildren.id = sections.id
                )
                WHERE parent_id = ?
                """,
                (parent_id, parent_id)
            )
            self.conn.commit()
            self.invalidate_caches()
        except Exception as e:
            print(f"Error in fix_placement: {e}")
            self.conn.rollback()

    @timer
    def initialize_placement(self):
        """Initializes and fixes placement values for the entire database."""
        try:
            # First set initial placements based on hierarchy
            self.cursor.execute(
                """
                WITH RECURSIVE section_hierarchy(id, parent_id, level) AS (
                    SELECT id, parent_id, 0 FROM sections WHERE parent_id IS NULL
                    UNION ALL
                    SELECT s.id, s.parent_id, h.level + 1
                    FROM sections s
                    INNER JOIN section_hierarchy h ON s.parent_id = h.id
                )
                SELECT id, ROW_NUMBER() OVER (PARTITION BY parent_id ORDER BY id) AS new_placement
                FROM section_hierarchy
                """
            )
            for row in self.cursor.fetchall():
                self.cursor.execute(
                    "UPDATE sections SET placement = ? WHERE id = ?",
                    (row[1], row[0]),
                )
            self.conn.commit()
            
            # Then ensure they're consecutive using fix_all_placements
            self.fix_all_placements()
            
        except Exception as e:
            print(f"Error in initialize_placement: {e}")
            self.conn.rollback()

    @timer
    def swap_placement(self, item_id1, item_id2):
        """Swap the placement of two items in the database."""
        try:
            # Get current placements
            self.cursor.execute(
                "SELECT placement FROM sections WHERE id = ?", (item_id1,)
            )
            placement1 = self.cursor.fetchone()[0] or 0  # Handle NULL

            self.cursor.execute(
                "SELECT placement FROM sections WHERE id = ?", (item_id2,)
            )
            placement2 = self.cursor.fetchone()[0] or 0  # Handle NULL

            # Perform the swap
            self.cursor.execute(
                "UPDATE sections SET placement = ? WHERE id = ?", (placement2, item_id1)
            )
            self.cursor.execute(
                "UPDATE sections SET placement = ? WHERE id = ?", (placement1, item_id2)
            )

            self.conn.commit()

            # Post-commit verification
            self.cursor.execute(
                "SELECT id, placement FROM sections WHERE id IN (?, ?) ORDER BY id",
                (item_id1, item_id2),
            )
            verification = self.cursor.fetchall()
            for row in verification:
                if (row[0] == item_id1 and row[1] != placement2) or (
                    row[0] == item_id2 and row[1] != placement1
                ):
                    raise RuntimeError(
                        "Post-commit verification failed: Placements do not match expected values."
                    )

        except sqlite3.OperationalError as e:
            print(f"Database is locked: {e}")
            self.conn.rollback()
        except Exception as e:
            print(f"Error in swap_placement: {e}")
            self.conn.rollback()

    @timer
    def get_section_type(self, section_id):
        """Fetch the type of a section by its ID."""
        try:
            self.cursor.execute("SELECT type FROM sections WHERE id = ?", (section_id,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error in get_section_type: {e}")
            return None

    @timer
    def search_sections(self, query):
        """
        Perform a recursive search for sections matching the query in title or questions.
        Returns a tuple of ids_to_show and parents_to_show.
        """
        try:
            self.cursor.execute(
                """
                WITH RECURSIVE parents AS (
                    SELECT id, parent_id, title, questions
                    FROM sections
                    WHERE title LIKE ? OR questions LIKE ?
                    UNION
                    SELECT s.id, s.parent_id, s.title, s.questions
                    FROM sections s
                    INNER JOIN parents p ON s.id = p.parent_id
                )
                SELECT id, parent_id
                FROM parents
                ORDER BY parent_id, id
                """,
                (f"%{query}%", f"%{query}%"),
            )
            matches = self.cursor.fetchall()
            ids_to_show = {row[0] for row in matches}
            parents_to_show = {row[1] for row in matches if row[1] is not None}
            return ids_to_show, parents_to_show
        except Exception as e:
            print(f"Error in search_sections: {e}")
            return set(), set()

    def clean_parent_ids(self):
        """Update any parent_id values that are empty strings to NULL."""
        self.cursor.execute(
            "UPDATE sections SET parent_id = NULL WHERE parent_id = ''"
        )
        self.conn.commit()

    def validate_password(self, password):
        """
        Validate the password and verify decryption capability.
        Returns True only if password hash matches AND test decryption succeeds.
        """
        try:
            # First check the password hash
            self.cursor.execute(
                "SELECT value FROM settings WHERE key = ?", ("password",)
            )
            result = self.cursor.fetchone()
            if not result:
                return False  # No password set
                
            stored_hashed_password = result[0]
            if hashlib.sha256(password.encode()).hexdigest() != stored_hashed_password:
                return False
                
            # Create a temporary encryption manager for validation
            temp_manager = EncryptionManager(password)
            
            # Test encryption/decryption
            test_string = "test_string"
            encrypted = temp_manager.encrypt_string(test_string)
            decrypted = temp_manager.decrypt_string(encrypted)
            
            if decrypted != test_string:
                return False
                
            # If we get here, both the hash matches and encryption works
            self.encryption_manager = temp_manager
            return True
            
        except Exception as e:
            print(f"Password validation error: {e}")
            return False

    def load_database_from_file(self, db_path):
        """Load an existing database file and verify its schema and password."""
        try:
            # First check if the file exists and is a valid SQLite database
            temp_conn = sqlite3.connect(db_path)
            temp_cursor = temp_conn.cursor()
            
            # Check for settings table and password
            temp_cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='settings'
                """
            )
            if not temp_cursor.fetchone():
                temp_conn.close()
                raise ValueError("Invalid database: 'settings' table not found.")
                
            # Check for password in settings
            temp_cursor.execute(
                "SELECT value FROM settings WHERE key = ?",
                ("password",)
            )
            stored_password = temp_cursor.fetchone()
            temp_conn.close()
            
            # If there's a stored password, prompt for it
            if stored_password:
                while True:  # Keep trying until success or user cancels
                    password = simpledialog.askstring(
                        "Database Password",
                        "Enter the password for this database:",
                        show="*"
                    )
                    if not password:
                        raise ValueError("Password entry cancelled.")
                        
                    # Create temporary encryption manager to validate password
                    temp_encryption_manager = EncryptionManager(password)
                    
                    # Try to validate with the new connection
                    self.conn.close()
                    self.db_name = db_path
                    self.conn = sqlite3.connect(self.db_name)
                    self.cursor = self.conn.cursor()
                    
                    if self.validate_password(password):
                        self.encryption_manager = temp_encryption_manager
                        break
                    else:
                        messagebox.showerror(
                            "Invalid Password", 
                            "The password is incorrect. Please try again."
                        )
            
            # Verify sections table exists
            self.cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='sections'
                """
            )
            if not self.cursor.fetchone():
                raise ValueError("Invalid database: 'sections' table not found.")
                
            # Reinitialize schema if needed
            self.setup_database()
            return True

        except sqlite3.DatabaseError:
            raise RuntimeError("The selected file is not a valid SQLite database.")
        except Exception as e:
            raise RuntimeError(f"An error occurred while loading the database: {e}")

    def decrypt_safely(self, encrypted_value, default=""):
        """Safely decrypt a value with error handling."""
        if not encrypted_value:
            return default
            
        try:
            return self.encryption_manager.decrypt_string(encrypted_value)
        except Exception as e:
            print(f"Decryption error: {e}")
            return default

    def load_from_database(self):
        """Load and decrypt data from the database with enhanced error handling."""
        try:
            self.cursor.execute(
                "SELECT id, title, type, parent_id, questions FROM sections ORDER BY placement, id"
            )
            rows = self.cursor.fetchall()
            decrypted_rows = []
            
            for row in rows:
                try:
                    decrypted_title = self.decrypt_safely(row[1], f"[Section {row[0]}]")
                    decrypted_questions = self.decrypt_safely(row[4], "[]")
                    
                    decrypted_rows.append((
                        row[0],                # id
                        decrypted_title,       # title
                        row[2],                # type
                        row[3],                # parent_id
                        decrypted_questions    # questions
                    ))
                except Exception as e:
                    print(f"Error processing row {row[0]}: {e}")
                    decrypted_rows.append((
                        row[0],
                        f"[Error: Section {row[0]}]",
                        row[2],
                        row[3],
                        "[]"
                    ))
            
            return decrypted_rows
            
        except Exception as e:
            print(f"Database error: {e}")
            raise


    # Search related
    def _should_refresh_cache(self) -> bool:
        """Check if the cache needs refreshing based on time or modifications."""
        return time.time() - self._last_cache_update > self._cache_lifetime

    @timer
    def refresh_search_cache(self, node_id=None):
        """Refresh the search cache for specified node or entire database."""
        if node_id:
            # Load specific node and its children
            sections = self._load_node_and_children(node_id)
        else:
            # Load all sections
            self.cursor.execute("SELECT id, title, questions FROM sections")
            sections = self.cursor.fetchall()

        # Update cache with decrypted values
        for section_id, title, questions in sections:
            if str(section_id) not in self._search_cache:
                self._search_cache[str(section_id)] = {
                    'title': self.decrypt_safely(title, ''),
                    'questions': self.decrypt_safely(questions, '[]')
                }

        self._last_cache_update = time.time()

    @timer
    def _load_node_and_children(self, node_id) -> list:
        """Recursively load a node and all its descendants."""
        result = []
        self.cursor.execute("""
            WITH RECURSIVE descendants AS (
                SELECT id, title, questions, parent_id
                FROM sections
                WHERE id = ?
                UNION ALL
                SELECT s.id, s.title, s.questions, s.parent_id
                FROM sections s
                INNER JOIN descendants d ON s.parent_id = d.id
            )
            SELECT id, title, questions FROM descendants
        """, (node_id,))
        return self.cursor.fetchall()

    @timer
    def search_sections(self, query: str, node_id: int = None, global_search: bool = False) -> Tuple[Set[int], Set[int]]:
        """
        Enhanced search function supporting both local and global searches with caching.
        """
        if not query:
            return set(), set()

        # Always refresh cache for the appropriate scope
        if global_search:
            self.refresh_search_cache(None)  # Refresh entire database
        elif node_id is not None:
            self.refresh_search_cache(node_id)  # Refresh selected node and children
        else:
            # If no node selected and not global, search root level items
            self.cursor.execute("SELECT id FROM sections WHERE parent_id IS NULL")
            root_ids = [row[0] for row in self.cursor.fetchall()]
            for root_id in root_ids:
                self.refresh_search_cache(root_id)

        matching_ids = set()
        parent_ids = set()
        
        # Get relevant section IDs based on search scope
        if global_search:
            sections_to_search = self._search_cache.keys()
        elif node_id is not None:
            sections = self._load_node_and_children(node_id)
            sections_to_search = [str(s[0]) for s in sections]
        else:
            # If no node selected and not global, search all root level items and their children
            sections_to_search = self._search_cache.keys()

        # Perform search on cached data
        query = query.lower()
        for section_id in sections_to_search:
            cached_data = self._search_cache.get(section_id)
            if not cached_data:
                continue

            if (query in cached_data['title'].lower() or 
                query in cached_data['questions'].lower()):
                matching_ids.add(int(section_id))

        # Get all parent IDs for matching sections
        if matching_ids:
            placeholders = ','.join('?' * len(matching_ids))
            self.cursor.execute(f"""
                WITH RECURSIVE ancestors AS (
                    SELECT id, parent_id
                    FROM sections
                    WHERE id IN ({placeholders})
                    UNION ALL
                    SELECT s.id, s.parent_id
                    FROM sections s
                    INNER JOIN ancestors a ON s.id = a.parent_id
                    WHERE s.parent_id IS NOT NULL
                )
                SELECT DISTINCT parent_id
                FROM ancestors
                WHERE parent_id IS NOT NULL
            """, list(matching_ids))
            parent_ids = {row[0] for row in self.cursor.fetchall()}

        return matching_ids, parent_ids

    def close(self):
        self.conn.close()

