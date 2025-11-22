
import fitz  # PyMuPDF
import os
import glob
import sys
import shutil

#================= CONFIGURATION ===============
# 9_SAM_29_NOV_25
# 10__DIM_30_NOV_25

BASE_PATH = r"C:\Users\hdoghmen\OneDrive\VNTD_LBC_25\0.Warehouse\1.Route"
PDF_FOLDER = r"2025\NOV\8__DIM_23_NOV_25"


#BASE_PATH = r"C:\Users\hdoghmen\Downloads\down01"
#PDF_FOLDER = r"BB"

TARGET_FOLDER = os.path.join(BASE_PATH, PDF_FOLDER)
PREFIX = "VG__"
#------- Style Parameters -------------
FONT_NAME = "helv"
FONT_SIZE = 16
TEXT_COLOR_255 = (175, 10, 60)      # Deep Magenta/Red for Text
BOX_FILL_COLOR_255 = (255, 255, 0)  # Pure Yellow
LINE_COLOR_255 = (255, 0, 0)        # Pure Red
LINE_WIDTH = 2
#================================================

def supports_ansi() -> bool:
    """Return True if the terminal likely supports ANSI colors."""
    if os.name == "nt":
        term = os.environ.get("TERM", "")
        if "xterm" in term.lower() or "ansi" in term.lower():
            return True
        # PowerShell and old cmd generally do NOT support ANSI by default
        return False
    return sys.stdout.isatty()

USE_COLOR = supports_ansi()
RED = "\033[91m" if USE_COLOR else ""
GREEN = "\033[92m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""

def print_success(msg):
    print(f"{GREEN}{msg}{RESET}")

def print_error(msg):
    print(f"{RED}{msg}{RESET}")

# ---------- Utility Functions ----------
def convert_rgb_255_to_1(rgb_255_tuple):    
    return tuple(c / 255.0 for c in rgb_255_tuple)

def is_page_blank(page: fitz.Page) -> bool:
    if page.get_text().strip():
        return False
    if page.get_images(full=False):
        return False
    if page.get_drawings():
        return False
    if page.get_contents():
        return len(page.get_contents()) < 5
    return True

def add_styled_text_with_box(page, text):
    text_color = convert_rgb_255_to_1(TEXT_COLOR_255)
    fill_color = convert_rgb_255_to_1(BOX_FILL_COLOR_255)
    font = fitz.Font(FONT_NAME)

    PADDING = 15
    START_X = PADDING
    START_Y = PADDING + FONT_SIZE
    text_width = font.text_length(text, FONT_SIZE)

    rect = fitz.Rect(
        START_X - PADDING,
        START_Y - FONT_SIZE - PADDING,
        START_X + text_width + PADDING,
        START_Y + PADDING
    )

    page.draw_rect(rect, color=(0, 0, 0), fill=fill_color, width=1.5)
    page.insert_text((START_X, START_Y), text, fontsize=FONT_SIZE, color=text_color, fontname=FONT_NAME)


def add_bottom_line(doc):
    if doc.page_count == 0:
        return

    line_color = convert_rgb_255_to_1(LINE_COLOR_255)
    page = doc[-1]
    rect = page.rect

    BOTTOM_MARGIN = 20
    SIDE_PADDING = 50
    y_pos = rect.height - BOTTOM_MARGIN

    p1 = fitz.Point(rect.x0 + SIDE_PADDING, y_pos)
    p2 = fitz.Point(rect.x1 - SIDE_PADDING, y_pos)
    page.draw_line(p1, p2, color=line_color, width=LINE_WIDTH)


#---------- Main Processing Function ----------
def process_and_merge_pdfs(input_path: str):
    if not os.path.isdir(input_path):
        print_error(f"Error: Input directory not found: {input_path}")
        return

    pdf_files = sorted(glob.glob(os.path.join(input_path, "*.pdf")))
    if not pdf_files:
        print_error(f"No PDF files found in {input_path}. Aborting.")
        return

    folder_name = os.path.basename(os.path.normpath(input_path))
    output_path = os.path.join(input_path, f"{PREFIX}{folder_name}.pdf")

    print(f"[{len(pdf_files)}] - PDFs found. Output: {output_path}")
    print("_" * 60)

    final_doc = fitz.open()
    total_pages_removed = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        filename_no_ext = os.path.splitext(filename)[0]
        print(f"[{i}/{len(pdf_files)}] Processing {filename}...")

        try:
            src = fitz.open(pdf_path)
            temp = fitz.open()
            temp.insert_pdf(src)
            src.close()

            # Remove blank pages
            pages_to_delete = [p for p in range(len(temp)) if is_page_blank(temp[p])]
            for p in reversed(pages_to_delete):
                temp.delete_page(p)
            pages_removed = len(pages_to_delete)
            total_pages_removed += pages_removed

            if len(temp) == 0:
                print("All pages blank. Skipped.")
                temp.close()
                continue

            # Add filename text + red bottom line
            add_styled_text_with_box(temp[0], filename_no_ext)
            add_bottom_line(temp)

            # Merge into final PDF
            final_doc.insert_pdf(temp, links=False)
            temp.close()

            print_success(f"Processed successfully | Removed {pages_removed} blank page(s)")

        except Exception as e:
            print_error(f"Error processing {filename}: {e}")
            continue

    # Save final PDF
    if len(final_doc) > 0:
        print("-" * 60)
        print_success(f"Total blank pages removed: {total_pages_removed}")
        print_success(f"Total pages in merged PDF: {len(final_doc)}")
        try:
            final_doc.save(output_path, garbage=3, deflate=True)
            print_success(f"Final merged PDF saved to: {output_path}")
        except Exception as e:
            print_error(f"Error saving final PDF: {e}")
    else:
        print_error("No valid pages found. Nothing saved.")

    final_doc.close()


#=====================================================
#   RUN
#=====================================================
if __name__ == "__main__":
    process_and_merge_pdfs(TARGET_FOLDER)    