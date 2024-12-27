import json
from tkinter.filedialog import askopenfilename
from tkinter import messagebox

def validate_json_schema(data, max_depth=10):
    """Validates JSON structure for outline schema"""
    if not isinstance(data, dict):
        raise ValueError("Root must be an object")
    
    if "h1" not in data:
        raise ValueError("Root must have 'h1' key")
        
    if not isinstance(data["h1"], list):
        raise ValueError("h1 must be a list")

    def validate_node(node, level=1, path="root"):
        if not isinstance(node, dict):
            raise ValueError(f"Invalid node at {path}: must be an object")
            
        if "name" not in node:
            raise ValueError(f"Missing 'name' at {path}")
            
        if not isinstance(node["name"], str):
            raise ValueError(f"'name' must be string at {path}")
            
        if level >= max_depth:
            return
            
        # Check next level
        next_level = f"h{level+1}"
        if next_level in node:
            if not isinstance(node[next_level], list):
                raise ValueError(f"'{next_level}' must be a list at {path}")
            for idx, child in enumerate(node[next_level]):
                child_path = f"{path}.{next_level}[{idx}]"
                validate_node(child, level + 1, child_path)
                
        # Check children key
        if "children" in node:
            if not isinstance(node["children"], list):
                raise ValueError(f"'children' must be a list at {path}")
            for idx, child in enumerate(node["children"]):
                child_path = f"{path}.children[{idx}]"
                validate_node(child, level + 1, child_path)

    # Validate each h1 entry
    for idx, node in enumerate(data["h1"]):
        path = f"h1[{idx}]"
        validate_node(node, 1, path)
    
    return True

def load_from_json_file(cursor, db_handler, refresh_tree_callback=None):
    file_path = askopenfilename(
        filetypes=[("JSON Files", "*.json")], title="Select JSON File"
    )
    if not file_path:
        return

    sections_added = 0
    
    try:
        confirm = messagebox.askyesno(
            "Preload Warning",
            "Loading this JSON will populate the database and may cause duplicates. Do you want to continue?"
        )
        if not confirm:
            return

        with open(file_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        # Validate schema
        validate_json_schema(data)

        # Start transaction
        cursor.execute("BEGIN")
        
        def get_section_type(level):
            if level == 1:
                return "header"
            elif level == 2:
                return "category"
            elif level == 3:
                return "subcategory"
            else:
                return "subheader"

        def process_node(node, parent_id=None, level=1, placement=1):
            try:
                title = node.get("name", "")
                if not title:
                    return
                    
                section_type = get_section_type(level)
                nonlocal sections_added
                try:
                    section_id = db_handler.add_section(title, section_type, parent_id, placement)
                    sections_added += 1
                except Exception as e:
                    print(f"Error adding section '{title}': {e}")
                    raise ValueError(f"Failed to add section '{title}': {e}")

                # Process next level
                next_level_key = f"h{level+1}"
                children_key = "children"
                children = node.get(next_level_key, node.get(children_key, []))
                
                for idx, child in enumerate(children, start=1):
                    if isinstance(child, dict):
                        process_node(child, section_id, level+1, idx)
                        
            except Exception as e:
                print(f"Error processing node: {e}")
                raise

        # Process root level
        for idx, h1_item in enumerate(data.get("h1", []), start=1):
            process_node(h1_item, None, 1, idx)

        db_handler.conn.commit()
        messagebox.showinfo("Success", f"Successfully imported {sections_added} sections from {file_path}")
        
        if refresh_tree_callback:
            refresh_tree_callback()

    except json.JSONDecodeError:
        messagebox.showerror("Error", "Invalid JSON format")
    except ValueError as ve:
        messagebox.showerror("Error", f"Schema validation error: {str(ve)}")
    except Exception as e:
        if db_handler and db_handler.conn:
            db_handler.conn.rollback()
        messagebox.showerror("Error", f"Failed to import JSON: {str(e)}.\nSuccessfully imported {sections_added} sections before error.")
        print(f"Detailed error: {e}")

if __name__ == "__main__":
    # Test validation
    test_json = {
        "h1": [
            {
                "name": "Test",
                "h2": [
                    {
                        "name": "Subtest",
                        "h3": []
                    }
                ]
            }
        ]
    }
    try:
        validate_json_schema(test_json)
        print("Validation successful")
    except ValueError as e:
        print(f"Validation failed: {e}")