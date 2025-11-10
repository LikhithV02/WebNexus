# MoviePy - Loading Video Files

MoviePy is a Python library for video editing: cutting, concatenations, title insertions, video compositing, video processing, and creation of custom effects.

## Installation

Install MoviePy with pip:

```bash
pip install moviepy
```

For the latest development version:

```bash
pip install git+https://github.com/Zulko/moviepy.git
```

## Loading Video Files

### Basic Video Loading

The most common way to load a video file is using the `VideoFileClip` class:

```python
from moviepy.editor import VideoFileClip

# Load a video file
clip = VideoFileClip("my_video.mp4")

# Get basic properties
print(f"Duration: {clip.duration} seconds")
print(f"Size: {clip.size}")
print(f"FPS: {clip.fps}")

# Don't forget to close the clip
clip.close()
```

### Supported Video Formats

MoviePy supports a wide range of video formats through FFmpeg:

- **MP4** (.mp4) - Most common, good compression
- **AVI** (.avi) - Uncompressed, large file sizes
- **MOV** (.mov) - QuickTime format
- **MKV** (.mkv) - Matroska container
- **WebM** (.webm) - Web-optimized format
- **FLV** (.flv) - Flash video format

### Loading with Options

You can specify additional options when loading:

```python
clip = VideoFileClip(
    "video.mp4",
    audio=True,          # Load audio track
    target_resolution=(1280, 720),  # Resize on load
    resize_algorithm='bicubic'      # Resizing method
)
```

## Working with Audio

### Extracting Audio

Extract audio from a video file:

```python
from moviepy.editor import VideoFileClip

video = VideoFileClip("movie.mp4")
audio = video.audio

# Save audio to file
audio.write_audiofile("extracted_audio.mp3")

# Close resources
video.close()
```

### Loading Audio Files

Load audio files directly:

```python
from moviepy.editor import AudioFileClip

audio = AudioFileClip("soundtrack.mp3")

# Audio properties
print(f"Duration: {audio.duration} seconds")
print(f"FPS (sample rate): {audio.fps}")
print(f"Number of channels: {audio.nchannels}")

audio.close()
```

### Supported Audio Formats

- **MP3** (.mp3) - Compressed, lossy
- **WAV** (.wav) - Uncompressed, lossless
- **AAC** (.aac, .m4a) - Advanced audio coding
- **OGG** (.ogg) - Open format
- **FLAC** (.flac) - Lossless compression

## Loading Image Sequences

### From Directory

Load a sequence of images as a video:

```python
from moviepy.editor import ImageSequenceClip
import glob

# Get all images in order
image_files = sorted(glob.glob("frames/*.png"))

# Create clip from sequence
clip = ImageSequenceClip(image_files, fps=24)

# Save as video
clip.write_videofile("output.mp4")
```

### From Individual Images

```python
from moviepy.editor import ImageClip

# Load single image
img = ImageClip("image.png")

# Set duration (images don't have duration by default)
img = img.set_duration(5)  # 5 seconds

# Multiple images
from moviepy.editor import concatenate_videoclips

img1 = ImageClip("img1.png").set_duration(3)
img2 = ImageClip("img2.png").set_duration(3)
img3 = ImageClip("img3.png").set_duration(3)

slideshow = concatenate_videoclips([img1, img2, img3])
slideshow.write_videofile("slideshow.mp4", fps=24)
```

## Advanced Loading Options

### Subclipping During Load

Load only a portion of a video:

```python
# Load only seconds 10-20
clip = VideoFileClip("long_video.mp4").subclip(10, 20)

# From start to 30 seconds
clip = VideoFileClip("video.mp4").subclip(0, 30)

# From 1 minute to end
clip = VideoFileClip("video.mp4").subclip(60)
```

### Memory Management

For large videos, use these techniques:

```python
# Option 1: Use with statement (automatic cleanup)
with VideoFileClip("large_video.mp4") as clip:
    # Process the video
    result = clip.subclip(0, 10)
    result.write_videofile("output.mp4")

# Option 2: Manual cleanup
clip = VideoFileClip("video.mp4")
try:
    # Process video
    pass
finally:
    clip.close()
```

