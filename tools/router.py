#!/usr/bin/env python3
# pip install pymupdf pillow numpy

import fitz
import os
from PIL import Image
import base64
from datetime import datetime
import webbrowser
import json
import glob

#==========================CONFIG=============================================
INPUT_DIR = r"C:\Users\hdoghmen\Downloads\down01\CC"  # Directory containing PDF files
OUTPUT_BASE_DIR = r"C:\Users\hdoghmen\Downloads\down01\CC"
MIN_W = 300
MIN_H = 300
CROP_LEFT = 15   # percentage of the width to keep from the left
CROP_RIGHT = 45  # percentage of the width to keep from the right
IMG_TO_DISK = "off"  # "on" to write images to disk, "off" to use base64 in HTML
OUTPUT_HTML = "route_plan.html"  # Output HTML file name
#=======================================================================

# Color codes for console output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_color(text, color):
    """Print colored text to console"""
    print(f"{color}{text}{Colors.END}")

# ---------------------------------------------------
# UTILS
# ---------------------------------------------------
def ensure_dirs(pdf_name):
    """Create output directories for a specific PDF file"""
    pdf_output_dir = os.path.join(OUTPUT_BASE_DIR, pdf_name)
    embed_dir = os.path.join(pdf_output_dir, "embedded")
    page_dir = os.path.join(pdf_output_dir, "pages")
    if IMG_TO_DISK.lower() == "on":
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

def image_to_base64(pil_img, format='PNG'):
    """Convert PIL image to base64 string"""
    from io import BytesIO
    buffer = BytesIO()
    pil_img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# ---------------------------------------------------
# EXTRACT EMBEDDED IMAGES >= MIN_W x MIN_H
# ---------------------------------------------------
def extract_large_images(doc, embed_dir, pdf_name, all_images_data):
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

            if IMG_TO_DISK.lower() == "on":
                pil_img.save(os.path.join(embed_dir, f"page{page_number}_img{index}.png"))
                print_color(f"  ✓ Saved embedded image: page{page_number}_img{index}.png", Colors.GREEN)
            else:
                # Store in memory for HTML
                base64_data = image_to_base64(pil_img)
                all_images_data.append({
                    'folder': pdf_name,
                    'name': f"page{page_number}_img{index}.png",
                    'base64': f"data:image/png;base64,{base64_data}"
                })
                print_color(f"  ✓ Processed embedded image: page{page_number}_img{index}.png", Colors.CYAN)

            pix = None
            index += 1

    if os.path.exists(f"temp_{pdf_name}.png"):
        os.remove(f"temp_{pdf_name}.png")

# ---------------------------------------------------
# EXPORT ALL NON-BLANK PAGES AS IMAGES + EDGE CROP
# ---------------------------------------------------
def export_pages_as_images(doc, page_dir, pdf_name, all_images_data):
    for page_number, page in enumerate(doc, start=1):
        if page_is_blank_rule1(page):
            continue

        pix = page.get_pixmap(dpi=150)
        temp_file = f"temp_page_{pdf_name}.png"
        pix.save(temp_file)
        pix = None

        pil_img = Image.open(temp_file)
        pil_img = crop_edges(pil_img)

        if IMG_TO_DISK.lower() == "on":
            pil_img.save(os.path.join(page_dir, f"page_{page_number}.png"))
            print_color(f"  ✓ Saved page image: page_{page_number}.png", Colors.GREEN)
        else:
            # Store in memory for HTML
            base64_data = image_to_base64(pil_img)
            all_images_data.append({
                'folder': pdf_name,
                'name': f"page_{page_number}.png",
                'base64': f"data:image/png;base64,{base64_data}"
            })
            print_color(f"  ✓ Processed page image: page_{page_number}.png", Colors.CYAN)

    if os.path.exists(f"temp_page_{pdf_name}.png"):
        os.remove(f"temp_page_{pdf_name}.png")

