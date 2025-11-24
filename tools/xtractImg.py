# pip install pymupdf pillow numpy

import fitz
import os
from PIL import Image

#==========================CONFIG=============================================
INPUT_DIR = r"C:\Users\hdoghmen\Downloads\down01\CC"  # Directory containing PDF files
OUTPUT_BASE_DIR = r"C:\Users\hdoghmen\Downloads\down01\CC"
MIN_W = 300
MIN_H = 300
CROP_LEFT = 15   # percentage of the width to keep from the left
CROP_RIGHT = 45  # percentage of the width to keep from the right
#=======================================================================

# ---------------------------------------------------
# UTILS
# ---------------------------------------------------
def ensure_dirs(pdf_name):
    """Create output directories for a specific PDF file"""
    pdf_output_dir = os.path.join(OUTPUT_BASE_DIR, pdf_name)
    embed_dir = os.path.join(pdf_output_dir, "embedded")
    page_dir = os.path.join(pdf_output_dir, "pages")
    os.makedirs(embed_dir, exist_ok=True)
    os.makedirs(page_dir, exist_ok=True)
    return embed_dir, page_dir

def crop_edges(pil_img, keep_left_percent=CROP_LEFT, keep_right_percent=CROP_RIGHT):
    """
    Crop both left and right edges of the image by percentage.
    keep_left_percent=65 means keep 65% from the left, crop the rest on right.
    keep_right_percent=65 means keep 65% from the right, crop the rest on left.
    """
    w, h = pil_img.size
    
    # Calculate crop boundaries
    left_crop_boundary = int(w * keep_left_percent / 100)
    right_crop_boundary = w - int(w * keep_right_percent / 100)
    
    # Ensure we don't have invalid crop (right boundary should be > left boundary)
    if right_crop_boundary <= left_crop_boundary:
        # If crop areas overlap, keep the center portion
        center = w // 2
        keep_each_side = min(keep_left_percent, keep_right_percent) / 100 * w / 2
        left_crop_boundary = int(center - keep_each_side)
        right_crop_boundary = int(center + keep_each_side)
    
    return pil_img.crop((left_crop_boundary, 0, right_crop_boundary, h))

def page_is_blank_rule1(page):
    """Page is blank if no text and no embedded images."""
    if page.get_text().strip():
        return False
    if page.get_images(full=True):
        return False
    return True

# ---------------------------------------------------
# EXTRACT EMBEDDED IMAGES >= MIN_W x MIN_H
# ---------------------------------------------------
def extract_large_images(doc, embed_dir, pdf_name):
    index = 1
    first_image_skipped = False  # Flag to skip cropping for the first image

    for page_number, page in enumerate(doc, start=1):
        if page_is_blank_rule1(page):
            continue

        for img in page.get_images(full=True):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)

            if pix.width < MIN_W or pix.height < MIN_H:
                pix = None
                continue

            temp_file = f"temp_{pdf_name}.png"
            if pix.n < 5:
                pix.save(temp_file)
            else:
                rgb = fitz.Pixmap(fitz.csRGB, pix)
                rgb.save(temp_file)
                rgb = None

            pil_img = Image.open(temp_file)

            # Crop only if it's NOT the first image
            if first_image_skipped:
                pil_img = crop_edges(pil_img)
            else:
                first_image_skipped = True  # Skip cropping for the first image

            pil_img.save(os.path.join(embed_dir, f"page{page_number}_img{index}.png"))

            pix = None
            index += 1

    if os.path.exists(f"temp_{pdf_name}.png"):
        os.remove(f"temp_{pdf_name}.png")

# ---------------------------------------------------
# EXPORT ALL NON-BLANK PAGES AS IMAGES + EDGE CROP
# ---------------------------------------------------
def export_pages_as_images(doc, page_dir, pdf_name):
    for page_number, page in enumerate(doc, start=1):
        if page_is_blank_rule1(page):
            continue

        pix = page.get_pixmap(dpi=150)
        temp_file = f"temp_page_{pdf_name}.png"
        pix.save(temp_file)
        pix = None

        pil_img = Image.open(temp_file)
        pil_img = crop_edges(pil_img)
        pil_img.save(os.path.join(page_dir, f"page_{page_number}.png"))

    if os.path.exists(f"temp_page_{pdf_name}.png"):
        os.remove(f"temp_page_{pdf_name}.png")

# ---------------------------------------------------
# PROCESS SINGLE PDF
# ---------------------------------------------------
def process_pdf(pdf_path):
    """Process a single PDF file"""
    try:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        print(f"Processing: {pdf_name}")
        
        embed_dir, page_dir = ensure_dirs(pdf_name)
        doc = fitz.open(pdf_path)

        extract_large_images(doc, embed_dir, pdf_name)
        export_pages_as_images(doc, page_dir, pdf_name)

        doc.close()
        print(f"Completed: {pdf_name}")
        return True
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return False

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    # Create base output directory
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    # Get all PDF files in the input directory
    pdf_files = [f for f in os.listdir(INPUT_DIR) 
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(INPUT_DIR, f))]
    
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    successful = 0
    failed = 0
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        if process_pdf(pdf_path):
            successful += 1
        else:
            failed += 1
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {successful} files")
    print(f"Failed: {failed} files")

if __name__ == "__main__":
    main()