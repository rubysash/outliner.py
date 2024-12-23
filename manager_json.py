import json
from tkinter.filedialog import askopenfilename
from tkinter import messagebox

def load_from_json_file(cursor, db_handler, refresh_tree_callback=None):
    """
    Load JSON from a file and populate the database with hierarchical data.
    Args:
        cursor: SQLite database cursor for executing queries.
        db_handler: Instance of DatabaseHandler to interact with the database.
        refresh_tree_callback: Optional callback to refresh the tree view.
    """
    file_path = askopenfilename(
        filetypes=[("JSON Files", "*.json")], title="Select JSON File"
    )
    if not file_path:
        return  # User cancelled

    try:
        confirm = messagebox.askyesno(
            "Preload Warning",
            "Loading this JSON will populate the database and may cause duplicates. Do you want to continue?"
        )
        if not confirm:
            return

        with open(file_path, "r") as file:
            data = json.load(file)

        validate_json_structure(data)

        def insert_section(title, section_type, placement, parent_id=None):
            return db_handler.add_section(title, section_type, parent_id, placement)

        for h1_idx, h1_item in enumerate(data.get("h1", []), start=1):
            h1_id = insert_section(h1_item["name"], "header", h1_idx)
            for h2_idx, h2_item in enumerate(h1_item.get("h2", []), start=1):
                h2_id = insert_section(h2_item["name"], "category", h2_idx, h1_id)
                for h3_idx, h3_item in enumerate(h2_item.get("h3", []), start=1):
                    h3_id = insert_section(h3_item["name"], "subcategory", h3_idx, h2_id)
                    for h4_idx, h4_item in enumerate(h3_item.get("h4", []), start=1):
                        insert_section(h4_item["name"], "subheader", h4_idx, h3_id)

        messagebox.showinfo("Success", f"JSON data successfully loaded from {file_path}.")

        # Call the callback to refresh the tree if provided
        if refresh_tree_callback:
            refresh_tree_callback()

    except FileNotFoundError:
        messagebox.showerror("Error", f"File not found: {file_path}")
    except json.JSONDecodeError:
        messagebox.showerror("Error", "Invalid JSON format. Please select a valid JSON file.")
    except ValueError as ve:
        messagebox.showerror("Error", f"Invalid JSON structure: {ve}")
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")


def validate_json_structure(data):
    """
    Validate the hierarchical structure of the JSON data.
    Args:
        data: The JSON object to validate.
    Raises:
        ValueError: If the JSON structure is invalid.
    """
    if not isinstance(data, dict) or "h1" not in data:
        raise ValueError("Root JSON must be a dictionary with an 'h1' key.")

    for h1_item in data.get("h1", []):
        if not isinstance(h1_item, dict) or "name" not in h1_item:
            raise ValueError("Each 'h1' item must be a dictionary with a 'name'.")

        if "h2" in h1_item:
            if not isinstance(h1_item["h2"], list):
                raise ValueError("'h2' must be a list in 'h1' item.")

            for h2_item in h1_item["h2"]:
                if not isinstance(h2_item, dict) or "name" not in h2_item:
                    raise ValueError("Each 'h2' item must be a dictionary with a 'name'.")

                if "h3" in h2_item:
                    if not isinstance(h2_item["h3"], list):
                        raise ValueError("'h3' must be a list in 'h2' item.")

                    for h3_item in h2_item["h3"]:
                        if not isinstance(h3_item, dict) or "name" not in h3_item:
                            raise ValueError("Each 'h3' item must be a dictionary with a 'name'.")
