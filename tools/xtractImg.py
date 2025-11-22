# pip install pymupdf pillow numpy

import fitz
import os
from PIL import Image

# ---------------- CONFIG ----------------
PDF_PATH = r"C:\Users\hdoghmen\Downloads\down01\CC\input.pdf"          # Set your PDF path here
OUT_DIR = r"C:\Users\hdoghmen\Downloads\down01\CC\output"
EMBED_DIR = os.path.join(OUT_DIR, "embedded")
PAGE_DIR = os.path.join(OUT_DIR, "pages")

MIN_W = 300
MIN_H = 300
CROP_LEFT = 55   # percentage of the width to keep from the left
# ---------------------------------------

# ---------------------------------------------------
# UTILS
# ---------------------------------------------------
def ensure_dirs():
    os.makedirs(EMBED_DIR, exist_ok=True)
    os.makedirs(PAGE_DIR, exist_ok=True)

def crop_left(pil_img, keep_percent=CROP_LEFT):
    """
    Keep left portion of the image by percentage.
    keep_percent=70 means keep 70% from the left, crop the rest.
    """
    w, h = pil_img.size
    right = int(w * keep_percent / 100)
    return pil_img.crop((0, 0, right, h))

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
def extract_large_images(doc):
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

            temp_file = "temp.png"
            if pix.n < 5:
                pix.save(temp_file)
            else:
                rgb = fitz.Pixmap(fitz.csRGB, pix)
                rgb.save(temp_file)
                rgb = None

            pil_img = Image.open(temp_file)

            # Crop only if it's NOT the first image
            if first_image_skipped:
                pil_img = crop_left(pil_img)
            else:
                first_image_skipped = True  # Skip cropping for the first image

            pil_img.save(os.path.join(EMBED_DIR, f"page{page_number}_img{index}.png"))

            pix = None
            index += 1

    if os.path.exists("temp.png"):
        os.remove("temp.png")

# ---------------------------------------------------
# EXPORT ALL NON-BLANK PAGES AS IMAGES + LEFT CROP
# ---------------------------------------------------
def export_pages_as_images(doc):
    for page_number, page in enumerate(doc, start=1):
        if page_is_blank_rule1(page):
            continue

        pix = page.get_pixmap(dpi=150)
        temp_file = "temp_page.png"
        pix.save(temp_file)
        pix = None

        pil_img = Image.open(temp_file)
        pil_img = crop_left(pil_img)
        pil_img.save(os.path.join(PAGE_DIR, f"page_{page_number}.png"))

    if os.path.exists("temp_page.png"):
        os.remove("temp_page.png")

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    ensure_dirs()
    doc = fitz.open(PDF_PATH)

    extract_large_images(doc)
    export_pages_as_images(doc)

    doc.close()
    print("Done.")

if __name__ == "__main__":
    main()