### Lazy Loading

MoviePy loads videos lazily by default:

```python
# Video is not fully loaded into memory
clip = VideoFileClip("video.mp4")

# Frames are loaded on-demand when accessed
frame_at_5s = clip.get_frame(5.0)

# Force loading entire video (not recommended for large files)
clip = clip.to_RGB()
```

## Loading from URLs

Load videos directly from the internet:

```python
from moviepy.editor import VideoFileClip
import urllib.request

# Download video
url = "https://example.com/video.mp4"
local_file = "downloaded_video.mp4"
urllib.request.urlretrieve(url, local_file)

# Load the downloaded video
clip = VideoFileClip(local_file)
```

## Color Space and Format

### RGB vs other formats

```python
# Default loading (RGB)
clip = VideoFileClip("video.mp4")

# Convert to grayscale
gray_clip = clip.fx(lambda pic: pic.mean(axis=2).astype('uint8'))

# Work with specific color channels
red_channel = clip.fl_image(lambda image: image[:,:,0])
```

### Pixel Format

```python
# Specify pixel format
clip = VideoFileClip("video.mp4", pixel_format='rgb24')

# Common formats:
# - 'rgb24': Standard RGB
# - 'rgba': RGB with alpha channel
# - 'gray': Grayscale
# - 'yuv420p': YUV color space
```

## Performance Tips

### 1. Use Appropriate Resolution

```python
# Load at lower resolution for faster processing
clip = VideoFileClip("4k_video.mp4", target_resolution=(1920, 1080))
```

### 2. Disable Audio When Not Needed

```python
# Skip audio loading
clip = VideoFileClip("video.mp4", audio=False)
```

### 3. Use Subclips

```python
# Only load needed portion
clip = VideoFileClip("movie.mp4").subclip(60, 120)  # 1-2 minutes only
```

### 4. Close Resources

```python
# Always close clips when done
clip.close()

# Or use context managers
with VideoFileClip("video.mp4") as clip:
    clip.write_videofile("output.mp4")
```

## Troubleshooting

### Common Issues

#### FFmpeg Not Found

```bash
# Error: FFmpeg not found
# Solution: Install FFmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

#### Codec Not Supported

```python
# Error: Codec not supported
# Solution: Try re-encoding with FFmpeg

import subprocess

subprocess.run([
    'ffmpeg', '-i', 'input.avi',
    '-c:v', 'libx264',  # Video codec
    '-c:a', 'aac',      # Audio codec
    'output.mp4'
])
```

#### Memory Errors

```python
# Error: Out of memory
# Solution: Process in smaller chunks

def process_in_chunks(clip, chunk_size=10):
    results = []
    for start in range(0, int(clip.duration), chunk_size):
        end = min(start + chunk_size, clip.duration)
        chunk = clip.subclip(start, end)
        # Process chunk
        results.append(process_chunk(chunk))
        chunk.close()
    return results
```

## Best Practices

### 1. Always Close Resources

```python
# Bad
clip = VideoFileClip("video.mp4")
# ... use clip
# No cleanup

# Good
clip = VideoFileClip("video.mp4")
try:
    # ... use clip
finally:
    clip.close()

# Better
with VideoFileClip("video.mp4") as clip:
    # ... use clip
    # Automatic cleanup
```

### 2. Check File Exists

```python
import os
from pathlib import Path

def safe_load_video(filename):
    if not Path(filename).exists():
        raise FileNotFoundError(f"Video file not found: {filename}")

    try:
        clip = VideoFileClip(filename)
        return clip
    except Exception as e:
        print(f"Error loading video: {e}")
        return None
```

### 3. Validate Properties

```python
def validate_video(clip, min_duration=1.0, required_fps=30):
    if clip.duration < min_duration:
        raise ValueError(f"Video too short: {clip.duration}s")

    if clip.fps < required_fps:
        raise ValueError(f"FPS too low: {clip.fps}")

    if clip.size[0] < 640 or clip.size[1] < 480:
        raise ValueError(f"Resolution too low: {clip.size}")

    return True
