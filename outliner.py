import ttkbootstrap as ttk
from ttkbootstrap import Style
from tkinter import messagebox, simpledialog
from tkinter.filedialog import asksaveasfilename, askopenfilename

import tkinter as tk
import tkinter.font as tkFont 
import sqlite3
import json

from utility import timer
from manager_docx import export_to_docx
from manager_json import load_from_json_file
from manager_encryption import EncryptionManager

from database import DatabaseHandler
from config import (
    THEME,
    VERSION,
    DB_NAME,
    GLOBAL_FONT_FAMILY,
    GLOBAL_FONT_SIZE,
    GLOBAL_FONT,
    DOC_FONT,
    H1_SIZE,
    H2_SIZE,
    H3_SIZE,
    H4_SIZE,
    P_SIZE,
    INDENT_SIZE,
    PASSWORD_MIN_LENGTH
)

class PasswordChangeDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.result = None
        
        self.title("Change Database Password")
        self.geometry("300x400")
        self.resizable(False, False)
        
        # Current password
        ttk.Label(self, text="Current Password:").pack(pady=(20, 5))
        self.current_password = ttk.Entry(self, show="*")
        self.current_password.pack(pady=5, padx=20, fill="x")
        
        # New password
        ttk.Label(self, text="New Password (min 14 characters):").pack(pady=(15, 5))
        self.new_password = ttk.Entry(self, show="*")
        self.new_password.pack(pady=5, padx=20, fill="x")
        
        # Confirm new password
        ttk.Label(self, text="Confirm New Password:").pack(pady=(15, 5))
        self.confirm_password = ttk.Entry(self, show="*")
        self.confirm_password.pack(pady=5, padx=20, fill="x")
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=20, fill="x")
        
        ttk.Button(button_frame, text="Change", command=self.change).pack(side="left", padx=20)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right", padx=20)
        
        # Center the dialog
        self.transient(parent)
        self.grab_set()
        
        
    def change(self):
        current = self.current_password.get()
        new = self.new_password.get()
        confirm = self.confirm_password.get()
        
        if not all([current, new, confirm]):
            messagebox.showerror("Error", "All fields are required.")
            return
            
        if new != confirm:
            messagebox.showerror("Error", "New passwords do not match.")
            return
            
        if len(new) < PASSWORD_MIN_LENGTH:
            messagebox.showerror("Error", "New password must be at least 14 characters.")
            return
            
        self.result = (current, new)
        self.destroy()
        
    def cancel(self):
        self.destroy()


