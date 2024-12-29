from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
import json
from config import DOC_FONT, H1_SIZE, H2_SIZE, H3_SIZE, H4_SIZE, P_SIZE, INDENT_SIZE
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox

def load_sections_for_export(db_handler, root_id=None):
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

def format_question_content(question, story, question_style, code_style):
    """
    Format question content with proper handling of code blocks and indentation.
    """
    lines = question.split('\n')
    in_code_block = False
    code_buffer = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for code block markers
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block - process the buffer
                if code_buffer:
                    # Preserve exact indentation by using a monospace font and spaces
                    formatted_code = []
                    for code_line in code_buffer:
                        # Replace spaces with non-breaking spaces to preserve indentation
                        space_prefix = len(code_line) - len(code_line.lstrip())
                        formatted_line = '&nbsp;' * space_prefix + code_line.lstrip()
                        formatted_code.append(formatted_line)
                    
                    # Join with line breaks and create a single paragraph
                    code_text = '<br/>'.join(formatted_code)
                    story.append(Paragraph(code_text, code_style))
                code_buffer = []
                in_code_block = False
            else:
                # Start new code block
                in_code_block = True
            i += 1
            continue
            
        if in_code_block:
            # Add line to code buffer without any processing
            code_buffer.append(line)
        else:
            # Regular text - preserve indentation but use question style
            if line.strip():  # Only process non-empty lines
                space_prefix = len(line) - len(line.lstrip())
                if space_prefix > 0:
                    # Indented regular text
                    formatted_line = '&nbsp;' * space_prefix + line.lstrip()
                    story.append(Paragraph(formatted_line, question_style))
                else:
                    # Non-indented regular text
                    story.append(Paragraph(line, question_style))
            else:
                # Empty line - add a small spacer
                story.append(Spacer(1, 3))
        i += 1
    
    # Handle any remaining code in buffer
    if code_buffer:
        formatted_code = []
        for code_line in code_buffer:
            space_prefix = len(code_line) - len(code_line.lstrip())
            formatted_line = '&nbsp;' * space_prefix + code_line.lstrip()
            formatted_code.append(formatted_line)
        code_text = '<br/>'.join(formatted_code)
        story.append(Paragraph(code_text, code_style))

def export_to_pdf(db_handler, root_id=None, file_path=None):
    """Creates the PDF file based on specs defined."""
    try:
        if root_id is None:
            confirm = messagebox.askyesno(
                "Full Export Warning",
                "No section selected. This will export the entire document which may take some time. Continue?",
                icon='warning'
            )
            if not confirm:
                return

        sections = load_sections_for_export(db_handler, root_id)
        
        if not file_path:
            file_path = asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF Documents", "*.pdf")],
                title="Save PDF As",
            )
            if not file_path:
                return

        # Create the PDF document
        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Define styles
        styles = getSampleStyleSheet()
        
        # Create custom styles for different heading levels
        h1_style = ParagraphStyle(
            'Heading1',
            parent=styles['Heading1'],
            fontName=DOC_FONT,
            fontSize=H1_SIZE,
            textColor=colors.maroon,
            leftIndent=0,
            spaceAfter=12
        )
        
        h2_style = ParagraphStyle(
            'Heading2',
            parent=styles['Heading2'],
            fontName=DOC_FONT,
            fontSize=H2_SIZE,
            textColor=colors.navy,
            leftIndent=INDENT_SIZE*inch,
            spaceAfter=12
        )
        
        h3_style = ParagraphStyle(
            'Heading3',
            parent=styles['Heading3'],
            fontName=DOC_FONT,
            fontSize=H3_SIZE,
            leftIndent=INDENT_SIZE*2*inch,
            spaceAfter=12
        )
        
        h4_style = ParagraphStyle(
            'Heading4',
            parent=styles['Heading4'],
            fontName=DOC_FONT,
            fontSize=H4_SIZE,
            leftIndent=INDENT_SIZE*3*inch,
            spaceAfter=12
        )
        
        # Style for regular text
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontName=DOC_FONT,
            fontSize=P_SIZE,
            leftIndent=INDENT_SIZE*4*inch,
            spaceAfter=6,
            spaceBefore=0
        )

        # Style specifically for code blocks
        code_style = ParagraphStyle(
            'Code',
            parent=styles['Code'],
            fontName='Courier',  # Monospace font for code
            fontSize=P_SIZE-1,  # Slightly smaller for code
            leftIndent=INDENT_SIZE*4*inch,
            spaceAfter=6,
            spaceBefore=6,
            wordWrap='LTR',
            fontColor=colors.darkblue # Different color for code
        )

        # Build the document content
        story = []
        
        # Add title page
        story.append(Paragraph("Table of Contents", h1_style))
        story.append(PageBreak())
        
        def get_style(section_type):
            if section_type == "header":
                return h1_style
            elif section_type == "category":
                return h2_style
            elif section_type == "subcategory":
                return h3_style
            else:  # subheader
                return h4_style

        def add_to_story(parent_id, numbering_prefix=""):
            children = [s for s in sections if s[3] == parent_id]
            
            for idx, section in enumerate(children, start=1):
                section_id, title, section_type, _, questions = section
                number = f"{numbering_prefix}{idx}"
                title_with_number = f"{number}. {title}"
                
                # Add section title
                style = get_style(section_type)
                story.append(Paragraph(title_with_number, style))
                
                # Add questions
                try:
                    questions_list = json.loads(questions) if questions else []
                except json.JSONDecodeError:
                    questions_list = []
                
                if not questions_list:
                    story.append(Paragraph("(No questions added yet)", question_style))
                else:
                    for question in questions_list:
                        format_question_content(question, story, question_style, code_style)
                
                # Add space after all questions
                story.append(Spacer(1, 12))
                
                # Process children
                add_to_story(section_id, f"{number}.")

        # If root_id is specified, first add the root node
        if root_id:
            root_section = [s for s in sections if s[0] == root_id][0]
            section_id, title, section_type, _, questions = root_section
            
            # Add root section
            style = get_style(section_type)
            story.append(Paragraph(f"1. {title}", style))
            
            try:
                questions_list = json.loads(questions) if questions else []
            except json.JSONDecodeError:
                questions_list = []
            
            if not questions_list:
                story.append(Paragraph("(No questions added yet)", question_style))
            else:
                for question in questions_list:
                    format_question_content(question, story, question_style, code_style)
            
            story.append(Spacer(1, 12))

        # Process all sections
        add_to_story(root_id)

        # Build the PDF
        doc.build(story)
        
        messagebox.showinfo(
            "Exported", 
            f"Document exported successfully to {file_path}."
        )
        
    except Exception as e:
        messagebox.showerror("Export Failed", f"An error occurred during export:\n{e}")