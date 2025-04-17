import os
import sys
import subprocess
import tempfile
import shutil
import traceback
import time
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor, as_completed

# Dynamic path resolution
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Config
SCRIPT_DIR = os.path.dirname(sys.argv[0] if len(sys.argv) > 0 else "")
TEMP_DIR = tempfile.mkdtemp()
FFMPEG_PATH = os.path.join(TEMP_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(TEMP_DIR, "ffprobe.exe")
FONT_PATH = os.path.join(TEMP_DIR, "arial.ttf")

# Sheet configuration
SHEET_WIDTH = 1920
GRID_COLUMNS = 5
GRID_ROWS = 5
MARGIN = 5
JPEG_QUALITY = 90
BG_COLOR = (0, 0, 0)
FONT_SIZE = 22
TIME_FONT_SIZE = 18

# Video extensions to process
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp']

# Maximum parallel processing
MAX_WORKERS = 4

def extract_embedded_files():
    """Extract embedded binaries to the temporary directory"""
    try:
        # Copy files from the PyInstaller temp directory to our temp directory
        shutil.copy(resource_path("ffmpeg.exe"), FFMPEG_PATH)
        shutil.copy(resource_path("ffprobe.exe"), FFPROBE_PATH)
        shutil.copy(resource_path("arial.ttf"), FONT_PATH)
        
        # Make sure ffmpeg and ffprobe are executable
        os.chmod(FFMPEG_PATH, 0o755)
        os.chmod(FFPROBE_PATH, 0o755)
    except Exception as e:
        print(f"Error extracting embedded files: {e}")
        sys.exit(1)

def cleanup():
    """Clean up temporary files"""
    try:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Could not clean up temporary files: {e}")

def get_video_info(video_path):
    """Get video metadata using ffprobe more robustly"""
    try:
        # Get duration
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
        
        # Get width
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        width = result.stdout.strip()
        
        # Get height
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=height',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        height = result.stdout.strip()
        
        # Get codec
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        codec = result.stdout.strip()
        
        resolution = f"{width}x{height}" if width and height else "Unknown"
        
        # Calculate file size
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        
        return {
            'duration': duration,
            'resolution': resolution,
            'size': f"{size_mb:.2f} MB",
            'codec': codec if codec else "Unknown"
        }
    except subprocess.CalledProcessError as e:
        print(f"Error analyzing video: {e}")
        print(f"FFPROBE stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"Error getting video info: {e}")
        traceback.print_exc()  # Print the full traceback for debugging
        return None

def generate_timestamps(duration, total=25):
    """Create evenly distributed timestamps throughout the video"""
    if duration <= 0:
        return [0] * total
    
    # Add padding at the start and end
    gap = duration / (total + 2)
    return [gap * (i + 1) for i in range(total)]

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def extract_thumbnails(video_path, timestamps, temp_dir):
    """Extract frame thumbnails at specified timestamps"""
    images = []
    total = len(timestamps)
    
    for i, sec in enumerate(timestamps):
        output_path = os.path.join(temp_dir, f"thumb_{i:02d}.jpg")
        try:
            subprocess.run([
                FFMPEG_PATH, '-ss', str(sec), '-i', video_path,
                '-frames:v', '1', '-q:v', '2', output_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            images.append((output_path, sec))
        except subprocess.CalledProcessError:
            pass  # Silently skip failed thumbnails when in batch mode
    
    return images

def build_sheet(video_path, thumbnails, video_info):
    """Create the thumbnail sheet with video information"""
    if not thumbnails:
        print(f"Error: No thumbnails were extracted for {os.path.basename(video_path)}")
        return None
    
    # Get dimensions from first thumbnail
    try:
        sample_img = Image.open(thumbnails[0][0])
        thumb_width = (SHEET_WIDTH - (GRID_COLUMNS + 1) * MARGIN) // GRID_COLUMNS
        ratio = sample_img.height / sample_img.width
        thumb_height = int(thumb_width * ratio)
        
        # Calculate sheet height with space for info header
        info_header_height = (FONT_SIZE * 5) + 20
        sheet_height = (GRID_ROWS * (thumb_height + MARGIN)) + MARGIN + info_header_height
        
        # Create sheet image
        sheet = Image.new("RGB", (SHEET_WIDTH, sheet_height), BG_COLOR)
        draw = ImageDraw.Draw(sheet)
        
        # Try to load font, fall back to default if necessary
        try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
            time_font = ImageFont.truetype(FONT_PATH, TIME_FONT_SIZE)
        except Exception as e:
            font = ImageFont.load_default()
            time_font = ImageFont.load_default()
        
        # Add file info at the top
        base_name = os.path.basename(video_path)
        lines = [
            f"Filename: {base_name}",
            f"Size: {video_info['size']}",
            f"Resolution: {video_info['resolution']}",
            f"Video Codec: {video_info['codec']}",
            f"Duration: {format_timestamp(video_info['duration'])}"
        ]
        
        y_offset = MARGIN
        for line in lines:
            # Check if we're using Pillow < 9.2.0 (getsize) or >= 9.2.0 (textbbox)
            if hasattr(font, 'getsize'):
                draw.text((MARGIN, y_offset), line, fill=(255, 255, 255), font=font)
            else:
                draw.text((MARGIN, y_offset), line, fill=(255, 255, 255), font=font)
            
            y_offset += FONT_SIZE + 2
        
        y_offset += 8  # Extra spacing after info
        
        # Place thumbnails in grid
        for idx, (thumb_path, ts) in enumerate(thumbnails):
            row = idx // GRID_COLUMNS
            col = idx % GRID_COLUMNS
            
            x = MARGIN + col * (thumb_width + MARGIN)
            y = y_offset + row * (thumb_height + MARGIN)
            
            try:
                img = Image.open(thumb_path).resize((thumb_width, thumb_height))
                sheet.paste(img, (x, y))
                
                # Add timestamp overlay
                timestamp = format_timestamp(ts)
                
                # Add semi-transparent background for timestamp
                # Handle different Pillow versions for text size calculation
                if hasattr(time_font, 'getsize'):
                    text_width, text_height = time_font.getsize(timestamp)
                else:
                    bbox = draw.textbbox((0, 0), timestamp, font=time_font)
                    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                
                # Create timestamp background
                timestamp_bg = Image.new('RGBA', (text_width + 6, text_height + 2), (0, 0, 0, 128))
                sheet.paste(timestamp_bg, (x + 5, y + 5), timestamp_bg)
                
                # Draw timestamp
                draw.text((x + 8, y + 5), timestamp, fill=(255, 255, 255), font=time_font)
            except Exception:
                pass  # Skip problematic thumbnails in batch mode
        
        return sheet
    except Exception as e:
        print(f"Error building sheet for {os.path.basename(video_path)}: {e}")
        return None

def process_video(video_path, total_videos=1, current_index=1):
    """Process a single video and create its thumbnail sheet"""
    try:
        base_name = os.path.basename(video_path)
        output_path = os.path.splitext(video_path)[0] + "_sheet.jpg"
        
        # Skip if sheet already exists
        if os.path.exists(output_path):
            print(f"[{current_index}/{total_videos}] Sheet already exists for {base_name}, skipping...")
            return True
            
        print(f"[{current_index}/{total_videos}] Processing: {base_name}")
        
        # Get video metadata
        video_info = get_video_info(video_path)
        if not video_info:
            print(f"[{current_index}/{total_videos}] Failed to analyze {base_name}")
            return False
        
        # Generate timestamps and extract thumbnails
        timestamps = generate_timestamps(video_info['duration'], GRID_COLUMNS * GRID_ROWS)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            thumbs = extract_thumbnails(video_path, timestamps, tmpdir)
            
            if not thumbs:
                print(f"[{current_index}/{total_videos}] Failed to extract thumbnails for {base_name}")
                return False
                
            sheet = build_sheet(video_path, thumbs, video_info)
            
            if sheet:
                # Save the sheet in the same directory as the video
                sheet.save(output_path, "JPEG", quality=JPEG_QUALITY)
                print(f"[{current_index}/{total_videos}] Saved sheet for {base_name}")
                return True
            else:
                print(f"[{current_index}/{total_videos}] Failed to build sheet for {base_name}")
                return False
        
    except Exception as e:
        print(f"[{current_index}/{total_videos}] Error processing {os.path.basename(video_path)}: {e}")
        return False

def find_video_files(folder_path):
    """Find all video files in a folder (non-recursive)"""
    video_files = []
    
    try:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                ext = os.path.splitext(file)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    video_files.append(file_path)
    except Exception as e:
        print(f"Error scanning folder {folder_path}: {e}")
    
    return video_files

def process_folder(folder_path):
    """Process all video files in a folder"""
    print(f"Scanning folder: {folder_path}")
    video_files = find_video_files(folder_path)
    
    if not video_files:
        print(f"No video files found in {folder_path}")
        return
    
    print(f"Found {len(video_files)} video files")
    
    # Process videos in parallel
    successful = 0
    failed = 0
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_video = {
            executor.submit(process_video, video_path, len(video_files), i+1): video_path 
            for i, video_path in enumerate(video_files)
        }
        
        # Process results as they complete
        for future in as_completed(future_to_video):
            video_path = future_to_video[future]
            try:
                result = future.result()
                if result:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Exception processing {os.path.basename(video_path)}: {e}")
                failed += 1
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\nFolder processing complete!")
    print(f"Total videos: {len(video_files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Time taken: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

def main():
    """Main function to start processing"""
    try:
        # Extract embedded binaries
        extract_embedded_files()
        
        if len(sys.argv) < 2:
            print("Error: No path specified.")
            print("Usage: video_sheet_generator.exe <video_file_or_folder_path>")
            print("   or: Drag and drop a video file or folder onto the .exe")
            return 1
        
        path = sys.argv[1]
        
        if not os.path.exists(path):
            print(f"Error: Path not found: {path}")
            return 1
            
        if os.path.isdir(path):
            # Process folder
            process_folder(path)
        else:
            # Process single file
            if os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS:
                if process_video(path):
                    print("Video processed successfully!")
                else:
                    print("Failed to process video.")
                    return 1
            else:
                print(f"Error: Not a supported video file: {path}")
                return 1
        
        # Clean up
        cleanup()
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        cleanup()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    
    # Keep console window open if there was an error
    if exit_code != 0:
        input("Press Enter to exit...")
    
    sys.exit(exit_code)