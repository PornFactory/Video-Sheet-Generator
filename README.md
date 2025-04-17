# Video Thumbnail Sheet Generator

A powerful utility for automatically generating visual thumbnail sheets from video files. This tool captures frames from throughout the video and arranges them in a clean grid layout with timestamp references, creating a visual index for video content.
## Example
![https://github.com/PornFactory/video_sheet_generator/blob/main/SampleVideo_sheet.jpg?raw=true](https://github.com/PornFactory/video_sheet_generator/blob/main/SampleVideo_sheet.jpg?raw=true)
## Features

- **Batch Processing**: Process an entire folder of videos with multi-threaded performance
- **Detailed Metadata**: Displays video information including resolution, codec, size, and duration
- **Grid Layout**: Organizes thumbnails in a 5x5 grid with timestamps
- **Smart Timestamp Distribution**: Evenly spaces thumbnails across the video duration
- **High-Quality Output**: Generate clean, high-resolution JPEG sheets

## Usage

### Simple Usage

1. **Drag and Drop**: Simply drag a video file or folder onto the executable
2. **Command Line**: Run `video_sheet_generator.exe <path_to_video_or_folder>`

The program will generate a thumbnail sheet with the same name as the video file but with "_sheet.jpg" appended.

### Output Example

The generated sheet includes:
- Video filename, size, resolution, codec, and duration at the top
- 25 thumbnails arranged in a 5x5 grid
- Each thumbnail labeled with its timestamp

## Technical Details

- Supports common video formats: mp4, mkv, avi, mov, wmv, flv, webm, m4v, mpg, mpeg, 3gp
- Uses FFmpeg for video processing and frame extraction
- Outputs 1920px wide sheets with quality-preserving JPEG compression
- Skips videos that already have a sheet generated

## Requirements

- Windows OS
- No additional installations required - FFmpeg is bundled with the application

## Building From Source

The application is written in Python and can be packaged into a standalone executable using PyInstaller:

```bash
pip install pillow pyinstaller
pyinstaller --onefile --add-data "ffmpeg.exe;." --add-data "ffprobe.exe;." --add-data "arial.ttf;." video_sheet_generator.py
```

## Development Notes

- Uses ThreadPoolExecutor for parallel processing
- Automatically handles path resolution for both development and PyInstaller environments
- Creates temporary directories for extraction work
- Handles different Pillow versions for compatibility

## License

This project is available under the MIT License.

## Acknowledgements

- Uses FFmpeg for video processing
- Built with Python and Pillow for image manipulation