class OutLineEditorApp:
    def __init__(self, root):
        # Apply ttkbootstrap theme
        self.style = Style(THEME)
        self.root = root
        self.root.title(f"Outline Editor v{VERSION}")

        # Set global font scaling using tkinter.font
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(family=GLOBAL_FONT_FAMILY, size=GLOBAL_FONT_SIZE)

        # Padding constants
        LABEL_PADX = 5
        LABEL_PADY = (5, 5)
        ENTRY_PADY = (5, 5)
        SECTION_PADY = (5, 10)
        BUTTON_PADX = 5
        BUTTON_PADY = (5, 0)
        FRAME_PADX = 10
        FRAME_PADY = 10

        # Initialize notebook and tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=FRAME_PADX, pady=FRAME_PADY)

        # Initialize tabs
        self.editor_tab = ttk.Frame(self.notebook)
        self.database_tab = ttk.Frame(self.notebook)
        self.exports_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.editor_tab, text="Editor")
        self.notebook.add(self.database_tab, text="Database")
        self.notebook.add(self.exports_tab, text="Exports")

        # Key Bindings
        self.root.bind_all("<Control-D>", lambda event: self.delete_selected())
        self.root.bind_all("<Control-d>", lambda event: self.delete_selected())
        self.root.bind_all("<Control-j>", lambda event: self.move_up())
        self.root.bind_all("<Control-k>", lambda event: self.move_down())
        self.root.bind_all("<Control-i>", lambda event: self.move_left())
        self.root.bind_all("<Control-o>", lambda event: self.move_right())
        self.root.bind_all("<F2>", self.focus_title_entry)
        self.root.bind_all("<Control-Key-1>", lambda event: self.add_h1())
        self.root.bind_all("<Control-Key-2>", lambda event: self.add_h2())
        self.root.bind_all("<Control-Key-3>", lambda event: self.add_h3())
        self.root.bind_all("<Control-Key-4>", lambda event: self.add_h4())
        self.root.bind_all("<Control-s>", self.save_data)
        self.root.bind_all("<Control-r>", self.refresh_tree)

        # Create the individual tabs
        self.create_editor_tab(
            LABEL_PADX, LABEL_PADY, ENTRY_PADY, SECTION_PADY, BUTTON_PADX, BUTTON_PADY
        )
        self.create_database_tab(
            LABEL_PADX, LABEL_PADY, FRAME_PADX, FRAME_PADY, BUTTON_PADX, BUTTON_PADY
        )
        self.create_exports_tab(
            LABEL_PADX, LABEL_PADY, FRAME_PADX, FRAME_PADY, BUTTON_PADX, BUTTON_PADY
        )

        # Add new attributes for security state
        self.is_authenticated = False
        self.password_validated = False
        
        # Initialize database without Encryption Manager
        self.db = DatabaseHandler(DB_NAME)

        # Handle password initialization
        try:
            self.initialize_password()
            self.password_validated = True
            self.is_authenticated = True
        except ValueError as e:
            self.handle_authentication_failure(str(e))
        
        # Disable UI elements until authenticated
        self.set_ui_state(self.is_authenticated)

        # Assign the encryption manager to the database
        self.db.encryption_manager = self.encryption_manager

        # Ensure the database is initialized properly
        self.db.setup_database()
        self.db.initialize_placement()

        # State to track the last selected item
        self.last_selected_item_id = None

        # Load initial data into the editor
        self.load_from_database()

        # Bind notebook tab change to save data and refresh the tree
        self.notebook.bind("<<NotebookTabChanged>>", lambda event: (self.save_data(), self.refresh_tree()))


        # Save on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)



    def initialize_password(self):
        """
        Handles password logic: prompts user for existing password or sets a new one.
        Initializes the EncryptionManager.
        """
        self.db.cursor.execute(
            "SELECT value FROM settings WHERE key = ?", ("password",)
        )
        result = self.db.cursor.fetchone()

        if result:
            # Password exists; validate user input
            while True:
                password = simpledialog.askstring(
                    "Enter Password",
                    "Enter the password for this database:",
                    show="*",
                )
                if not password:
                    raise ValueError("Password entry canceled.")
                if self.db.validate_password(password):
                    self.encryption_manager = EncryptionManager(password=password)
                    break
                else:
                    messagebox.showerror("Invalid Password", "The password is incorrect. Try again.")
        else:
            # No password set; create a new one
            while True:
                password = simpledialog.askstring(
                    "Set Password",
                    "No password found. Set a new password (min. 14 characters):",
                    show="*",
                )
                if not password or len(password) < PASSWORD_MIN_LENGTH:
                    messagebox.showerror("Invalid Password", "Password must be at least 14 characters.")
                    continue
                self.db.set_password(password)
                self.encryption_manager = EncryptionManager(password=password)
                messagebox.showinfo("Success", "Password has been set.")
                break

    def handle_authentication_failure(self, message="Authentication failed"):
        """Handle failed authentication attempts."""
        self.is_authenticated = False
        self.password_validated = False
        self.encryption_manager = None
        messagebox.showerror("Authentication Error", message)
        self.set_ui_state(False)

    @timer
    def set_ui_state(self, enabled):
        """Enable or disable UI elements based on authentication state."""
        state = "normal" if enabled else "disabled"
        
        # Disable all input elements
        self.title_entry.configure(state=state)
        self.questions_text.configure(state=state)
        self.search_entry.configure(state=state)
        self.tree.configure(selectmode="none" if not enabled else "browse")
        
        # Disable all buttons
        for button in self.editor_buttons.winfo_children():
            button.configure(state=state)
        for button in self.database_buttons.winfo_children():
            if button["text"] != "Change Password":  # Keep password change enabled
                button.configure(state=state)
        for button in self.exports_buttons.winfo_children():
            button.configure(state=state)

    @timer
    def add_section(self, section_type, parent_type=None, title_prefix="Section"):
        """
        Add a new section (H1, H2, H3, H4) to the tree with proper encryption.
        """
        if not self.is_authenticated or not self.encryption_manager:
            messagebox.showerror("Error", "Not authenticated. Please verify your password.")
            return

        previous_selection = self.tree.selection()

        if parent_type:
            # Validate the parent selection
            if not previous_selection or self.get_item_type(previous_selection[0]) != parent_type:
                messagebox.showerror(
                    "Error", f"Please select a valid {parent_type} to add a {section_type}."
                )
                return
            parent_id = self.get_item_id(previous_selection[0])
        else:
            parent_id = None

        # Calculate the next placement value for the new section
        self.db.cursor.execute(
            """
            SELECT COALESCE(MAX(placement), 0) + 1
            FROM sections
            WHERE parent_id IS ?
            """,
            (parent_id,)
        )
        next_placement = self.db.cursor.fetchone()[0]

        # Ensure placement is positive
        if next_placement <= 0:
            next_placement = 1

        title = f"{title_prefix} {next_placement}"

        try:
            # Add the section using the database handler with current encryption manager
            self.db.encryption_manager = self.encryption_manager
            section_id = self.db.add_section(title, section_type, parent_id, next_placement)

            # Reload the treeview and reselect the parent if applicable
            self.load_from_database()
            if previous_selection:
                self.select_item(previous_selection[0])

            # Update numbering after adding the section
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)

            return section_id

        except Exception as e:
            print(f"Error adding section: {e}")
            messagebox.showerror("Error", "Failed to add section. Please verify your password.")
            return None

    @timer
    def handle_load_database(self):
        """Handle loading a database file with proper encryption management."""
        file_path = askopenfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db")],
            title="Select Database File"
        )
        if not file_path:
            return

        try:
            # Create a temporary database connection to verify the file
            temp_conn = sqlite3.connect(file_path)
            temp_cursor = temp_conn.cursor()
            
            # Check for required tables
            temp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            if not temp_cursor.fetchone():
                temp_conn.close()
                raise ValueError("Invalid database: 'settings' table not found.")

            # Get stored password hash
            temp_cursor.execute("SELECT value FROM settings WHERE key = ?", ("password",))
            stored_hash = temp_cursor.fetchone()
            if not stored_hash:
                temp_conn.close()
                raise ValueError("No password found in database.")
            
            temp_conn.close()

            # Prompt for password
            while True:
                password = simpledialog.askstring(
                    "Database Password",
                    "Enter the password for this database:",
                    show="*"
                )
                if not password:
                    return  # User cancelled

                try:
                    # Create new encryption manager for validation
                    test_manager = EncryptionManager(password)
                    
                    # Create new database handler with the test manager
                    new_db = DatabaseHandler(file_path, test_manager)
                    
                    # Validate the password
                    if not new_db.validate_password(password):
                        messagebox.showerror("Error", "Invalid password. Please try again.")
                        continue
                    
                    # Password validated, update the current database
                    self.db.close()
                    self.db = new_db
                    self.encryption_manager = test_manager
                    self.db.encryption_manager = test_manager  # Ensure DB handler has the current manager
                    self.is_authenticated = True
                    self.password_validated = True
                    
                    # Clear editor fields
                    self.title_entry.delete(0, tk.END)
                    self.questions_text.delete(1.0, tk.END)
                    self.last_selected_item_id = None
                    
                    # Enable UI and refresh tree
                    self.set_ui_state(True)
                    self.refresh_tree()
                    
                    messagebox.showinfo("Success", f"Database loaded successfully from {file_path}")
                    break
                    
                except Exception as e:
                    print(f"Validation error: {e}")
                    messagebox.showerror("Error", f"Failed to validate password: {e}")
                    continue

        except Exception as e:
            print(f"Database loading error: {e}")
            messagebox.showerror("Error", f"Failed to load database: {e}")
            self.handle_authentication_failure("Failed to authenticate with the loaded database.")
    
    # TABS

    def create_editor_tab(self, label_padx, label_pady, entry_pady, section_pady, button_padx, button_pady):
        # Configure the main grid for the Editor tab
        self.editor_tab.grid_rowconfigure(0, weight=1)  # Main content row
        self.editor_tab.grid_rowconfigure(1, weight=0)  # Buttons row
        self.editor_tab.grid_columnconfigure(0, weight=1, minsize=300)  # Treeview column
        self.editor_tab.grid_columnconfigure(1, weight=2)  # Editor column

        # Treeview Frame (Left)
        self.tree_frame = ttk.Frame(self.editor_tab)
        self.tree_frame.grid(row=0, column=0, sticky="nswe", padx=10, pady=(10, 0))
        self.tree_frame.grid_rowconfigure(1, weight=1)  # Treeview expands vertically
        self.tree_frame.grid_columnconfigure(0, weight=1)  # Treeview fills horizontally

        ttk.Label(self.tree_frame, text="Your Outline", bootstyle="info").grid(
            row=0, column=0, sticky="w", padx=label_padx, pady=label_pady
        )
        self.tree = ttk.Treeview(self.tree_frame, show="tree", bootstyle="info")
        self.tree.grid(row=1, column=0, sticky="nswe", pady=section_pady)

        self.tree.bind("<<TreeviewSelect>>", self.load_selected)  # Bind for handling selection
        # self.tree.bind("<<TreeviewSelect>>", lambda event: (self.load_selected, self.refresh_tree()))  # can't go here
        #self.tree.bind("<<TreeviewSelect>>", lambda event: (self.refresh_tree(), self.load_selected))  # can't go here
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)   # Bind for handling lazy loading on expand


        ttk.Label(self.tree_frame, text="Search <Enter>", bootstyle="info").grid(
            row=2, column=0, sticky="w", padx=label_padx, pady=(5, 0)
        )
        self.search_entry = ttk.Entry(self.tree_frame, bootstyle="info")
        self.search_entry.grid(row=3, column=0, sticky="ew", pady=entry_pady)
        self.search_entry.bind("<Return>", self.execute_search)

        # Editor Frame (Right)
        self.editor_frame = ttk.Frame(self.editor_tab)
        self.editor_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)
        self.editor_frame.grid_rowconfigure(3, weight=1)  # Text editor expands vertically
        self.editor_frame.grid_columnconfigure(0, weight=1)  # Editor expands horizontally

        ttk.Label(self.editor_frame, text="Title", bootstyle="info").grid(
            row=0, column=0, sticky="w", padx=label_padx, pady=label_pady
        )
        self.title_entry = ttk.Entry(self.editor_frame, bootstyle="info")
        self.title_entry.grid(row=1, column=0, sticky="ew", pady=entry_pady)

        ttk.Label(self.editor_frame, text="Questions Notes and Details", bootstyle="info").grid(
            row=2, column=0, sticky="w", padx=label_padx, pady=label_pady
        )
        self.questions_text = tk.Text(self.editor_frame, height=15)
        self.questions_text.grid(row=3, column=0, sticky="nswe", pady=section_pady)

        # Buttons Row (Bottom)
        self.editor_buttons = ttk.Frame(self.editor_tab)
        self.editor_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        for text, command, style in [
            ("H(1)", self.add_h1, "primary"),
            ("H(2)", self.add_h2, "primary"),
            ("H(3)", self.add_h3, "primary"),
            ("H(4)", self.add_h4, "primary"),
            ("(j) ↑", self.move_up, "secondary"),
            ("(k) ↓", self.move_down, "secondary"),
            ("(i) ←", self.move_left, "secondary"),
            ("(o) →", self.move_right, "secondary"),
            ("(D)elete", self.delete_selected, "danger"),
        ]:
            ttk.Button(self.editor_buttons, text=text, command=command, bootstyle=style).pack(side=tk.LEFT, padx=button_padx)

    def create_database_tab(self, label_padx, label_pady, frame_padx, frame_pady, button_padx, button_pady):
        # Configure the main grid for the Database tab
        self.database_tab.grid_rowconfigure(0, weight=1)  # Main content row
        self.database_tab.grid_rowconfigure(1, weight=0)  # Buttons row
        self.database_tab.grid_columnconfigure(0, weight=1)  # Single column layout

        # Main Content Frame
        self.database_frame = ttk.Frame(self.database_tab)
        self.database_frame.grid(row=0, column=0, sticky="nswe", padx=frame_padx, pady=(frame_pady, 0))
        self.database_frame.grid_rowconfigure(0, weight=1)
        self.database_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(self.database_frame, text="Database Operations", font=GLOBAL_FONT).grid(
            row=0, column=0, sticky="w", padx=label_padx, pady=label_pady
        )
        ttk.Label(self.database_frame, text="Use the buttons below for database actions.", font=GLOBAL_FONT).grid(
            row=1, column=0, sticky="w", padx=label_padx, pady=label_pady
        )

        # Buttons Frame (Bottom)
        self.database_buttons = ttk.Frame(self.database_tab)
        self.database_buttons.grid(row=1, column=0, sticky="ew", padx=frame_padx, pady=frame_pady)

        for text, command, style in [
            ("Load JSON", lambda: load_from_json_file(self.db.cursor, self.db, self.refresh_tree), "info"),
            ("Load DB", self.handle_load_database, "info"),
            ("New DB", self.reset_database, "warning"),
            ("Change Password", self.change_database_password, "secondary"),
        ]:
            ttk.Button(self.database_buttons, text=text, command=command, bootstyle=style).pack(
                side=tk.LEFT, padx=button_padx, pady=button_pady
            )

    def create_exports_tab(self, label_padx, label_pady, frame_padx, frame_pady, button_padx, button_pady):
        # Configure the main grid for the Exports tab
        self.exports_tab.grid_rowconfigure(0, weight=1)  # Main content row
        self.exports_tab.grid_rowconfigure(1, weight=0)  # Buttons row
        self.exports_tab.grid_columnconfigure(0, weight=1)  # Single column layout

        # Main Content Frame
        self.exports_frame = ttk.Frame(self.exports_tab)
        self.exports_frame.grid(row=0, column=0, sticky="nswe", padx=frame_padx, pady=(frame_pady, 0))
        self.exports_frame.grid_rowconfigure(0, weight=1)
        self.exports_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(self.exports_frame, text="Export Options", font=GLOBAL_FONT).grid(
            row=0, column=0, sticky="w", padx=label_padx, pady=label_pady
        )
        ttk.Label(self.exports_frame, text="Use the button below to export your outline.", font=GLOBAL_FONT).grid(
            row=1, column=0, sticky="w", padx=label_padx, pady=label_pady
        )

        # Buttons Frame (Bottom)
        self.exports_buttons = ttk.Frame(self.exports_tab)
        self.exports_buttons.grid(row=1, column=0, sticky="ew", padx=frame_padx, pady=frame_pady)

        ttk.Button(self.exports_buttons, text="Make DOCX", command=lambda: export_to_docx(self.db.cursor), bootstyle="success").pack(
            side=tk.LEFT, padx=button_padx, pady=button_padx
        )


    # TREE MANIPULATION

    @timer
    def on_tree_expand(self, event):
        """
        Handle TreeView node expansion and load child nodes lazily.
        """
        selected_node = self.tree.focus()
        if not selected_node:
            return

        # Remove any existing hidden nodes
        children = self.tree.get_children(selected_node)
        for child in children:
            if "hidden" in self.tree.item(child, "tags"):
                try:
                    self.tree.delete(child)
                except Exception as e:
                    print(f"Error deleting hidden node: {e}")
                    continue

        try:
            # Load actual children dynamically
            self.populate_tree(
                parent_id=self.get_item_id(selected_node), 
                parent_node=selected_node
            )

            # Update numbering after loading children
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)
        except Exception as e:
            print(f"Error in tree expansion: {e}")

    @timer
    def populate_filtered_tree(self, parent_id, parent_node, ids_to_show, parents_to_show):
        """Recursively populate the treeview with filtered data."""
        children = self.db.load_children(parent_id)  # Add `load_children` method in `DatabaseHandler`

        for child in children:
            if child[0] in ids_to_show or child[0] in parents_to_show:
                node = self.tree.insert(parent_node, "end", child[0], text=child[1])
                self.tree.see(node)  # Ensure the node is visible
                self.populate_filtered_tree(child[0], node, ids_to_show, parents_to_show)

    @timer
    def move_up(self):
        selected = self.tree.selection()
        if not selected:
            return
        

        item_id = self.get_item_id(selected[0])
        parent_id = self.tree.parent(selected[0]) or None

        if parent_id is None:
            
            # First, let's see all H1 sections and their placements
            self.db.cursor.execute(
                "SELECT id, placement, title FROM sections WHERE parent_id IS NULL ORDER BY placement"
            )
            all_h1s = self.db.cursor.fetchall()
            
            # Handle H1 sections - direct placement manipulation
            query = """
                SELECT s1.id, s1.placement, s2.id as prev_id, s2.placement as prev_placement
                FROM sections s1
                LEFT JOIN sections s2 ON s2.parent_id IS NULL 
                    AND s2.placement < s1.placement
                WHERE s1.id = ?
                ORDER BY s2.placement DESC
                LIMIT 1
                """
            
            self.db.cursor.execute(query, (item_id,))
            result = self.db.cursor.fetchone()
            
            if result and result[2] is not None:  # If there's a previous item
                # Direct swap of placement values
                update_query = """
                    UPDATE sections 
                    SET placement = CASE
                        WHEN id = ? THEN ?
                        WHEN id = ? THEN ?
                    END
                    WHERE id IN (?, ?)
                    """
                params = (item_id, result[3], result[2], result[1], item_id, result[2])
                
                self.db.cursor.execute(update_query, params)
                self.db.conn.commit()
                
                # Verify the update
                self.db.cursor.execute(
                    "SELECT id, placement, title FROM sections WHERE id IN (?, ?)",
                    (item_id, result[2])
                )
                updated_rows = self.db.cursor.fetchall()
        else:
            # Handle child sections
            self.db.cursor.execute(
                "SELECT id, placement FROM sections WHERE parent_id = ? ORDER BY placement",
                (parent_id,),
            )
            siblings = self.db.cursor.fetchall()
            sibling_ids = [item[0] for item in siblings]
            current_index = sibling_ids.index(item_id)

            if current_index > 0:
                prev_item_id = sibling_ids[current_index - 1]
                self.swap_placement(item_id, prev_item_id)
                self.db.fix_placement(parent_id)

        self.refresh_tree()
        
        # Recalculate numbering after moving the node
        numbering_dict = self.db.generate_numbering()  # Generate new numbering
        self.calculate_numbering(numbering_dict)       # Apply numbering to the TreeView
        
        self.select_item(item_id)

    @timer
    def move_down(self):
        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])  # Get the ID of the selected item
        parent_id = self.tree.parent(selected[0]) or None  # Get the parent ID, or None for root-level items

        if parent_id is None:
            # Handle root-level (H1) sections
            self.db.cursor.execute(
                "SELECT id, placement, title FROM sections WHERE parent_id IS NULL ORDER BY placement"
            )
            all_h1s = self.db.cursor.fetchall()
            
            # Query for the next sibling
            query = """
                SELECT s1.id, s1.placement, s2.id as next_id, s2.placement as next_placement
                FROM sections s1
                LEFT JOIN sections s2 ON s2.parent_id IS NULL 
                    AND s2.placement > s1.placement
                WHERE s1.id = ?
                ORDER BY s2.placement ASC
                LIMIT 1
            """
            
            self.db.cursor.execute(query, (item_id,))
            result = self.db.cursor.fetchone()
            
            if result and result[2] is not None:  # If there's a next item
                # Swap placements
                update_query = """
                    UPDATE sections 
                    SET placement = CASE
                        WHEN id = ? THEN ?
                        WHEN id = ? THEN ?
                    END
                    WHERE id IN (?, ?)
                """
                params = (item_id, result[3], result[2], result[1], item_id, result[2])
                
                self.db.cursor.execute(update_query, params)
                self.db.conn.commit()

                # Verify the update (optional, for debugging)
                self.db.cursor.execute(
                    "SELECT id, placement, title FROM sections WHERE id IN (?, ?)",
                    (item_id, result[2])
                )
                updated_rows = self.db.cursor.fetchall()
        else:
            # Handle child sections
            self.db.cursor.execute(
                "SELECT id, placement FROM sections WHERE parent_id = ? ORDER BY placement",
                (parent_id,),
            )
            siblings = self.db.cursor.fetchall()
            sibling_ids = [item[0] for item in siblings]
            current_index = sibling_ids.index(item_id)

            if current_index < len(sibling_ids) - 1:
                next_item_id = sibling_ids[current_index + 1]
                self.swap_placement(item_id, next_item_id)
                self.db.fix_placement(parent_id)

        # Refresh the tree to reflect changes
        self.refresh_tree()

        # Recalculate numbering after moving the node
        numbering_dict = self.db.generate_numbering()  # Generate new numbering
        self.calculate_numbering(numbering_dict)       # Apply numbering to the TreeView

        # Reselect the moved item
        self.select_item(item_id)

    @timer
    def move_left(self):
        """Move the selected item up one level in the hierarchy."""
        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])
        current_parent_id = self.tree.parent(selected[0])

        if not current_parent_id:
            messagebox.showerror("Error", "Cannot move root-level items left.")
            return

        grandparent_id = self.tree.parent(self.tree.parent(selected[0]))
        grandparent_id = None if grandparent_id == "" else grandparent_id  # Normalize empty string to None
        current_type = self.db.get_section_type(item_id)

        # Determine the new type
        new_type = None
        if current_type == "category":
            new_type = "header"
        elif current_type == "subcategory":
            new_type = "category"
        elif current_type == "subheader":
            new_type = "subcategory"

        if not new_type:
            messagebox.showerror("Error", "Unsupported section type for this operation.")
            return

        # Update database
        self.db.cursor.execute(
            "UPDATE sections SET parent_id = ?, type = ? WHERE id = ?",
            (grandparent_id, new_type, item_id)
        )

        # Fix placements
        self.db.fix_placement(current_parent_id)
        if grandparent_id:
            self.db.fix_placement(grandparent_id)

        self.db.conn.commit()

        # Refresh the tree
        self.refresh_tree()
        self.select_item(selected[0])

    @timer
    def move_right(self):
        """Move the selected item down one level in the hierarchy."""
        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])
        current_parent_id = self.tree.parent(selected[0])
        siblings = self.tree.get_children(current_parent_id)

        index = siblings.index(selected[0])
        if index == 0:
            messagebox.showerror("Error", "Cannot move the first sibling right.")
            return

        new_parent_id = self.get_item_id(siblings[index - 1])
        parent_type = self.db.get_section_type(new_parent_id)

        # Determine the new type
        new_type = None
        if parent_type == "header":
            new_type = "category"
        elif parent_type == "category":
            new_type = "subcategory"
        elif parent_type == "subcategory":
            new_type = "subheader"

        if not new_type:
            messagebox.showerror("Error", "Unsupported section type for this operation.")
            return

        # Update database
        self.db.cursor.execute(
            "UPDATE sections SET parent_id = ?, type = ? WHERE id = ?",
            (new_parent_id, new_type, item_id)
        )

        # Fix placements
        self.db.fix_placement(current_parent_id)
        self.db.fix_placement(new_parent_id)

        self.db.conn.commit()

        # Refresh the tree
        self.refresh_tree()
        self.select_item(selected[0])

    @timer
    def calculate_numbering(self, numbering_dict):
        """
        Assign hierarchical numbering to tree nodes based on the provided numbering dictionary.
        Skip dummy nodes during numbering.
        """
        for node in self.tree.get_children():
            self.apply_numbering_recursive(node, numbering_dict)

    @timer
    def apply_numbering_recursive(self, node, numbering_dict):
        """
        Apply numbering to a node and its children recursively.
        Skip dummy nodes during numbering.
        """
        # Skip dummy nodes
        if "hidden" in self.tree.item(node, "tags"):
            return
            
        node_id = self.get_item_id(node)
        if node_id is not None and node_id in numbering_dict:
            logical_title = self.tree.item(node, "text").split(". ", 1)[-1]  # Remove existing numbering
            display_title = f"{numbering_dict[node_id]}. {logical_title}"
            self.tree.item(node, text=display_title)

        # Process children recursively
        for child in self.tree.get_children(node):
            self.apply_numbering_recursive(child, numbering_dict)

    @timer
    def refresh_tree(self, event=None):
        """
        Reload the TreeView to reflect database changes while preserving expansion state.
        """
        try:
            # Get currently expanded items before refresh (using database IDs)
            expanded_db_ids = self.get_expanded_items()
            
            # Store current selection if any
            selected = self.tree.selection()
            selected_db_id = self.get_item_id(selected[0]) if selected else None
            
            # Clear the tree
            self.tree.delete(*self.tree.get_children())
            
            # Reload the tree
            self.load_from_database()
            
            # Restore expansion state
            self.restore_expansion_state(expanded_db_ids)
            
            # Restore selection if possible
            if selected_db_id is not None:
                self.select_item(selected_db_id)
                
            # Update numbering
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)
            
        except Exception as e:
            print(f"Error in refresh_tree: {e}")

    @timer
    def get_expanded_items(self):
        """
        Get a list of database IDs for expanded items in the Treeview.
        Returns:
            list: List of database IDs (not tree IDs) of expanded items
        """
        expanded_db_ids = []
        for item in self.tree.get_children():
            expanded_db_ids.extend(self.get_expanded_items_recursively(item))
        return expanded_db_ids

    @timer
    def get_expanded_items_recursively(self, item):
        """
        Recursively check for expanded items and return their database IDs.
        Args:
            item: Current tree item ID
        Returns:
            list: List of database IDs for expanded items in this branch
        """
        expanded_db_ids = []
        try:
            if self.tree.item(item, "open"):
                # Extract the database ID from the tree item ID
                db_id = self.get_item_id(item)
                if db_id is not None:
                    expanded_db_ids.append(db_id)
                
                # Process children
                for child in self.tree.get_children(item):
                    if "hidden" not in self.tree.item(child, "tags"):  # Skip hidden nodes
                        expanded_db_ids.extend(self.get_expanded_items_recursively(child))
        except Exception as e:
            print(f"Error in get_expanded_items_recursively: {e}")
        return expanded_db_ids

    @timer
    def restore_expansion_state(self, expanded_db_ids):
        """
        Restore the expanded state of items in the treeview using database IDs.
        Args:
            expanded_db_ids: List of database IDs that were previously expanded
        """
        if not expanded_db_ids:
            return

        def expand_recursive(node):
            """Recursively expand nodes and their children if they match expanded_db_ids."""
            try:
                db_id = self.get_item_id(node)
                if db_id in expanded_db_ids:
                    # Remove any dummy nodes before expanding
                    children = self.tree.get_children(node)
                    for child in children:
                        if "hidden" in self.tree.item(child, "tags"):
                            self.tree.delete(child)
                    
                    # Populate real children
                    self.populate_tree(db_id, node)
                    
                    # Set the node as expanded
                    self.tree.item(node, open=True)
                    
                    # Process actual children
                    for child in self.tree.get_children(node):
                        if "hidden" not in self.tree.item(child, "tags"):
                            expand_recursive(child)
            except Exception as e:
                print(f"Error in expand_recursive: {e}")

        # Start the recursive expansion from root level
        for root_item in self.tree.get_children():
            expand_recursive(root_item)

    @timer
    def get_item_id(self, node):
        """
        Extract the numeric ID from the node identifier. Supports both numeric and prefixed IDs.
        """
        try:
            # Assume node ID is numeric by default
            if node.startswith("I"):
                return int(node[1:])  # Strip "I" prefix and parse as integer
            return int(node)
        except (ValueError, TypeError):
            print(f"Warning: Invalid node ID format: {node}")
            return None

    @timer
    def select_item(self, item_id):
        """Select and focus an item in the treeview."""
        try:
            if self.tree.exists(str(item_id)):
                self.tree.selection_set(str(item_id))
                self.tree.focus(str(item_id))
                self.tree.see(str(item_id))  # Ensure the item is visible
        except Exception as e:
            print(f"Error in select_item: {e}")


    # CRUD RELATED

    @timer
    def load_from_database(self):
        """
        Load and populate the root-level nodes in the TreeView.
        """
        try:
            # Clear the TreeView
            self.tree.delete(*self.tree.get_children())

            # Ensure consistency in the database
            self.db.clean_parent_ids()

            # Populate the root-level nodes
            self.populate_tree(None, "")

            # Generate numbering for all sections
            numbering_dict = self.db.generate_numbering()

            # Apply numbering to the TreeView nodes
            self.calculate_numbering(numbering_dict)

        except Exception as e:
            print(f"Error in load_from_database: {e}")

    @timer
    def populate_tree(self, parent_id=None, parent_node=""):
        """
        Populate the tree lazily with nodes.
        Args:
            parent_id: The database ID of the parent section
            parent_node: The treeview ID of the parent node
        """
        children = self.db.load_children(parent_id)
        for child_id, encrypted_title, parent_id in children:
            if not child_id:  # Skip invalid entries
                continue
                
            title = self.db.decrypt_safely(encrypted_title, default="Untitled")
            node_id = f"I{child_id}"
            
            # Check if node already exists
            if not self.tree.exists(node_id):
                # Only create nodes that have actual content
                if title and title.strip():
                    node = self.tree.insert(parent_node, "end", node_id, text=title)
                    
                    # If this node has children, configure it to show the + sign
                    if self.db.has_children(child_id):
                        dummy_id = f"dummy_{node_id}"
                        # Only add dummy if it doesn't exist
                        if not self.tree.exists(dummy_id):
                            self.tree.insert(node, 0, dummy_id, text="", tags=["hidden"])

    @timer
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
                password = simpledialog.askstring(
                    "Database Password",
                    "Enter the password for this database:",
                    show="*"
                )
                if not password:
                    raise ValueError("Password entry cancelled.")
                    
                # Create temporary encryption manager to validate password
                temp_encryption_manager = EncryptionManager(password)
                
                # Reopen connection to verify password
                temp_conn = sqlite3.connect(db_path)
                temp_cursor = temp_conn.cursor()
                stored_hash = temp_cursor.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    ("password",)
                ).fetchone()[0]
                
                if hashlib.sha256(password.encode()).hexdigest() != stored_hash:
                    temp_conn.close()
                    raise ValueError("Invalid password.")
                
                # Password verified, update the encryption manager
                self.encryption_manager = temp_encryption_manager
            
            # Close existing connection and open new one
            self.conn.close()
            self.db_name = db_path
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            
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

        except sqlite3.DatabaseError:
            raise RuntimeError("The selected file is not a valid SQLite database.")
        except Exception as e:
            raise RuntimeError(f"An error occurred while loading the database: {e}")

    @timer
    def load_selected(self, event):
        """Load the selected item and populate the editor with decrypted data."""
        if not self.is_authenticated or not self.encryption_manager:
            return
                
        if self.last_selected_item_id is not None:
            self.save_data()
            # can't go here
            #self.refresh_tree()


        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])
        self.last_selected_item_id = item_id
        
        # can't go here
        #self.refresh_tree()

        try:
            # Ensure DB handler has current encryption manager
            self.db.encryption_manager = self.encryption_manager
            
            row = self.db.cursor.execute(
                "SELECT title, questions FROM sections WHERE id = ?", (item_id,)
            ).fetchone()

            self.title_entry.delete(0, tk.END)
            self.questions_text.delete(1.0, tk.END)

            if row:
                title, encrypted_questions = row
                decrypted_title = self.encryption_manager.decrypt_string(title)
                self.title_entry.insert(0, decrypted_title if decrypted_title else "")

                if encrypted_questions:
                    decrypted_questions = self.encryption_manager.decrypt_string(
                        encrypted_questions
                    )
                    parsed_questions = json.loads(decrypted_questions.strip())
                    self.questions_text.insert(tk.END, "\n".join(parsed_questions))
                    
            # can't go here
            #self.refresh_tree()

                    
        except Exception as e:
            print(f"Selection loading error: {e}")
            self.handle_authentication_failure("Decryption failed. Please verify your password.")
            return

    @timer
    def save_data(self, event=None):
        """Save data with authentication check."""
        if not self.is_authenticated or self.last_selected_item_id is None:
            return

        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Error", "Title cannot be empty.")
            return

        try:
            questions = self.questions_text.get(1.0, tk.END).strip().split("\n")
            questions = [q for q in questions if q]
            questions_json = json.dumps(questions)

            self.db.update_section(self.last_selected_item_id, title, questions_json)

            if self.tree.exists(str(self.last_selected_item_id)):
                self.tree.item(self.last_selected_item_id, text=title)

            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)
            
            # can't go here
            #self.refresh_tree()

           
        except Exception as e:
            print(f"Encryption Error: {e}")
            self.handle_authentication_failure("Encryption failed. Please verify your password.")
            return

    @timer
    def delete_selected(self):
        """Deletes the selected item and all its children, ensuring parent restrictions."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an item to delete.")
            return

        item_id = self.get_item_id(selected[0])
        item_type = self.get_item_type(selected[0])

        # Check if the item has children using `DatabaseHandler`
        if self.db.has_children(item_id):
            messagebox.showerror(
                "Error", f"Cannot delete {item_type} with child items."
            )
            return

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the selected {item_type}?",
        )
        if confirm:
            # Use `DatabaseHandler` to perform the deletion
            self.db.delete_section(item_id)

            # Remove the item from the Treeview
            self.tree.delete(selected[0])

            # Reset the editor and last selected item
            self.last_selected_item_id = None
            self.title_entry.delete(0, tk.END)
            self.questions_text.delete(1.0, tk.END)

            print(f"Deleted: {item_type.capitalize()} deleted successfully.")
            
            # Update numbering 
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)

    def reset_database(self):
        """Prompt for a new database file and password, then reset the Treeview."""
        try:
            new_db_path = asksaveasfilename(
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db")],
                title="Create New Database File",
            )
            if not new_db_path:
                return  # User cancelled

            # Prompt for new password
            while True:
                password = simpledialog.askstring(
                    "Set Password",
                    "Enter a new password for this database (min. 14 characters):",
                    show="*"
                )
                if not password:
                    return  # User cancelled
                    
                if len(password) < PASSWORD_MIN_LENGTH:
                    messagebox.showerror(
                        "Invalid Password", 
                        "Password must be at least 14 characters long."
                    )
                    continue
                    
                confirm_password = simpledialog.askstring(
                    "Confirm Password",
                    "Confirm your password:",
                    show="*"
                )
                
                if password != confirm_password:
                    messagebox.showerror(
                        "Password Mismatch",
                        "Passwords do not match. Please try again."
                    )
                    continue
                    
                break

            # Create new encryption manager with the password
            self.encryption_manager = EncryptionManager(password)
            
            # Reset the database
            self.db.reset_database(new_db_path)
            
            # Set the password in the new database
            self.db.set_password(password)
            
            # Update authentication state
            self.is_authenticated = True
            self.password_validated = True
            
            # Clear and reset the Treeview
            self.tree.delete(*self.tree.get_children())
            
            # Enable UI elements
            self.set_ui_state(True)
            
            messagebox.showinfo(
                "Success", 
                f"New encrypted database created: {new_db_path}"
            )

        except RuntimeError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror(
                "Error", 
                f"An unexpected error occurred while resetting the database: {e}"
            )

    def add_h1(self):
        self.add_section(section_type="header", title_prefix="Header")

    def add_h2(self):
        self.add_section(section_type="category", parent_type="header", title_prefix="Category")

    def add_h3(self):
        self.add_section(section_type="subcategory", parent_type="category", title_prefix="Subcategory")

    def add_h4(self):
        self.add_section(section_type="subheader", parent_type="subcategory", title_prefix="Sub Header")

    def swap_placement(self, item_id1, item_id2):
        """Swap the placement of two items using the DatabaseHandler."""
        try:
            self.db.swap_placement(item_id1, item_id2)
        except Exception as e:
            print(f"Error in swap_placement: {e}")

    def fix_placement(self, parent_id):
        """Ensure all children of a parent have sequential placement values."""
        try:
            self.db.fix_placement(parent_id)
        except Exception as e:
            print(f"Error in fix_placement: {e}")

    def get_item_type(self, node):
        """Fetch the type of the selected node using DatabaseHandler."""
        try:
            item_id = self.get_item_id(node)
            return self.db.get_section_type(item_id) if item_id is not None else None
        except Exception as e:
            print(f"Error in get_item_type: {e}")
            return None

    @timer
    def execute_search(self, event=None):
        """Filter TreeView to show only items matching the search query."""
        query = self.search_entry.get().strip()
        if not query:
            self.load_from_database()  # Reset tree if query is empty
            return

        ids_to_show, parents_to_show = self.db.search_sections(query)

        # Generate numbering for all items
        numbering_dict = self.db.generate_numbering()

        # Clear and repopulate the treeview
        self.tree.delete(*self.tree.get_children())
        self.populate_filtered_tree(None, "", ids_to_show, parents_to_show)

        # Apply consistent numbering
        self.calculate_numbering(numbering_dict)
        

    # UTILITY

    @timer
    def change_database_password(self):
        """Enhanced password change with proper validation and UI state management."""
        dialog = PasswordChangeDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result:
            current_password, new_password = dialog.result
            try:
                self.db.change_password(current_password, new_password)
                self.encryption_manager = EncryptionManager(new_password)
                self.is_authenticated = True
                self.password_validated = True
                self.set_ui_state(True)
                messagebox.showinfo("Success", "Password changed successfully.")
            except ValueError as e:
                self.handle_authentication_failure(str(e))
            except Exception as e:
                self.handle_authentication_failure(f"Failed to change password: {e}")

    def focus_title_entry(self, event):
        """Move focus to the title entry and position the cursor at the end."""
        self.title_entry.focus_set()  # Focus on the title entry
        #self.title_entry.icursor(tk.END)  # Move the cursor to the end of the text
        self.title_entry.selection_range(0, tk.END)  # Select all text

    def on_closing(self):
        """Handle window closing event."""
        try:
            self.save_data()  # Save any pending changes
            self.db.close()  # Close the database connection
            self.root.destroy()
        except Exception as e:
            print(f"Error during closing: {e}")
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = OutLineEditorApp(root)
    root.mainloop()

    #1234123412341234