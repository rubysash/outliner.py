import sys
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
from manager_pdf import export_to_pdf
from manager_passwords import get_password

from database import DatabaseHandler
from config import (
    THEME,
    VERSION,
    DB_NAME,
    GLOBAL_FONT_FAMILY,
    GLOBAL_FONT_SIZE,
    GLOBAL_FONT,
    NOTES_FONT_FAMILY,
    NOTES_FONT_SIZE,
    NOTES_FONT,
    DOC_FONT,
    H1_SIZE,
    H2_SIZE,
    H3_SIZE,
    H4_SIZE,
    P_SIZE,
    INDENT_SIZE,
    PASSWORD_MIN_LENGTH
)


class OutLineEditorApp:
    def __init__(self, root):
        # Apply ttkbootstrap theme
        self.style = Style(THEME)
        self.root = root
        self.root.title(f"Outline Editor v{VERSION}")

        
        # tree item tracking for lazy loading work around
        self._suppress_selection_event = False
        self._selection_binding = None  # Store the event binding
        self.last_selected_item_id = None
        self.previous_item_id = None  # Track the previously selected item

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
        
        # context menu
        self.create_context_menu()

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
        
        # Update title with database info
        self.update_title()

        # Bind notebook tab change to save data and refresh the tree
        #self.notebook.bind("<<NotebookTabChanged>>", lambda event: (self.save_data(), self.refresh_tree()))
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)


        # Save on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_title(self):
        """Update the title bar with version, database name, and record count."""
        try:
            # Get record count
            self.db.cursor.execute("SELECT COUNT(*) FROM sections")
            count = self.db.cursor.fetchone()[0]
            
            # Get database filename without path
            db_name = self.db.db_name.split("/")[-1]
            
            # Update title
            self.root.title(f"Outline Editor v{VERSION} - {db_name}, {count} records")
        except Exception as e:
            print(f"Error updating title: {e}")
            self.root.title(f"Outline Editor v{VERSION}")

    def on_tab_change(self, event):
        """Handle notebook tab changes while preserving tree selection."""
        selected = self.tree.selection()
        selected_id = self.get_item_id(selected[0]) if selected else None
        
        # Save data
        self.save_data(refresh=False)
        
        # Refresh tree
        self.refresh_tree()
        
        # Restore selection if there was one
        if selected_id:
            self.select_item(f"I{selected_id}")

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


    # PASSWORDS
    
    def initialize_password(self):
        self.db.cursor.execute(
            "SELECT value FROM settings WHERE key = ?", ("password",)
        )
        result = self.db.cursor.fetchone()

        if result:
            # Password exists; validate user input
            while True:
                password = get_password(
                    self.root,
                    "Enter Password",
                    "Enter the password for this database:"
                )
                
                if password is None:  # User cancelled
                    if messagebox.askyesno(
                        "Load Different Database?",
                        "Would you like to load a different database?"
                    ):
                        success = self.handle_load_database()
                        if success:
                            return
                        continue
                    else:
                        # Exit the application instead of resetting
                        self.root.destroy()  # Close the main window
                        sys.exit()  # Terminate the application completely

                if self.db.validate_password(password):
                    self.encryption_manager = EncryptionManager(password=password)
                    break
                else:
                    messagebox.showerror(
                        "Invalid Password", 
                        "The password is incorrect. Please try again."
                    )
        else:
            # No password set; create a new one
            while True:
                result = get_password(
                    self.root,
                    "Set New Password",
                    f"Enter a new password (min. {PASSWORD_MIN_LENGTH} characters):",
                    confirm=True,
                    min_length=PASSWORD_MIN_LENGTH
                )
                
                if result is None:  # User cancelled
                    if messagebox.askyesno(
                        "Load Existing Database?", 
                        "Would you like to load an existing database instead?"
                    ):
                        success = self.handle_load_database()
                        if success:
                            return
                        continue
                    else:
                        self.root.destroy()
                        sys.exit()
                        
                password, confirm = result
                self.db.set_password(password)
                self.encryption_manager = EncryptionManager(password=password)
                messagebox.showinfo("Success", "Password has been set.")
                break

    # Update change_database_password method
    def change_database_password(self):
        result = get_password(
            self.root,
            "Change Database Password",
            "Enter current password:",
            confirm=False
        )
        
        if result is None:
            return
            
        current_password = result
        
        if not self.db.validate_password(current_password):
            messagebox.showerror("Error", "Current password is incorrect.")
            return
            
        result = get_password(
            self.root,
            "Change Database Password",
            f"Enter new password (min {PASSWORD_MIN_LENGTH} characters):",
            confirm=True,
            min_length=PASSWORD_MIN_LENGTH
        )
        
        if result is None:
            return
            
        new_password, _ = result
        
        try:
            self.db.change_password(current_password, new_password)
            self.encryption_manager = EncryptionManager(new_password)
            self.is_authenticated = True
            self.password_validated = True
            self.set_ui_state(True)
            messagebox.showinfo("Success", "Password changed successfully.")
        except Exception as e:
            self.handle_authentication_failure(f"Failed to change password: {e}")


    # RIGHT CLICK CONTEXT TREE
    
    def create_context_menu(self):
        """Create and bind the context menu to the TreeView."""
        self.tree_menu = tk.Menu(self.tree, tearoff=0)

        self.tree_menu.add_command(label="Add Section", command=self.add_child_section)
        self.tree_menu.add_command(label="Clone Section", command=self.clone_section)  # Add this line

        # Add multiple separators and a disabled spacer for visual safety gap
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label=" ", state="disabled")  # Empty disabled item for spacing
        self.tree_menu.add_separator()

        # Add the delete option
        self.tree_menu.add_command(label="Delete Section", command=self.context_delete_section)

        # Bind right-click to show the context menu
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """Display the context menu at the pointer location."""
        # Identify the item clicked
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
            item = self.tree.identify_row(event.y)
            if item:  # Ensure an item was clicked
                self.tree.selection_set(item)  # Select the item
                self.tree_menu.post(event.x_root, event.y_root)

    def add_child_section(self):
        """Add a new child section to the selected parent."""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "No item selected.")
            return

        # Retrieve the parent ID and type
        parent_id = self.get_item_id(selected_item[0])
        parent_type = self.get_item_type(selected_item[0])

        # Determine the new section type based on parent type
        if parent_type == "header":
            section_type = "category"
            title_prefix = "Category"
        elif parent_type == "category":
            section_type = "subcategory"
            title_prefix = "Subcategory"
        elif parent_type == "subcategory":
            section_type = "subheader"
            title_prefix = "Subheader"
        else:
            messagebox.showerror(
                "Error",
                f"Cannot add a child to a section of type '{parent_type}'."
            )
            return

        # Add the new section to the database
        try:
            section_id = self.add_section(
                section_type=section_type,
                parent_id=parent_id,  # Pass parent_id directly
                title_prefix=title_prefix
            )
            if section_id:
                self.refresh_tree()
                self.select_item(f"I{section_id}")
            else:
                raise ValueError("Database operation failed.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add the section: {e}")

    def context_delete_section(self):
        """Handle deletion from context menu using existing deletion logic."""
        self.delete_selected()
   
    def clone_section(self):
        """Clone the selected section and all its children."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "No section selected for cloning.")
            return

        source_id = self.get_item_id(selected[0])
        parent_node = self.tree.parent(selected[0])
        parent_id = self.get_item_id(parent_node) if parent_node else None
        
        try:
            # Get the source section's type and title
            self.db.cursor.execute(
                "SELECT type, title FROM sections WHERE id = ?", 
                (source_id,)
            )
            section_type, encrypted_title = self.db.cursor.fetchone()
            original_title = self.db.decrypt_safely(encrypted_title)
            
            # Create the cloned parent section
            cloned_title = f"{original_title}-Cloned"
            
            # Get the placement for the new section
            self.db.cursor.execute(
                """
                SELECT COALESCE(MAX(placement), 0) + 1
                FROM sections
                WHERE parent_id IS ?
                """,
                (parent_id,)
            )
            next_placement = self.db.cursor.fetchone()[0]
            
            # Add the cloned parent section
            new_parent_id = self.db.add_section(
                cloned_title,
                section_type,
                parent_id,
                next_placement
            )

            # Recursively clone children
            def clone_children(source_parent_id, new_parent_id):
                """
                source_parent_id: The ID of the original section whose children we're cloning
                new_parent_id: The ID of the new cloned parent where children will be attached
                """
                self.db.cursor.execute(
                    """
                    SELECT id, title, type, placement 
                    FROM sections 
                    WHERE parent_id = ? 
                    ORDER BY placement
                    """,
                    (source_parent_id,)
                )
                children = self.db.cursor.fetchall()
                
                for idx, (child_id, encrypted_title, child_type, _) in enumerate(children, 1):
                    # Decrypt the child's title
                    child_title = self.db.decrypt_safely(encrypted_title)
                    
                    # Add the cloned child with incremental placement
                    new_child_id = self.db.add_section(
                        child_title,  # Keep original title for children
                        child_type,
                        new_parent_id,
                        idx  # Use enumerated index for placement
                    )
                    
                    # Recursively clone this child's children
                    clone_children(child_id, new_child_id)

            # Start the recursive cloning
            clone_children(source_id, new_parent_id)
            
            # Refresh the tree and select the new cloned section
            self.refresh_tree()
            self.select_item(f"I{new_parent_id}")
            
            messagebox.showinfo(
                "Success", 
                f"Successfully cloned section '{original_title}'"
            )
            
        except Exception as e:
            print(f"Error cloning section: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to clone section: {str(e)}"
            )
            self.db.conn.rollback()

    # RIGHT CLICK CONTEXT NOTES
    
    def create_notes_context_menu(self):
        """Create and bind the context menu to the notes/questions text area."""
        self.notes_menu = tk.Menu(self.questions_text, tearoff=0)
        self.notes_menu.add_command(label="Select All", command=self.notes_select_all)
        self.notes_menu.add_separator()
        self.notes_menu.add_command(label="Copy", command=self.notes_copy)
        self.notes_menu.add_command(label="Paste", command=self.notes_paste)
        
        # Bind right-click to show the context menu
        self.questions_text.bind("<Button-3>", self.show_notes_context_menu)

    def show_notes_context_menu(self, event):
        """Display the context menu for the notes area at the pointer location."""
        try:
            # Enable/disable copy based on whether there's a selection
            if self.questions_text.tag_ranges("sel"):
                self.notes_menu.entryconfig("Copy", state="normal")
            else:
                self.notes_menu.entryconfig("Copy", state="disabled")
            
            self.notes_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Error showing notes context menu: {e}")

    def notes_select_all(self):
        """Select all text in the notes area."""
        try:
            self.questions_text.tag_add("sel", "1.0", "end-1c")
            self.questions_text.mark_set("insert", "1.0")
            self.questions_text.see("insert")
        except Exception as e:
            print(f"Error in select all: {e}")

    def notes_copy(self):
        """Copy selected text to clipboard."""
        try:
            if self.questions_text.tag_ranges("sel"):
                selected_text = self.questions_text.get("sel.first", "sel.last")
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
        except Exception as e:
            print(f"Error in copy: {e}")

    def notes_paste(self):
        """Paste clipboard content into notes area, replacing selection if exists."""
        try:
            # Get clipboard content
            clipboard_text = self.root.clipboard_get()
            
            # If there's a selection, delete it first
            if self.questions_text.tag_ranges("sel"):
                self.questions_text.delete("sel.first", "sel.last")
            
            # Insert clipboard content at current cursor position
            self.questions_text.insert("insert", clipboard_text)
        except tk.TclError:  # Empty clipboard
            pass
        except Exception as e:
            print(f"Error in paste: {e}")


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
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)   # Bind for handling lazy loading on expand
        self._selection_binding = self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        # Search Frame with new controls
        search_frame = ttk.Frame(self.tree_frame)
        search_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0), padx=label_padx)
        search_frame.grid_columnconfigure(1, weight=1)  # Make the entry expand

        # Search label
        ttk.Label(search_frame, text="Search", bootstyle="info").grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        # Search entry
        self.search_entry = ttk.Entry(search_frame, bootstyle="info")
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.search_entry.bind("<Return>", self.execute_search)

        # Global search checkbox
        self.global_search_var = tk.BooleanVar(value=False)
        self.global_search_cb = ttk.Checkbutton(
            search_frame,
            text="Global",
            variable=self.global_search_var,
            bootstyle="info-round-toggle"
        )
        self.global_search_cb.grid(row=0, column=2, padx=5)

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
        self.questions_text = tk.Text(self.editor_frame, height=15, font=NOTES_FONT)
        self.questions_text.grid(row=3, column=0, sticky="nswe", pady=section_pady)
        
        # Create and bind the notes context menu
        self.create_notes_context_menu()

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
            ttk.Button(self.editor_buttons, text=text, command=command, bootstyle=style).pack(
                side=tk.LEFT, padx=button_padx
            )

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

        # Export scope checkbox
        self.export_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.exports_frame,
            text="Export All Sections",
            variable=self.export_all,
            bootstyle="info-round-toggle"
        ).grid(row=0, column=0, sticky="w", padx=label_padx, pady=label_pady)

        # Buttons Frame (Bottom)
        self.exports_buttons = ttk.Frame(self.exports_tab)
        self.exports_buttons.grid(row=1, column=0, sticky="ew", padx=frame_padx, pady=frame_pady)

        ttk.Button(
            self.exports_buttons, 
            text="Make DOCX", 
            command=self.handle_export_docx,
            bootstyle="success"
        ).pack(side=tk.LEFT, padx=button_padx, pady=button_padx)

        ttk.Button(
            self.exports_buttons, 
            text="Make PDF", 
            command=self.handle_export_pdf,
            bootstyle="success"
        ).pack(side=tk.LEFT, padx=button_padx, pady=button_padx)

        ttk.Button(
            self.exports_buttons, 
            text="Titles to JSON", 
            command=self.export_titles_to_json,
            bootstyle="info"
        ).pack(side=tk.LEFT, padx=button_padx, pady=button_padx)


    # TREE MANIPULATION

    @timer
    def add_section(self, section_type, parent_id=None, title_prefix="Section"):
        """
        Add a new section to the tree with proper encryption.
        """
        if not self.is_authenticated or not self.encryption_manager:
            messagebox.showerror("Error", "Not authenticated. Please verify your password.")
            return

        try:
            # Calculate the next placement value
            self.db.cursor.execute(
                """
                SELECT COALESCE(MAX(placement), 0) + 1
                FROM sections
                WHERE parent_id IS ?
                """,
                (parent_id,)
            )
            next_placement = self.db.cursor.fetchone()[0]
            if next_placement <= 0:
                next_placement = 1

            title = f"{title_prefix} {next_placement}"
            
            # Add the section to database
            section_id = self.db.add_section(title, section_type, parent_id, next_placement)
            
            # Force clear any caching
            self.db.invalidate_caches()
            
            # Clear the tree and reload
            self.tree.delete(*self.tree.get_children())
            self.load_from_database()
            
            # Select and make visible the new item
            new_item_id = f"I{section_id}"
            if self.tree.exists(new_item_id):
                self.tree.selection_set(new_item_id)
                self.tree.focus(new_item_id)
                self.tree.see(new_item_id)
            
            # Force an immediate update of numbering
            self.db.conn.commit()
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)
            
            return section_id

        except Exception as e:
            print(f"Error adding section: {e}")
            return None

    @timer
    def refresh_tree(self, event=None):
        """
        Reload the TreeView to reflect database changes while preserving expansion state and selection.
        """
        try:
            # Store currently selected item before refresh
            selected = self.tree.selection()
            selected_db_id = self.get_item_id(selected[0]) if selected else None
            
            # Get currently expanded items before refresh
            expanded_db_ids = self.get_expanded_items()
            
            # Temporarily unbind selection event
            if self._selection_binding:
                self.tree.unbind("<<TreeviewSelect>>", self._selection_binding)
            
            # Clear the tree and caches
            self.tree.delete(*self.tree.get_children())
            self.db.invalidate_caches()  # Force cache invalidation on refresh
            
            # Reload the tree
            self.load_from_database()
            
            # Restore expansion state
            self.restore_expansion_state(expanded_db_ids)
            
            # Update numbering with fresh numbering
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)
            
            # Restore selection if possible
            if selected_db_id is not None:
                self.select_item(selected_db_id)
            
            # Rebind selection event
            self._selection_binding = self.tree.bind("<<TreeviewSelect>>", self.load_selected)
            
        except Exception as e:
            print(f"Error in refresh_tree: {e}")
            # Ensure event is rebound even if there's an error
            if not self._selection_binding:
                self._selection_binding = self.tree.bind("<<TreeviewSelect>>", self.load_selected)

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
        try:
            children = self.db.load_children(parent_id)
            for child_id, encrypted_title, _ in children:
                # Only show items that match the search or are parents of matching items
                if child_id in ids_to_show or child_id in parents_to_show:
                    # Decrypt the title using cached value if available
                    decrypted_title = None
                    if str(child_id) in self.db._search_cache:
                        decrypted_title = self.db._search_cache[str(child_id)]['title']
                    else:
                        decrypted_title = self.db.decrypt_safely(encrypted_title)
                        
                    node = self.tree.insert(parent_node, "end", f"I{child_id}", text=decrypted_title)
                    self.tree.see(node)  # Ensure the node is visible
                    
                    # Recursively populate children
                    self.populate_filtered_tree(child_id, node, ids_to_show, parents_to_show)
        except Exception as e:
            print(f"Error in populate_filtered_tree: {e}")

    @timer
    def move_up(self):
        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])
        parent_node = self.tree.parent(selected[0])
        parent_db_id = self.get_item_id(parent_node) if parent_node else None

        try:
            # Fix consecutive placements first
            if parent_db_id is None:
                self.db.fix_all_placements()
            else:
                self.db.fix_placement(parent_db_id)

            # Get current placement
            self.db.cursor.execute(
                "SELECT placement FROM sections WHERE id = ? AND parent_id IS ?",
                (item_id, parent_db_id)
            )
            current_placement = self.db.cursor.fetchone()
            
            if not current_placement:
                return
                
            current_placement = current_placement[0]
            
            if current_placement > 1:  # Can only move up if not already at top
                # Swap with the item above
                self.db.cursor.execute(
                    """
                    UPDATE sections
                    SET placement = CASE 
                        WHEN placement = ? THEN ? 
                        WHEN placement = ? THEN ? 
                    END
                    WHERE parent_id IS ? AND placement IN (?, ?)
                    """,
                    (current_placement, current_placement - 1,
                     current_placement - 1, current_placement,
                     parent_db_id, current_placement, current_placement - 1)
                )
                self.db.conn.commit()

            # Force cache invalidation and refresh
            self.db.invalidate_caches()
            self.refresh_tree()
            self.select_item(f"I{item_id}")
            
        except Exception as e:
            print(f"Error in move_up: {e}")
            self.db.conn.rollback()

    @timer
    def move_down(self):
        selected = self.tree.selection()
        if not selected:
            return

        item_id = self.get_item_id(selected[0])
        parent_node = self.tree.parent(selected[0])
        parent_db_id = self.get_item_id(parent_node) if parent_node else None

        try:
            # Fix consecutive placements first
            if parent_db_id is None:
                self.db.fix_all_placements()
                self.db.cursor.execute(
                    "SELECT MAX(placement) FROM sections WHERE parent_id IS NULL"
                )
            else:
                self.db.fix_placement(parent_db_id)
                self.db.cursor.execute(
                    "SELECT MAX(placement) FROM sections WHERE parent_id = ?",
                    (parent_db_id,)
                )
            max_placement = self.db.cursor.fetchone()[0]

            # Get current placement
            self.db.cursor.execute(
                "SELECT placement FROM sections WHERE id = ? AND parent_id IS ?",
                (item_id, parent_db_id)
            )
            current_placement = self.db.cursor.fetchone()
            
            if not current_placement:
                return
                
            current_placement = current_placement[0]

            if current_placement < max_placement:  # Can only move down if not at bottom
                # Swap with the item below
                self.db.cursor.execute(
                    """
                    UPDATE sections
                    SET placement = CASE 
                        WHEN placement = ? THEN ? 
                        WHEN placement = ? THEN ? 
                    END
                    WHERE parent_id IS ? AND placement IN (?, ?)
                    """,
                    (current_placement, current_placement + 1,
                     current_placement + 1, current_placement,
                     parent_db_id, current_placement, current_placement + 1)
                )
                self.db.conn.commit()

            # Force cache invalidation and refresh
            self.db.invalidate_caches()
            self.refresh_tree()
            self.select_item(f"I{item_id}")
            
        except Exception as e:
            print(f"Error in move_down: {e}")
            self.db.conn.rollback()

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

        grandparent_node = self.tree.parent(current_parent_id)
        grandparent_id = self.get_item_id(grandparent_node) if grandparent_node else None
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

        # Update database with proper ID conversion
        parent_db_id = self.get_item_id(current_parent_id)
        self.db.cursor.execute(
            "UPDATE sections SET parent_id = ?, type = ? WHERE id = ?",
            (grandparent_id, new_type, item_id)
        )

        # Fix placements
        self.db.fix_placement(parent_db_id)
        if grandparent_id:
            self.db.fix_placement(grandparent_id)

        self.db.conn.commit()
        self.refresh_tree()
        self.select_item(f"I{item_id}")

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

        new_parent_node = siblings[index - 1]
        new_parent_id = self.get_item_id(new_parent_node)
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

        # Update database with proper ID conversion
        parent_db_id = self.get_item_id(current_parent_id) if current_parent_id else None
        self.db.cursor.execute(
            "UPDATE sections SET parent_id = ?, type = ? WHERE id = ?",
            (new_parent_id, new_type, item_id)
        )

        # Fix placements
        if parent_db_id:
            self.db.fix_placement(parent_db_id)
        self.db.fix_placement(new_parent_id)

        self.db.conn.commit()
        self.refresh_tree()
        self.select_item(f"I{item_id}")

    @timer
    def calculate_numbering(self, numbering_dict):
        """
        Assign hierarchical numbering to tree nodes based on the provided numbering dictionary.
        """
        try:
            for node_id in self.tree.get_children():
                self._apply_numbering_recursive(node_id, numbering_dict)
        except Exception as e:
            print(f"Error in calculate_numbering: {e}")

    @timer
    def _apply_numbering_recursive(self, node_id, numbering_dict):
        """
        Apply numbering to a node and its children recursively.
        """
        try:
            # Skip hidden nodes
            if "hidden" in self.tree.item(node_id, "tags"):
                return

            db_id = self.get_item_id(node_id)
            if db_id is not None and db_id in numbering_dict:
                current_text = self.tree.item(node_id, "text")
                if '. ' in current_text:
                    base_text = current_text.split('. ', 1)[1]
                else:
                    base_text = current_text
                
                new_text = f"{numbering_dict[db_id]}. {base_text}"
                self.tree.item(node_id, text=new_text)

            # Process children
            for child_id in self.tree.get_children(node_id):
                self._apply_numbering_recursive(child_id, numbering_dict)
        except Exception as e:
            print(f"Error in _apply_numbering_recursive: {e}")

    @timer
    def update_tree_item(self, item_id, new_title):
        """Update a single tree item's text and numbering without full refresh."""
        try:
            # Get the current numbering
            numbering_dict = self.db.generate_numbering()
            
            # Find and update the item - try both with and without the "I" prefix
            item_iid = f"I{item_id}"  # First try with "I" prefix
            if not self.tree.exists(item_iid):
                item_iid = str(item_id)  # Try without prefix
                
            if self.tree.exists(item_iid):
                # Apply numbering format
                if item_id in numbering_dict:
                    display_title = f"{numbering_dict[item_id]}. {new_title}"
                else:
                    display_title = new_title
                
                self.tree.item(item_iid, text=display_title)
                self.tree.update()  # Force visual refresh
                
        except Exception as e:
            print(f"Error updating tree item: {e}")

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
        """Select and focus an item in the treeview without triggering selection event."""
        try:
            if self.tree.exists(str(item_id)):
                self._suppress_selection_event = True  # Set flag before selection
                self.tree.selection_set(str(item_id))
                self.tree.focus(str(item_id))
                self.tree.see(str(item_id))
                self._suppress_selection_event = False  # Reset flag after selection
        except Exception as e:
            self._suppress_selection_event = False  # Reset flag in case of error
            print(f"Error in select_item: {e}")


    # CRUD RELATED

    @timer
    def handle_load_database(self):
        """Handle loading a database file with proper encryption management."""
        file_path = askopenfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db")],
            title="Select Database File"
        )
        if not file_path:
            return False  # User cancelled file selection

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
                dialog = PasswordDialog(
                    self.root,
                    "Database Password",
                    "Enter the password for this database:"
                )
                self.root.wait_window(dialog)
                password = dialog.result
                
                if password is None:
                    return False  # User cancelled password entry

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
                    self.db.encryption_manager = test_manager
                    self.is_authenticated = True
                    self.password_validated = True
                    self.update_title() 
                    
                    # Clear editor fields
                    self.title_entry.delete(0, tk.END)
                    self.questions_text.delete(1.0, tk.END)
                    self.last_selected_item_id = None
                    
                    # Enable UI and refresh tree
                    self.set_ui_state(True)
                    self.refresh_tree()
                    
                    messagebox.showinfo("Success", f"Database loaded successfully from {file_path}")
                    return True
                        
                except Exception as e:
                    print(f"Validation error: {e}")
                    messagebox.showerror("Error", f"Failed to validate password: {e}")
                    continue

        except Exception as e:
            print(f"Database loading error: {e}")
            messagebox.showerror("Error", f"Failed to load database: {e}")
            self.handle_authentication_failure("Failed to authenticate with the loaded database.")
            return False

        return False

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
            # Verify the database file
            temp_conn = sqlite3.connect(db_path)
            temp_cursor = temp_conn.cursor()
            
            # Check if the settings table exists
            temp_cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='settings'
                """
            )
            if not temp_cursor.fetchone():
                temp_conn.close()
                raise ValueError("Invalid database: 'settings' table not found.")
                
            # Check for a stored password
            temp_cursor.execute(
                "SELECT value FROM settings WHERE key = ?",
                ("password",)
            )
            stored_password = temp_cursor.fetchone()
            temp_conn.close()
            
            if stored_password:
                # Prompt user for the password
                while True:
                    password = simpledialog.askstring(
                        "Database Password",
                        "Enter the password for this database:",
                        show="*"
                    )
                    if not password:
                        # Close the application entirely if canceled
                        self.root.destroy()  # Close the main application window
                        sys.exit()  # Ensure the process exits completely

                    # Create a temporary encryption manager to verify the password
                    temp_encryption_manager = EncryptionManager(password)

                    # Reconnect to verify the password
                    temp_conn = sqlite3.connect(db_path)
                    temp_cursor = temp_conn.cursor()
                    stored_hash = temp_cursor.execute(
                        "SELECT value FROM settings WHERE key = ?",
                        ("password",)
                    ).fetchone()[0]
                    
                    if hashlib.sha256(password.encode()).hexdigest() != stored_hash:
                        temp_conn.close()
                        messagebox.showerror("Invalid Password", "The password is incorrect. Try again.")
                        continue

                    # Password verified
                    self.encryption_manager = temp_encryption_manager
                    break

            # Replace the current database connection
            self.conn.close()
            self.db_name = db_path
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()

            # Ensure the schema is valid
            self.cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='sections'
                """
            )
            if not self.cursor.fetchone():
                raise ValueError("Invalid database: 'sections' table not found.")

            # Set up the database if needed
            self.setup_database()

        except sqlite3.DatabaseError:
            raise RuntimeError("The selected file is not a valid SQLite database.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.root.destroy()  # Close the main application window
            sys.exit()  # Terminate the application

    @timer
    def load_selected(self, event):
        """Load the selected item and populate the editor with decrypted data."""
        if not self.is_authenticated or not self.encryption_manager:
            return

        # If selection event is suppressed, ignore it
        if self._suppress_selection_event:
            return

        selected = self.tree.selection()
        if not selected:
            return

        current_item_id = self.get_item_id(selected[0])
        if current_item_id == self.last_selected_item_id:
            return  # Don't reload if selecting the same item

        try:
            # Save data for the previous item before loading new one
            if self.last_selected_item_id is not None:
                self._suppress_selection_event = True  # Suppress selection events
                
                # Get current title from entry before saving
                current_title = self.title_entry.get().strip()
                
                self.save_data(refresh=False)  # Save without immediate refresh
                
                # Debug: Check what's in the database after save
                self.db.cursor.execute(
                    "SELECT title FROM sections WHERE id = ?", (self.last_selected_item_id,)
                )
                row = self.db.cursor.fetchone()
                if row and row[0]:
                    decrypted_title = self.encryption_manager.decrypt_string(row[0])
                    self.update_tree_item(self.last_selected_item_id, decrypted_title)
                
                self._suppress_selection_event = False  # Re-enable selection events
                self.previous_item_id = self.last_selected_item_id  # Track previous item

            # Update selection tracking
            self.last_selected_item_id = current_item_id

            # Load the newly selected item's data
            self.db.encryption_manager = self.encryption_manager
            row = self.db.cursor.execute(
                "SELECT title, questions FROM sections WHERE id = ?", (current_item_id,)
            ).fetchone()

            if row:
                self.title_entry.delete(0, tk.END)
                self.questions_text.delete(1.0, tk.END)

                title, encrypted_questions = row
                decrypted_title = self.encryption_manager.decrypt_string(title)
                self.title_entry.insert(0, decrypted_title if decrypted_title else "")

                if encrypted_questions:
                    decrypted_questions = self.encryption_manager.decrypt_string(
                        encrypted_questions
                    )
                    parsed_questions = json.loads(decrypted_questions.strip())
                    self.questions_text.insert(tk.END, "\n".join(parsed_questions))

        except Exception as e:
            print(f"Selection loading error: {e}")
            self.handle_authentication_failure("Decryption failed. Please verify your password.")
            return

    @timer
    def save_data(self, event=None, refresh=True):
        """Save data with authentication check."""
        if not self.is_authenticated or self.last_selected_item_id is None:
            return

        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Error", "Title cannot be empty.")
            return

        try:
            # Get raw text content and split by newlines while preserving empty lines
            raw_text = self.questions_text.get(1.0, tk.END).rstrip()
            questions = raw_text.split("\n")
            # Keep empty lines by only filtering out lines that are actually None
            questions = [q if q else "" for q in questions]
            questions_json = json.dumps(questions)
            
            self.db.update_section(self.last_selected_item_id, title, questions_json)

            if refresh:
                self.refresh_tree()
                self.select_item(self.last_selected_item_id)
            self.update_title() 

        except Exception as e:
            print(f"Encryption Error: {e}")
            self.handle_authentication_failure("Encryption failed. Please verify your password.")
            return

    @timer
    def delete_selected(self):
        """Deletes the selected item and all its children."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Please select an item to delete.")
            return

        item_id = self.get_item_id(selected[0])
        item_type = self.get_item_type(selected[0])

        # Get number of children that will be deleted
        child_count = self.db.count_descendants(item_id)
        warning = f"Delete this {item_type}"
        if child_count > 0:
            warning += f" and its {child_count} child items? This cannot be undone."
        else:
            warning += "? This cannot be undone."

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            warning,
        )
        if confirm:
            # Delete section and all descendants
            self.db.delete_section(item_id)

            # Remove the item from the Treeview
            self.tree.delete(selected[0])

            # Reset the editor and last selected item
            self.last_selected_item_id = None
            self.title_entry.delete(0, tk.END)
            self.questions_text.delete(1.0, tk.END)

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
                    f"Enter a new password for this database (min. {PASSWORD_MIN_LENGTH} characters):",
                    show="*"
                )
                if not password:
                    return  # User cancelled
                    
                if len(password) < PASSWORD_MIN_LENGTH:
                    messagebox.showerror(
                        "Invalid Password", 
                        f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
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
            
            self.update_title()
            
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

    def get_item_type(self, node):
        """Fetch the type of the selected node using DatabaseHandler."""
        try:
            item_id = self.get_item_id(node)
            return self.db.get_section_type(item_id) if item_id is not None else None
        except Exception as e:
            print(f"Error in get_item_type: {e}")
            return None

    @timer
    def initialize_placement(self):
        """Assign default placement for existing rows and ensure they are consecutive."""
        try:
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
            
            # After initializing, fix to ensure they're consecutive
            self.fix_all_placements()
            
        except Exception as e:
            print(f"Error in initialize_placement: {e}")
            self.conn.rollback()

    # JSON
    
    def export_titles_to_json(self):
        export_all = self.export_all.get()
        node_id = None

        if not export_all:
            selected = self.tree.selection()
            if selected:
                node_id = self.get_item_id(selected[0])
                decrypted_title = self.tree.item(selected[0])['text']
                if '. ' in decrypted_title:
                    decrypted_title = decrypted_title.split('. ', 1)[1]
                
                confirm = messagebox.askyesno(
                    "Export Selection",
                    f"Export '{decrypted_title}' and its subsections to JSON?",
                    icon='info'
                )
                if not confirm:
                    return
            else:
                export_all = True

        if export_all:
            confirm = messagebox.askyesno(
                "Full Export Warning",
                "This will export all titles which may take time for decryption. Continue?",
                icon='warning'
            )
            if not confirm:
                return

        try:
            data = self.build_hierarchy(node_id)
            file_path = asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON Files", "*.json")],
                title="Save JSON Export"
            )
            if not file_path:
                return

            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)

            messagebox.showinfo("Success", f"Exported titles to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

    def build_hierarchy(self, node_id):
        def get_level_key(level):
            return "children" if level > 4 else f"h{level}"

        def add_children(parent_id, level):
            children = self.db.load_children(parent_id)
            result = []
            for child_id, encrypted_title, _ in children:
                title = self.db.decrypt_safely(encrypted_title)
                child_hierarchy = {"name": title}
                
                has_children = self.db.has_children(child_id)
                next_level_key = get_level_key(level + 1)
                
                if has_children:
                    child_hierarchy[next_level_key] = add_children(child_id, level + 1)
                else:
                    child_hierarchy[next_level_key] = []
                    
                result.append(child_hierarchy)
            return result

        root_title = self.db.get_section_title(node_id)
        hierarchy = {
            "h1": [
                {
                    "name": root_title,
                    "h2": add_children(node_id, 2)
                }
            ]
        }
        return hierarchy

    # DOCX
    
    def handle_export_docx(self):
        export_all = self.export_all.get()
        root_id = None
        
        if not export_all:
            selected = self.tree.selection()
            if selected:
                root_id = self.get_item_id(selected[0])
                level = self.db.get_section_level(root_id)
                decrypted_title = self.tree.item(selected[0])['text']
                if '. ' in decrypted_title:
                    decrypted_title = decrypted_title.split('. ', 1)[1]
                
                confirm = messagebox.askyesno(
                    "Export Selection",
                    f"Export '{decrypted_title}' (Level {level}) and all its subsections?",
                    icon='info'
                )
                if not confirm:
                    return
            else:
                export_all = True  # Default to all if nothing selected
        
        if export_all:
            confirm = messagebox.askyesno(
                "Full Export Warning",
                "This will export the entire document which may take some time for decryption. Continue?",
                icon='warning'
            )
            if not confirm:
                return
                
        export_to_docx(self.db, root_id)


    # PDF
    
    def handle_export_pdf(self):
        export_all = self.export_all.get()
        root_id = None
        
        if not export_all:
            selected = self.tree.selection()
            if selected:
                root_id = self.get_item_id(selected[0])
                level = self.db.get_section_level(root_id)
                decrypted_title = self.tree.item(selected[0])['text']
                if '. ' in decrypted_title:
                    decrypted_title = decrypted_title.split('. ', 1)[1]
                
                confirm = messagebox.askyesno(
                    "Export Selection",
                    f"Export '{decrypted_title}' (Level {level}) and all its subsections?",
                    icon='info'
                )
                if not confirm:
                    return
            else:
                export_all = True  # Default to all if nothing selected
        
        if export_all:
            confirm = messagebox.askyesno(
                "Full Export Warning",
                "This will export the entire document which may take some time for decryption. Continue?",
                icon='warning'
            )
            if not confirm:
                return
                
        export_to_pdf(self.db, root_id)
    
    # SEARCH

    @timer
    def execute_search(self, event=None):
        """Enhanced search with support for local/global search."""
        query = self.search_entry.get().strip()
        if not query:
            self.load_from_database()
            return

        try:
            global_search = self.global_search_var.get()
            if global_search:
                confirm = messagebox.askyesno(
                    "Global Search",
                    "Global search requires decrypting all records and may take several minutes. Continue?"
                )
                if not confirm:
                    return

            # Get current selection for local search
            selected = self.tree.selection()
            node_id = None
            if selected and not global_search:
                node_id = self.get_item_id(selected[0])

            # Perform search
            ids_to_show, parents_to_show = self.db.search_sections(
                query,
                node_id=node_id,
                global_search=global_search
            )

            if not ids_to_show and not parents_to_show:
                messagebox.showinfo("Search Results", "No matches found.")
                return

            # Clear and repopulate tree
            self.tree.delete(*self.tree.get_children())
            self.populate_filtered_tree(None, "", ids_to_show, parents_to_show)

            # Apply numbering
            numbering_dict = self.db.generate_numbering()
            self.calculate_numbering(numbering_dict)

        except Exception as e:
            print(f"Error in execute_search: {e}")
            messagebox.showerror("Search Error", f"An error occurred while searching: {str(e)}")

    # UTILITY

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