import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple

from config import (
    PASSWORD_MIN_LENGTH,
)

class PasswordDialog(tk.Toplevel):
    def __init__(
        self, 
        parent: tk.Tk,
        title: str,
        prompt: str,
        confirm_password: bool = False,
        min_length: int = PASSWORD_MIN_LENGTH
    ):
        super().__init__(parent)
        self.result: Optional[str | Tuple[str, str]] = None
        self.min_length = min_length
        
        # Configure dialog
        self.title(title)
        self.transient(parent)
        
        # Center the dialog
        window_width = 400
        window_height = 260 if confirm_password else 210
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        self.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        # Make dialog modal and unclosable
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.resizable(False, False)
        
        # Create main frame for proper padding
        main_frame = ttk.Frame(self)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # First password field
        ttk.Label(main_frame, text=prompt).pack(pady=(0,10))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            main_frame, 
            show="*", 
            textvariable=self.password_var
        )
        self.password_entry.pack(fill='x', pady=(0,10))
        
        # Second password field for confirmation if needed
        if confirm_password:
            ttk.Label(
                main_frame, 
                text="Confirm Password:"
            ).pack(pady=(10,10))
            self.confirm_var = tk.StringVar()
            self.confirm_entry = ttk.Entry(
                main_frame, 
                show="*", 
                textvariable=self.confirm_var
            )
            self.confirm_entry.pack(fill='x', pady=(0,10))
            
            # Add binding for Tab key to move between fields
            self.password_entry.bind('<Tab>', lambda e: self.confirm_entry.focus_set())
            self.confirm_entry.bind('<Tab>', lambda e: self.password_entry.focus_set())
            self.confirm_entry.bind('<Return>', lambda e: self.ok_clicked())
        else:
            self.password_entry.bind('<Tab>', lambda e: self.password_entry.focus_set())
        
        # Key bindings for OK/Cancel
        self.bind('<Return>', lambda e: self.ok_clicked())
        self.bind('<Escape>', lambda e: self.cancel_clicked())
        self.password_entry.bind('<Return>', lambda e: self.ok_clicked())
        
        # Focus handling
        self.attributes('-topmost', True)
        self.focus_set()
        self.password_entry.focus_set()
        
        # Aggressive focus - wait for window to be visible
        self.wait_visibility()
        self.focus_force()
        self.password_entry.focus_force()
        
    def ok_clicked(self, event=None):
        """Handle OK action (Enter key)"""
        password = self.password_var.get()
        
        if len(password) < self.min_length:
            messagebox.showerror(
                "Error", 
                f"Password must be at least {self.min_length} characters."
            )
            self.password_entry.focus_set()
            return
            
        if hasattr(self, 'confirm_var'):
            confirm = self.confirm_var.get()
            if password != confirm:
                messagebox.showerror(
                    "Error", 
                    "Passwords do not match."
                )
                self.confirm_entry.focus_set()
                return
            self.result = (password, confirm)
        else:
            self.result = password
            
        self.destroy()
        
    def cancel_clicked(self, event=None):
        """Handle Cancel action (Escape key)"""
        self.result = None
        self.destroy()

def get_password(
    parent: tk.Tk,
    title: str,
    prompt: str,
    confirm: bool = False,
    min_length: int = 3
) -> Optional[str | Tuple[str, str]]:
    """
    Show password dialog and return the password(s).
    
    Args:
        parent: Parent window
        title: Dialog title
        prompt: Password prompt text
        confirm: Whether to show confirmation field
        min_length: Minimum password length
        
    Returns:
        Single password string, or tuple of (password, confirmation),
        or None if cancelled
    """
    dialog = PasswordDialog(
        parent,
        title,
        prompt,
        confirm_password=confirm,
        min_length=min_length
    )
    parent.wait_window(dialog)
    return dialog.result