```

## API Reference

### VideoFileClip

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filename` | str | required | Path to video file |
| `audio` | bool | True | Load audio track |
| `target_resolution` | tuple | None | Resize to (width, height) |
| `resize_algorithm` | str | 'bicubic' | Resizing algorithm |
| `audio_buffersize` | int | 200000 | Audio buffer size |
| `audio_fps` | int | 44100 | Audio sample rate |
| `audio_nbytes` | int | 2 | Audio bytes per sample |
| `verbose` | bool | False | Print loading info |

**Properties:**

- `duration`: Video duration in seconds
- `fps`: Frames per second
- `size`: Tuple (width, height)
- `w`: Width in pixels
- `h`: Height in pixels
- `audio`: AudioFileClip object or None
- `filename`: Original filename

**Methods:**

- `get_frame(t)`: Get frame at time t
- `subclip(t_start, t_end)`: Extract subclip
- `write_videofile(filename, **kwargs)`: Save to file
- `close()`: Release resources
- `to_RGB()`: Convert to RGB format

### AudioFileClip

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filename` | str | required | Path to audio file |
| `buffersize` | int | 200000 | Buffer size |
| `nbytes` | int | 2 | Bytes per sample |
| `fps` | int | 44100 | Sample rate |

**Properties:**

- `duration`: Audio duration in seconds
- `fps`: Sample rate
- `nchannels`: Number of audio channels

**Methods:**

- `write_audiofile(filename, **kwargs)`: Save to file
- `close()`: Release resources

## Examples

### Complete Example: Video Analysis

```python
from moviepy.editor import VideoFileClip
import numpy as np

def analyze_video(filename):
    """Analyze video and print statistics"""

    with VideoFileClip(filename) as clip:
        # Basic info
        print(f"File: {filename}")
        print(f"Duration: {clip.duration:.2f} seconds")
        print(f"Resolution: {clip.w}x{clip.h}")
        print(f"FPS: {clip.fps}")
        print(f"Total frames: {int(clip.duration * clip.fps)}")

        # Audio info
        if clip.audio:
            print(f"Audio channels: {clip.audio.nchannels}")
            print(f"Audio sample rate: {clip.audio.fps}")
        else:
            print("No audio track")

        # Sample frames
        sample_times = [0, clip.duration/2, clip.duration-0.1]
        print("\nSample frames:")
        for t in sample_times:
            frame = clip.get_frame(t)
            avg_brightness = np.mean(frame)
            print(f"  t={t:.2f}s: brightness={avg_brightness:.2f}")

# Usage
analyze_video("my_video.mp4")
```

### Complete Example: Video Converter

```python
from moviepy.editor import VideoFileClip
import sys

def convert_video(input_file, output_file, target_fps=30, target_resolution=None):
    """Convert video to different format/settings"""

    try:
        with VideoFileClip(input_file) as clip:
            print(f"Loading: {input_file}")
            print(f"Original: {clip.w}x{clip.h} @ {clip.fps} fps")

            # Apply transformations
            result = clip

            # Change FPS if needed
            if target_fps and clip.fps != target_fps:
                result = result.set_fps(target_fps)
                print(f"FPS changed to: {target_fps}")

            # Resize if needed
            if target_resolution:
                result = result.resize(target_resolution)
                print(f"Resized to: {target_resolution}")

            # Save
            print(f"Saving to: {output_file}")
            result.write_videofile(
                output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )

            print("✓ Conversion complete!")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

# Usage
if __name__ == "__main__":
    convert_video(
        "input.avi",
        "output.mp4",
        target_fps=30,
        target_resolution=(1280, 720)
    )
```

## Next Steps

- Learn about [Video Compositing](compositing.html)
- Explore [Video Effects](effects.html)
- Check out [Audio Processing](audio.html)
- See [Advanced Examples](examples.html)

## Additional Resources

- [MoviePy GitHub](https://github.com/Zulko/moviepy)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [MoviePy Gallery](https://zulko.github.io/moviepy/gallery.html)
- [Community Forum](https://github.com/Zulko/moviepy/discussions)

---

*Last updated: 2024-01-15*