# ---------------------------------------------------
# PROCESS SINGLE PDF
# ---------------------------------------------------
def process_pdf(pdf_path, all_images_data):
    """Process a single PDF file"""
    try:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        print_color(f"📄 Processing: {pdf_name}", Colors.BLUE + Colors.BOLD)
        
        embed_dir, page_dir = ensure_dirs(pdf_name)
        doc = fitz.open(pdf_path)

        extract_large_images(doc, embed_dir, pdf_name, all_images_data)
        export_pages_as_images(doc, page_dir, pdf_name, all_images_data)

        doc.close()
        print_color(f"✅ Completed: {pdf_name}", Colors.GREEN + Colors.BOLD)
        return True
    except Exception as e:
        print_color(f"❌ Error processing {pdf_path}: {str(e)}", Colors.RED)
        return False

# ---------------------------------------------------
# HTML GALLERY CREATION
# ---------------------------------------------------
def create_html_gallery(all_images_data, output_file):
    """Create HTML gallery from processed images"""
    print_color(f"\n🎨 Creating HTML gallery...", Colors.MAGENTA + Colors.BOLD)
    
    # Group images by folder
    folders_data = []
    folders_dict = {}
    
    for img_data in all_images_data:
        folder_name = img_data['folder']
        if folder_name not in folders_dict:
            folders_dict[folder_name] = []
        folders_dict[folder_name].append({
            'name': img_data['name'],
            'base64': img_data['base64']
        })
    
    for folder_name, images in folders_dict.items():
        folders_data.append({
            'name': folder_name,
            'images': images
        })
    
    print_color(f"📁 Found {len(folders_data)} folders with {len(all_images_data)} total images", Colors.YELLOW)
    
    if not folders_data:
        print_color("❌ No images found to create gallery", Colors.RED)
        return None
    
    # Create HTML content
    html_content = create_html_content(folders_data, INPUT_DIR)
    
    # Save HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print_color(f"✅ Gallery created successfully: {output_file}", Colors.GREEN + Colors.BOLD)
    
    # Open in web browser
    try:
        webbrowser.open(f'file://{os.path.abspath(output_file)}')
        print_color("🌐 Opening gallery in web browser...", Colors.CYAN)
    except:
        print_color(f"📋 Manual: Open {output_file} in your web browser", Colors.YELLOW)
    
    return output_file

