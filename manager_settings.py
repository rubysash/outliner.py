import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk, messagebox
import json
from typing import Dict, Any

from config import (
    VERSION, DB_NAME, PASSWORD_MIN_LENGTH, WARNING_LIMIT_ITEM_COUNT, 
    WARNING_DISPLAY_TIME_MS, GLOBAL_FONT_FAMILY, GLOBAL_FONT_SIZE,
    NOTES_FONT_FAMILY, NOTES_FONT_SIZE, DOC_FONT, H1_SIZE, H2_SIZE,
    H3_SIZE, H4_SIZE, P_SIZE, INDENT_SIZE, TIMER_ENABLED,
    MIN_TIME_IN_MS_THRESHOLD, MAX_TIME_IN_MS_THRESHOLD, THEME
)

class SettingsTab:
    def __init__(self, parent, db_handler=None, questions_text=None):
        self.parent = parent
        self.db = db_handler
        self.questions_text = questions_text
        self.changes_made = False
        self.original_settings = {}
        self.current_settings = {}
        
        # Create main frame
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add scrollable canvas
        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create all sections
        self.create_app_settings()
        self.create_ui_settings()
        self.create_doc_settings()
        self.create_timer_settings()
        self.create_button_frame()
        
        # Bind the theme change
        self.theme_var.trace_add("write", self.handle_theme_change)
        
        # Verify and load settings
        if self.db:
            self.verify_settings_complete()
            self.load_settings()
        
        # Bind mouse wheel to scroll
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def verify_settings_complete(self):
        """Verify all required settings exist in database."""
        try:
            # Define required settings with their default values from config
            required_settings = {
                "THEME": THEME, 
                "VERSION": VERSION,
                "DB_NAME": DB_NAME,
                "PASSWORD_MIN_LENGTH": str(PASSWORD_MIN_LENGTH),
                "WARNING_LIMIT_ITEM_COUNT": str(WARNING_LIMIT_ITEM_COUNT),
                "WARNING_DISPLAY_TIME_MS": str(WARNING_DISPLAY_TIME_MS),
                "GLOBAL_FONT_FAMILY": GLOBAL_FONT_FAMILY,
                "GLOBAL_FONT_SIZE": str(GLOBAL_FONT_SIZE),
                "NOTES_FONT_FAMILY": NOTES_FONT_FAMILY,
                "NOTES_FONT_SIZE": str(NOTES_FONT_SIZE),
                "DOC_FONT": DOC_FONT,
                "H1_SIZE": str(H1_SIZE),
                "H2_SIZE": str(H2_SIZE),
                "H3_SIZE": str(H3_SIZE),
                "H4_SIZE": str(H4_SIZE),
                "P_SIZE": str(P_SIZE),
                "INDENT_SIZE": str(INDENT_SIZE),
                "TIMER_ENABLED": str(TIMER_ENABLED).lower(),
                "MIN_TIME_IN_MS_THRESHOLD": str(MIN_TIME_IN_MS_THRESHOLD),
                "MAX_TIME_IN_MS_THRESHOLD": str(MAX_TIME_IN_MS_THRESHOLD)
            }

            # Get existing settings from database
            self.db.cursor.execute("SELECT key FROM settings WHERE key != 'password'")
            existing_keys = {row[0] for row in self.db.cursor.fetchall()}

            # Find missing settings
            missing_settings = {k: v for k, v in required_settings.items() if k not in existing_keys}

            if missing_settings:
                print(f"Adding missing settings: {', '.join(missing_settings.keys())}")
                self.db.cursor.execute("BEGIN")
                try:
                    for key, value in missing_settings.items():
                        self.db.cursor.execute(
                            "INSERT INTO settings (key, value) VALUES (?, ?)",
                            (key, str(value))
                        )
                    self.db.conn.commit()
                    print("Successfully added missing settings")
                except Exception as e:
                    self.db.conn.rollback()
                    print(f"Error adding settings: {e}")
                    raise

            # Verify all settings have non-empty values
            self.db.cursor.execute("SELECT key, value FROM settings WHERE key != 'password'")
            empty_settings = {row[0] for row in self.db.cursor.fetchall() if not row[1]}
            
            if empty_settings:
                print(f"Updating empty settings: {', '.join(empty_settings)}")
                self.db.cursor.execute("BEGIN")
                try:
                    for key in empty_settings:
                        if key in required_settings:
                            self.db.cursor.execute(
                                "UPDATE settings SET value = ? WHERE key = ?",
                                (str(required_settings[key]), key)
                            )
                    self.db.conn.commit()
                    print("Successfully updated empty settings")
                except Exception as e:
                    self.db.conn.rollback()
                    print(f"Error updating settings: {e}")
                    raise

        except Exception as e:
            print(f"Error verifying settings: {e}")
            if self.db:
                self.db.conn.rollback()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_section_frame(self, title):
        """Create a labeled frame for a settings section."""
        frame = ttk.LabelFrame(self.scrollable_frame, text=title, padding=10)
        frame.pack(fill="x", padx=5, pady=5)
        return frame

    def create_setting_row(self, frame, label_text, key, validator=None, widget_type="entry"):
        """Create a row with label and input widget."""
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=5, pady=2)
        
        label = ttk.Label(row, text=label_text)
        label.pack(side="left", padx=(0, 10))
        
        def on_value_change(*args):
            self.changes_made = True
        
        if widget_type == "entry":
            var = tk.StringVar()
            widget = ttk.Entry(row, textvariable=var)
            widget.pack(side="right", expand=True, fill="x")
            var.trace_add("write", on_value_change)
            
            if validator:
                var.trace_add("write", lambda *args: self.validate_entry(key, var, validator))
            
            return var
        elif widget_type == "combobox":
            var = tk.StringVar()
            widget = ttk.Combobox(row, textvariable=var)
            widget.pack(side="right", expand=True, fill="x")
            var.trace_add("write", on_value_change)
            return var
        elif widget_type == "checkbox":
            var = tk.BooleanVar()
            widget = ttk.Checkbutton(row, variable=var)
            widget.pack(side="right")
            var.trace_add("write", on_value_change)
            return var

    def validate_entry(self, key: str, var: tk.StringVar, validator) -> None:
        value = var.get()
        
        entry_widget = None
        for child in self.scrollable_frame.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, ttk.Entry) and widget.cget('textvariable') == str(var):
                    entry_widget = widget
                    break
            if entry_widget:
                break
        
        if entry_widget and value:
            if validator(value):
                entry_widget.configure(style="TEntry")
                self.changes_made = True
            else:
                entry_widget.configure(style="Invalid.TEntry")

    def create_app_settings(self):
        frame = self.create_section_frame("Application Settings")
        
        # Define available themes
        # more at: https://ttkbootstrap.readthedocs.io/en/latest/themes/
        self.themes = [
            "darkly",   # Default first
            "cosmo",
            "litera", 
            "minty", 
            "pulse", 
            "sandstone", 
            "solar", 
            "superhero", 
            "flatly"
        ]
        
        # Add theme selector
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(row, text="Theme").pack(side="left", padx=(0, 10))
        
        self.theme_var = tk.StringVar(value=THEME)  # Default from config
        theme_combo = ttk.Combobox(
            row, 
            textvariable=self.theme_var,
            values=self.themes,
            state="readonly"  # Prevent manual entry
        )
        theme_combo.pack(side="right", expand=True, fill="x")
        
        # Add warning label for theme changes
        warning_row = ttk.Frame(frame)
        warning_row.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Label(
            warning_row,
            text="Note: Theme changes require application restart",
            font=("Helvetica", 8),
            foreground="gray"
        ).pack(side="left")
        
        # Add other settings
        self.app_vars = {
            "THEME": self.theme_var,  # Add theme to vars
            "VERSION": self.create_setting_row(frame, "Version", "VERSION"),
            "DB_NAME": self.create_setting_row(frame, "Database Name", "DB_NAME"),
            "PASSWORD_MIN_LENGTH": self.create_setting_row(
                frame, 
                "Min Password Length", 
                "PASSWORD_MIN_LENGTH",
                lambda x: x.isdigit() and int(x) >= 3
            ),
            "WARNING_LIMIT_ITEM_COUNT": self.create_setting_row(
                frame,
                "Warning Item Count",
                "WARNING_LIMIT_ITEM_COUNT",
                lambda x: x.isdigit()
            ),
            "WARNING_DISPLAY_TIME_MS": self.create_setting_row(
                frame,
                "Warning Display Time (ms)",
                "WARNING_DISPLAY_TIME_MS",
                lambda x: x.isdigit()
            )
        }
        
    def create_ui_settings(self):
        frame = self.create_section_frame("UI Settings")
        
        self.ui_vars = {
            "GLOBAL_FONT_FAMILY": self.create_setting_row(frame, "Global Font Family", "GLOBAL_FONT_FAMILY"),
            "GLOBAL_FONT_SIZE": self.create_setting_row(
                frame,
                "Global Font Size",
                "GLOBAL_FONT_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "NOTES_FONT_FAMILY": self.create_setting_row(frame, "Notes Font Family", "NOTES_FONT_FAMILY"),
            "NOTES_FONT_SIZE": self.create_setting_row(
                frame,
                "Notes Font Size",
                "NOTES_FONT_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            )
        }
        
    def create_doc_settings(self):
        frame = self.create_section_frame("Document Settings")
        
        self.doc_vars = {
            "DOC_FONT": self.create_setting_row(frame, "Document Font", "DOC_FONT"),
            "H1_SIZE": self.create_setting_row(
                frame,
                "H1 Size",
                "H1_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "H2_SIZE": self.create_setting_row(
                frame,
                "H2 Size",
                "H2_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "H3_SIZE": self.create_setting_row(
                frame,
                "H3 Size",
                "H3_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "H4_SIZE": self.create_setting_row(
                frame,
                "H4 Size",
                "H4_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "P_SIZE": self.create_setting_row(
                frame,
                "Paragraph Size",
                "P_SIZE",
                lambda x: x.isdigit() and 8 <= int(x) <= 72
            ),
            "INDENT_SIZE": self.create_setting_row(
                frame,
                "Indent Size",
                "INDENT_SIZE",
                lambda x: x.replace('.', '').isdigit()
            )
        }
        
    def create_timer_settings(self):
        frame = self.create_section_frame("Timer Settings")
        
        self.timer_vars = {
            "TIMER_ENABLED": self.create_setting_row(
                frame,
                "Enable Timer",
                "TIMER_ENABLED",
                widget_type="checkbox"
            ),
            "MIN_TIME_IN_MS_THRESHOLD": self.create_setting_row(
                frame,
                "Min Time Threshold (ms)",
                "MIN_TIME_IN_MS_THRESHOLD",
                lambda x: x.replace('.', '').isdigit()
            ),
            "MAX_TIME_IN_MS_THRESHOLD": self.create_setting_row(
                frame,
                "Max Time Threshold (ms)",
                "MAX_TIME_IN_MS_THRESHOLD",
                lambda x: x.replace('.', '').isdigit()
            )
        }
        
    def create_button_frame(self):
        """Create frame with Save and Reset buttons."""
        button_frame = ttk.Frame(self.scrollable_frame)
        button_frame.pack(fill="x", padx=5, pady=10)
        
        ttk.Button(
            button_frame,
            text="Save Changes",
            command=self.save_changes,
            style="success.TButton"
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self.reset_to_defaults,
            style="secondary.TButton"
        ).pack(side="left", padx=5)

    def load_settings(self):
        """Load settings from database or config defaults if not found."""
        try:
            if self.db:
                # Load defaults from config.py
                default_settings = {
                    "THEME": THEME,
                    "VERSION": VERSION,
                    "DB_NAME": DB_NAME,
                    "PASSWORD_MIN_LENGTH": str(PASSWORD_MIN_LENGTH),
                    "WARNING_LIMIT_ITEM_COUNT": str(WARNING_LIMIT_ITEM_COUNT),
                    "WARNING_DISPLAY_TIME_MS": str(WARNING_DISPLAY_TIME_MS),
                    "GLOBAL_FONT_FAMILY": GLOBAL_FONT_FAMILY,
                    "GLOBAL_FONT_SIZE": str(GLOBAL_FONT_SIZE),
                    "NOTES_FONT_FAMILY": NOTES_FONT_FAMILY,
                    "NOTES_FONT_SIZE": str(NOTES_FONT_SIZE),
                    "DOC_FONT": DOC_FONT,
                    "H1_SIZE": str(H1_SIZE),
                    "H2_SIZE": str(H2_SIZE),
                    "H3_SIZE": str(H3_SIZE),
                    "H4_SIZE": str(H4_SIZE),
                    "P_SIZE": str(P_SIZE),
                    "INDENT_SIZE": str(INDENT_SIZE),
                    "TIMER_ENABLED": str(TIMER_ENABLED).lower(),
                    "MIN_TIME_IN_MS_THRESHOLD": str(MIN_TIME_IN_MS_THRESHOLD),
                    "MAX_TIME_IN_MS_THRESHOLD": str(MAX_TIME_IN_MS_THRESHOLD)
                }

                # Load existing settings from database
                self.db.cursor.execute("SELECT key, value FROM settings WHERE key != 'password'")
                db_settings = dict(self.db.cursor.fetchall())

                # Merge defaults with database settings
                settings = default_settings.copy()
                settings.update(db_settings)  # Existing settings override defaults

                # After loading settings, ensure theme is valid
                current_theme = settings.get("THEME", THEME)
                if current_theme not in self.themes:
                    current_theme = THEME  # Reset to default if invalid
                    settings["THEME"] = THEME

                # Store settings
                self.original_settings = settings.copy()
                self.current_settings = settings.copy()

                # Update GUI
                self.update_gui_from_settings()

                # If there are new defaults not in the database, save them
                if not db_settings:  # First time setup
                    try:
                        self.db.cursor.execute("BEGIN")
                        for key, value in default_settings.items():
                            self.db.cursor.execute(
                                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                                (key, str(value))
                            )
                        self.db.conn.commit()
                        print("Default settings initialized in database")
                    except Exception as e:
                        self.db.conn.rollback()
                        print(f"Error saving default settings: {e}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load settings: {str(e)}")

    def update_gui_from_settings(self):
        """Update all GUI elements with current settings values."""
        for section_vars in [self.app_vars, self.ui_vars, self.doc_vars, self.timer_vars]:
            for key, var in section_vars.items():
                if key in self.current_settings:
                    value = self.current_settings[key]
                    if isinstance(var, tk.BooleanVar):
                        var.set(value.lower() in ('true', '1', 'yes'))
                    else:
                        var.set(str(value))

    def collect_current_values(self) -> Dict[str, str]:
        """Collect all current values from GUI elements."""
        values = {}
        
        for section_vars in [self.app_vars, self.ui_vars, self.doc_vars, self.timer_vars]:
            for key, var in section_vars.items():
                if isinstance(var, tk.BooleanVar):
                    values[key] = str(var.get()).lower()
                else:
                    values[key] = var.get()
        
        return values

    def handle_theme_change(self, *args):
        """Handle theme selection changes."""
        new_theme = self.theme_var.get()
        if new_theme != self.original_settings.get("THEME"):
            self.changes_made = True
            messagebox.showinfo(
                "Theme Change",
                "Theme changes will take effect after restarting the application."
            )

    def save_changes(self):
        """Save and apply settings changes."""
        if not self.db:
            messagebox.showerror("Error", "No database connection available")
            return
            
        values = self.collect_current_values()
        
        # Check if any values have actually changed
        has_changes = False
        restart_required = False
        for key, value in values.items():
            if key not in self.original_settings or str(value) != str(self.original_settings[key]):
                has_changes = True
                if key in ['THEME', 'TIMER_ENABLED', 'MIN_TIME_IN_MS_THRESHOLD', 'MAX_TIME_IN_MS_THRESHOLD']:
                    restart_required = True
                
        if not has_changes:
            messagebox.showinfo("Info", "No changes to save.")
            return
            
        try:
            # Start transaction
            self.db.cursor.execute("BEGIN")
            
            # Update or insert each setting
            for key, value in values.items():
                self.db.cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(value))
                )
            
            # Commit changes
            self.db.conn.commit()
            
            # Get reference to main app instance
            main_app = self.parent.master
            
            # Apply immediate changes where possible
            if not restart_required:
                # Update global font if changed
                if 'GLOBAL_FONT_FAMILY' in values or 'GLOBAL_FONT_SIZE' in values:
                    default_font = tkFont.nametofont("TkDefaultFont")
                    default_font.configure(
                        family=values.get('GLOBAL_FONT_FAMILY', GLOBAL_FONT_FAMILY),
                        size=int(values.get('GLOBAL_FONT_SIZE', GLOBAL_FONT_SIZE))
                    )
                
                # Update notes font if changed
                if 'NOTES_FONT_FAMILY' in values or 'NOTES_FONT_SIZE' in values:
                    new_font = (
                        values.get('NOTES_FONT_FAMILY', NOTES_FONT_FAMILY),
                        int(values.get('NOTES_FONT_SIZE', NOTES_FONT_SIZE))
                    )
                    if self.questions_text:
                        self.questions_text.configure(font=new_font)
                
                message = "Settings saved and applied successfully."
            else:
                message = "Settings saved successfully.\nSome changes require application restart."
                
            messagebox.showinfo("Success", message)
            self.original_settings = values.copy()
            self.changes_made = False
            
        except Exception as e:
            self.db.conn.rollback()
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def reset_to_defaults(self):
        """Reset all settings to their original values."""
        if messagebox.askyesno("Confirm Reset", "Reset all settings to their original values?"):
            self.current_settings = self.original_settings.copy()
            self.update_gui_from_settings()
            self.changes_made = True
            
