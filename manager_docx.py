from docx import Document
from docx.shared import Pt, Inches, RGBColor
import json
from config import DOC_FONT, H1_SIZE, H2_SIZE, H3_SIZE, H4_SIZE, P_SIZE, INDENT_SIZE
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox

from database import DatabaseHandler
from manager_encryption import EncryptionManager

def load_sections_for_export(db_handler: DatabaseHandler, root_id=None):
    """Load sections from database with optional root filtering."""
    db_handler.cursor.execute("""
        WITH RECURSIVE descendants AS (
            SELECT id, title, type, parent_id, questions, placement
            FROM sections
            WHERE id = ? OR (? IS NULL AND parent_id IS NULL)
            UNION ALL
            SELECT s.id, s.title, s.type, s.parent_id, s.questions, s.placement
            FROM sections s
            INNER JOIN descendants d ON s.parent_id = d.id
        )
        SELECT id, title, type, parent_id, questions 
        FROM descendants
        ORDER BY parent_id NULLS FIRST, placement, id
    """, (root_id, root_id))
    
    rows = db_handler.cursor.fetchall()
    decrypted_rows = []
    
    for row in rows:
        decrypted_title = db_handler.decrypt_safely(row[1], f"[Section {row[0]}]")
        decrypted_questions = db_handler.decrypt_safely(row[4], "[]")
        decrypted_rows.append((
            row[0],           # id
            decrypted_title,  # title
            row[2],          # type
            row[3],          # parent_id
            decrypted_questions  # questions
        ))
    
    return decrypted_rows

def export_to_docx(db_handler: DatabaseHandler, root_id=None):
    """Creates the docx file based on specs defined."""
    try:
        # Only show the warning if no section is selected
        if root_id is None:
            confirm = messagebox.askyesno(
                "Full Export Warning",
                "No section selected. This will export the entire document which may take some time. Continue?",
                icon='warning'
            )
            if not confirm:
                return

        sections = load_sections_for_export(db_handler, root_id)
        
        # Calculate level adjustment based on root depth
        level_adjustment = 0
        if root_id:
            root_level = db_handler.get_section_level(root_id)
            if root_level > 1:
                level_adjustment = -(root_level - 1)

        doc = Document()

        # Add Table of Contents Placeholder
        toc_paragraph = doc.add_paragraph("Table of Contents", style="Heading 1")
        toc_paragraph.add_run("\n(TOC will need to be updated in Word)").italic = True
        doc.add_page_break()

        def add_custom_heading(doc, text, original_level, level_adjustment=0):
            """Add a custom heading with specific formatting and indentation."""
            adjusted_level = max(1, original_level + level_adjustment)
            paragraph = doc.add_heading(level=min(adjusted_level, 9))
            run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
            run.text = text
            run.font.name = DOC_FONT
            run.bold = True

            # Apply colors and underline based on level
            if adjusted_level == 1:
                run.font.size = Pt(H1_SIZE)
                run.font.color.rgb = RGBColor(178, 34, 34)  # Brick red
            elif adjusted_level == 2:
                run.font.size = Pt(H2_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 128)  # Navy blue
            elif adjusted_level == 3:
                run.font.size = Pt(H3_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 0)  # Black
            elif adjusted_level == 4:
                run.font.size = Pt(H4_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 0)  # Black underline
                run.underline = True
            elif adjusted_level > 4:
                run.font.size = Pt(H4_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 0)  # Black underline

            indent = INDENT_SIZE * (adjusted_level - 1)
            paragraph.paragraph_format.left_indent = Inches(indent)
            return indent

        def add_custom_paragraph(doc, text, style="Normal", indent=0):
            """Add a custom paragraph with specific formatting."""
            paragraph = doc.add_paragraph(text, style=style)
            paragraph.paragraph_format.left_indent = Inches(indent)
            paragraph.paragraph_format.space_after = Pt(P_SIZE)
            if len(paragraph.runs) == 0:
                run = paragraph.add_run()
            else:
                run = paragraph.runs[0]
            run.font.name = DOC_FONT
            run.font.size = Pt(P_SIZE)
            return paragraph

        def add_to_doc(parent_id, level, numbering_prefix="", is_first_h1=True):
            """Recursively add sections and their children to the document with hierarchical numbering."""
            children = [s for s in sections if s[3] == parent_id]

            for idx, section in enumerate(children, start=1):
                number = f"{numbering_prefix}{idx}"
                title_with_number = f"{number}. {section[1]}"

                if level + level_adjustment == 1 and not is_first_h1:
                    doc.add_page_break()
                if level + level_adjustment == 1:
                    is_first_h1 = False

                parent_indent = add_custom_heading(doc, title_with_number, level, level_adjustment)

                try:
                    questions = json.loads(section[4]) if section[4] else []
                except json.JSONDecodeError:
                    questions = []

                if not questions:
                    add_custom_paragraph(
                        doc,
                        "(No questions added yet)",
                        style="Normal",
                        indent=parent_indent + INDENT_SIZE,
                    )
                else:
                    for question in questions:
                        add_custom_paragraph(
                            doc,
                            question,
                            style="Normal",
                            indent=parent_indent + INDENT_SIZE,
                        )

                add_to_doc(
                    section[0],
                    level + 1,
                    numbering_prefix=f"{number}.",
                    is_first_h1=is_first_h1,
                )

        add_to_doc(root_id, 1)

        file_path = asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Documents", "*.docx")],
            title="Save Document As",
        )
        if not file_path:
            return

        doc.save(file_path)
        messagebox.showinfo(
            "Exported", f"Document exported successfully to {file_path}."
        )

    except Exception as e:
        messagebox.showerror("Export Failed", f"An error occurred during export:\n{e}")