def create_html_content(folders_data, master_dir):
    """Create the HTML content for the gallery"""
    folders_json = json.dumps(folders_data)
    
    # Dhuhr prayer times data
    dhuhr_times_json = '''
    {
        "location": "Association FAIF, Paris (CET)",
        "annee": "2025-2026",
        "unite_temps": "HH:MM",
        "horaires_dhuhr": [
            {
                "mois_num": 11,
                "mois_nom": "Novembre 2025",
                "jours": {
                    "1": "12:35",
                    "2": "12:35",
                    "8": "12:35",
                    "9": "12:36",
                    "15": "12:36",
                    "16": "12:37",
                    "22": "12:38",
                    "23": "12:38",
                    "29": "12:39",
                    "30": "12:39"
                }
            },
            {
                "mois_num": 12,
                "mois_nom": "Décembre 2025",
                "jours": {
                    "6": "12:42",
                    "7": "12:42",
                    "13": "12:45",
                    "14": "12:45",
                    "20": "12:48",
                    "21": "12:49",
                    "27": "12:52",
                    "28": "12:52"
                }
            },
            {
                "mois_num": 1,
                "mois_nom": "Janvier 2026",
                "jours": {
                    "3": "12:55",
                    "4": "12:56",
                    "10": "12:58",
                    "11": "12:59",
                    "17": "13:01",
                    "18": "13:01",
                    "24": "13:01",
                    "25": "13:01",
                    "31": "13:01"
                }
            }
        ]
    }
    '''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Images Gallery</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f7;
            color: #333;
            line-height: 1.6;
            padding: 10px;
        }}
        
        .container {{
            max-width: 100%;
            margin: 0 auto;
        }}
        
        /* Horizontal Menu */
        .top-menu {{
            background: white;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            border: 1px solid #e1e1e1;
        }}
        
        .menu-title {{
            font-size: 20px;
            font-weight: 600;
            color: #1d1d1f;
        }}
        
        .time-display {{
            display: flex;
            align-items: center;
            gap: 20px;
            font-family: 'Courier New', monospace;
        }}
        
        .dhuhr-countdown {{
            font-size: 16px;
            font-weight: 600;
            color: #ff3b30;
            background: #fff0f0;
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid #ffd1d1;
            box-shadow: 0 2px 8px rgba(255, 59, 48, 0.2);
        }}
        
        .real-time-clock {{
            font-size: 16px;
            font-weight: 500;
            color: #007aff;
        }}
        
        .folder-accordion {{
            margin-bottom: 20px;
        }}
        
        .folder-section {{
            position: relative;
            margin-bottom: 15px;
        }}
        
        .folder-section::after {{
            content: '';
            position: absolute;
            bottom: -8px;
            left: 0;
            right: 0;
            height: 2px;
            background: #ff3b30;
            display: none;
        }}
        
        .folder-section.at-bottom::after {{
            display: block;
        }}
        
        .folder-header {{
            background: #fff9c4;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border: 1px solid #e6e6e6;
            transition: all 0.3s ease;
        }}
        
        .folder-header:nth-child(even) {{
            background: #fffde7;
        }}
        
        .folder-header:hover {{
            background: #fff59d;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            transform: translateY(-1px);
        }}
        
        .folder-title {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .folder-name {{
            font-size: 18px;
            font-weight: 600;
            color: #1d1d1f;
        }}
        
        .copy-icon {{
            background: none;
            border: none;
            color: #007aff;
            cursor: pointer;
            padding: 6px;
            border-radius: 6px;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .copy-icon:hover {{
            background: rgba(0, 122, 255, 0.1);
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            transform: scale(1.1);
        }}
        
        .folder-count {{
            background: #007aff;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        
        .folder-content {{
            display: none;
            padding: 10px 0;
        }}
        
        .folder-content.active {{
            display: block;
        }}
        
        .image-stack {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }}
        
        .image-card {{
            background: white;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0,0,0,0.2);
            max-width: 100%;
            border: 2px solid #f0f0f0;
            transition: all 0.3s ease;
        }}
        
        .image-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 35px rgba(0,0,0,0.25);
            border-color: #e0e0e0;
        }}
        
        .image-container {{
            width: 100%;
            overflow: hidden;
        }}
        
        .image-container img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        footer {{
            text-align: center;
            padding: 20px 0;
            color: #86868b;
            font-size: 14px;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #86868b;
        }}
        
        .empty-state-icon {{
            font-size: 48px;
            margin-bottom: 15px;
            opacity: 0.7;
        }}
        
        /* Floating Home Button */
        .floating-home {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #007aff;
            color: white;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(0, 122, 255, 0.4);
            border: none;
            transition: all 0.3s ease;
            z-index: 1000;
        }}
        
        .floating-home:hover {{
            background: #0056cc;
            transform: scale(1.1);
            box-shadow: 0 8px 25px rgba(0, 122, 255, 0.6);
        }}
        
        .home-icon {{
            width: 24px;
            height: 24px;
        }}
        
        .toast {{
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        
        .toast.show {{
            opacity: 1;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Horizontal Menu -->
        <div class="top-menu">
            <div class="menu-title">PDF Images Gallery</div>
            <div class="time-display">
                <div class="dhuhr-countdown" id="dhuhrCountdown"></div>
                <div class="real-time-clock" id="realTimeClock"></div>
            </div>
        </div>
        
        <main>
            <div class="folder-accordion" id="folderAccordion">
                <!-- Folders will be inserted here by JavaScript -->
            </div>
        </main>
        
        <footer>
            <p>{len(folders_data)} folders • {sum(len(folder['images']) for folder in folders_data)} images</p>
        </footer>
    </div>

    <!-- Floating Home Button -->
    <button class="floating-home" onclick="goToHome()" title="Collapse all and go to top">
        <svg class="home-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
            <polyline points="9 22 9 12 15 12 15 22"></polyline>
        </svg>
    </button>

    <!-- Toast notification -->
    <div class="toast" id="toast"></div>

    <script>
        // Folder data injected by Python script
        const folders = {folders_json};
        const masterDir = "{master_dir}";
        
        // Dhuhr prayer times data
        const dhuhrTimes = {dhuhr_times_json};
        
        // Real-time clock function
        function updateClock() {{
            const now = new Date();
            const options = {{ 
                day: '2-digit', 
                month: 'short', 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit',
                hour12: false 
            }};
            const dateStr = now.toLocaleDateString('en-US', {{ day: '2-digit', month: 'short' }});
            const timeStr = now.toLocaleTimeString('en-US', {{ hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }});
            document.getElementById('realTimeClock').textContent = `${{dateStr}} ${{timeStr}}`;
            
            // Update Dhuhr countdown
            updateDhuhrCountdown(now);
        }}
        
        // Get nearest Dhuhr time (ignoring exact day matching)
        function getNearestDhuhrTime(now) {{
            const currentMonth = now.getMonth() + 1; // JavaScript months are 0-indexed
            
            // Find current month in dhuhrTimes
            const currentMonthData = dhuhrTimes.horaires_dhuhr.find(month => month.mois_num === currentMonth);
            
            if (currentMonthData) {{
                // Get all Dhuhr times for this month and find the next one
                const dhuhrTimesList = Object.values(currentMonthData.jours);
                if (dhuhrTimesList.length > 0) {{
                    // Use the first available time for the month (simplified approach)
                    // In a real implementation, you might want more complex logic
                    return dhuhrTimesList[0];
                }}
            }}
            
            return null;
        }}
        
        // Calculate time remaining until Dhuhr
        function updateDhuhrCountdown(now) {{
            const dhuhrTimeStr = getNearestDhuhrTime(now);
            
            if (!dhuhrTimeStr) {{
                document.getElementById('dhuhrCountdown').textContent = 'No Dhuhr time';
                return;
            }}
            
            // Parse Dhuhr time
            const [dhuhrHours, dhuhrMinutes] = dhuhrTimeStr.split(':').map(Number);
            const dhuhrTime = new Date(now);
            dhuhrTime.setHours(dhuhrHours, dhuhrMinutes, 0, 0);
            
            // If Dhuhr time has passed today, set it for tomorrow
            if (dhuhrTime <= now) {{
                dhuhrTime.setDate(dhuhrTime.getDate() + 1);
            }}
            
            // Calculate difference
            const diffMs = dhuhrTime - now;
            
            // Convert to hours and minutes
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            
            // Format as HH:MM
            const formattedTime = `${{diffHours.toString().padStart(2, '0')}}:${{diffMinutes.toString().padStart(2, '0')}}`;
            document.getElementById('dhuhrCountdown').textContent = `${{formattedTime}} to Dhuhr`;
        }}
        
        // Show toast notification
        function showToast(message) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            
            setTimeout(() => {{
                toast.classList.remove('show');
            }}, 2000);
        }}
        
        // Copy folder name to clipboard
        function copyFolderName(folderName) {{
            navigator.clipboard.writeText(folderName).then(() => {{
                showToast('Folder name copied!');
            }}).catch(err => {{
                console.error('Failed to copy: ', err);
                showToast('Failed to copy folder name');
            }});
        }}
        
        // Go to home - collapse all and scroll to top
        function goToHome() {{
            // Close all folders
            document.querySelectorAll('.folder-content').forEach(content => {{
                content.classList.remove('active');
            }});
            
            // Scroll to top
            window.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
            
            showToast('All sections collapsed');
        }}
        
        // Check if element is at bottom of viewport
        function isAtBottom(element) {{
            const rect = element.getBoundingClientRect();
            return rect.bottom >= (window.innerHeight - 10);
        }}
        
        // Update red lines for bottom elements
        function updateRedLines() {{
            document.querySelectorAll('.folder-section').forEach(section => {{
                if (isAtBottom(section)) {{
                    section.classList.add('at-bottom');
                }} else {{
                    section.classList.remove('at-bottom');
                }}
            }});
        }}
        
        // Function to render folders and images
        function renderFolders() {{
            const accordion = document.getElementById('folderAccordion');
            
            if (folders.length === 0) {{
                accordion.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📷</div>
                        <h2>No images found</h2>
                        <p>No images were found in the scanned folders.</p>
                    </div>
                `;
                return;
            }}
            
            let accordionHTML = '';
            folders.forEach((folder, index) => {{
                let imagesHTML = '';
                folder.images.forEach(image => {{
                    imagesHTML += `
                        <div class="image-card">
                            <div class="image-container">
                                <img src="${{image.base64}}" alt="${{image.name}}">
                            </div>
                        </div>
                    `;
                }});
                
                accordionHTML += `
                    <div class="folder-section" id="section-${{index}}">
                        <div class="folder-header" onclick="toggleFolder(${{index}})">
                            <div class="folder-title">
                                <div class="folder-name">${{folder.name}}</div>
                                <button class="copy-icon" onclick="event.stopPropagation(); copyFolderName('${{folder.name}}')" title="Copy folder name">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                    </svg>
                                </button>
                            </div>
                            <div class="folder-count">${{folder.images.length}}</div>
                        </div>
                        <div class="folder-content" id="folder-${{index}}">
                            <div class="image-stack">
                                ${{imagesHTML}}
                            </div>
                        </div>
                    </div>
                `;
            }});
            
            accordion.innerHTML = accordionHTML;
            
            // Update red lines after rendering
            setTimeout(updateRedLines, 100);
        }}
        
        // Toggle folder accordion - closes all others when opening one
        function toggleFolder(index) {{
            const folderContent = document.getElementById(`folder-${{index}}`);
            const isActive = folderContent.classList.contains('active');
            
            // Close all folders first
            document.querySelectorAll('.folder-content').forEach(content => {{
                content.classList.remove('active');
            }});
            
            // Open clicked folder only if it wasn't active
            if (!isActive) {{
                folderContent.classList.add('active');
            }}
            
            // Update red lines after toggle
            setTimeout(updateRedLines, 100);
        }}
        
        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            // Start real-time clock
            updateClock();
            setInterval(updateClock, 1000);
            
            // Render folders
            renderFolders();
            
            // Update red lines on scroll and resize
            window.addEventListener('scroll', updateRedLines);
            window.addEventListener('resize', updateRedLines);
        }});
    </script>
</body>
</html>'''

# ---------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------
def main():
    print_color("🚀 Starting PDF to HTML Gallery Converter", Colors.MAGENTA + Colors.BOLD)
    print_color(f"📁 Input directory: {INPUT_DIR}", Colors.BLUE)
    print_color(f"💾 Image to disk: {IMG_TO_DISK}", Colors.BLUE)
    print_color(f"📊 Output HTML: {OUTPUT_HTML}", Colors.BLUE)
    print_color("-" * 60, Colors.WHITE)
    
    # Create base output directory if needed
    if IMG_TO_DISK.lower() == "on":
        os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    # Get all PDF files in the input directory
    pdf_files = [f for f in os.listdir(INPUT_DIR) 
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(INPUT_DIR, f))]
    
    if not pdf_files:
        print_color(f"❌ No PDF files found in {INPUT_DIR}", Colors.RED)
        return
    
    print_color(f"📚 Found {len(pdf_files)} PDF files to process", Colors.YELLOW)
    
    # Store all images data for HTML generation
    all_images_data = []
    
    successful = 0
    failed = 0
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        if process_pdf(pdf_path, all_images_data):
            successful += 1
        else:
            failed += 1
    
    print_color("-" * 60, Colors.WHITE)
    print_color(f"📊 Processing complete!", Colors.MAGENTA + Colors.BOLD)
    print_color(f"✅ Successfully processed: {successful} files", Colors.GREEN)
    print_color(f"❌ Failed: {failed} files", Colors.RED if failed > 0 else Colors.GREEN)
    
    # Create HTML gallery
    if all_images_data:
        output_path = os.path.join(OUTPUT_BASE_DIR, OUTPUT_HTML)
        create_html_gallery(all_images_data, output_path)
    else:
        print_color("❌ No images were processed, cannot create HTML gallery", Colors.RED)

if __name__ == "__main__":
    main()