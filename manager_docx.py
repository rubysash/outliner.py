from docx import Document
from docx.shared import Pt, Inches, RGBColor
import json
from config import DOC_FONT, H1_SIZE, H2_SIZE, H3_SIZE, H4_SIZE, P_SIZE, INDENT_SIZE
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox

from database import DatabaseHandler
from manager_encryption import EncryptionManager

def export_to_docx(db_handler: DatabaseHandler):
    """Creates the docx file based on specs defined."""
    try:
        doc = Document()

        # Fetch and decrypt sections
        sections = db_handler.load_from_database()  

         # Add Table of Contents Placeholder
        toc_paragraph = doc.add_paragraph("Table of Contents", style="Heading 1")
        toc_paragraph.add_run("\n(TOC will need to be updated in Word)").italic = True
        doc.add_page_break()  # Add page break after TOC

        def add_custom_heading(doc, text, level):
            """Add a custom heading with specific formatting and indentation."""
            paragraph = doc.add_heading(level=level)
            if len(paragraph.runs) == 0:
                run = paragraph.add_run()
            else:
                run = paragraph.runs[0]
            run.text = text
            run.font.name = DOC_FONT
            run.bold = True

            # Apply colors and underline based on level
            if level == 1:
                run.font.size = Pt(H1_SIZE)
                run.font.color.rgb = RGBColor(178, 34, 34)  # Brick red
            elif level == 2:
                run.font.size = Pt(H2_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 128)  # Navy blue
            elif level == 3:
                run.font.size = Pt(H3_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 0)  # Black
            elif level == 4:
                run.font.size = Pt(H4_SIZE)
                run.font.color.rgb = RGBColor(0, 0, 0)  # Black underline
                run.underline = True

            # Adjust paragraph indentation
            paragraph.paragraph_format.left_indent = Inches(INDENT_SIZE * (level - 1))
            return paragraph.paragraph_format.left_indent.inches

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
                # Generate numbering dynamically
                number = f"{numbering_prefix}{idx}"
                title_with_number = f"{number}. {section[1]}"

                # Add page break before H1 (except the first one)
                if level == 1 and not is_first_h1:
                    doc.add_page_break()
                if level == 1:
                    is_first_h1 = False  # Update the flag after processing the first H1

                # Add heading with numbering
                parent_indent = add_custom_heading(doc, title_with_number, level)

                # Validate and load questions
                try:
                    questions = json.loads(section[4]) if section[4] else []
                except json.JSONDecodeError:
                    questions = []

                # Add content: bullet points for H3/H4, plain paragraphs otherwise
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

                # Recurse for children
                add_to_doc(
                    section[0],
                    level + 1,
                    numbering_prefix=f"{number}.",
                    is_first_h1=is_first_h1,
                )

        # Start adding sections from the root
        add_to_doc(None, 1)

        # Ask the user for a save location
        file_path = asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Documents", "*.docx")],
            title="Save Document As",
        )
        if not file_path:
            return  # User cancelled the save dialog

        # Save the document
        doc.save(file_path)
        messagebox.showinfo(
            "Exported", f"Document exported successfully to {file_path}."
        )

    except Exception as e:
        messagebox.showerror("Export Failed", f"An error occurred during export:\n{e}")
