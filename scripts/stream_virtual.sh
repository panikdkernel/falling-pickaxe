#!/bin/bash

# Script to run Pygame headless and stream video directly to YouTube Live via pipe + FFmpeg
# Usage: STREAM_KEY="your-youtube-stream-key" ./scripts/stream_virtual.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

if [ -z "$STREAM_KEY" ]; then
  echo "Error: STREAM_KEY environment variable is not set."
  echo "Usage: STREAM_KEY=\"xxxx-xxxx-xxxx-xxxx-xxxx\" ./scripts/stream_virtual.sh"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Error: Virtual environment .venv not found. Run ./scripts/run.sh once first."
  exit 1
fi

echo "Starting Pygame headless stream to YouTube Live..."
echo "Press Ctrl+C to stop."

# Stream Pygame rendering pipe directly to FFmpeg
.venv/bin/python -c "
import sys, os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
sys.path.insert(0, 'src')
import main
main.game()
" 2>/dev/null | ffmpeg -y \
  -f rawvideo \
  -vcodec rawvideo \
  -pix_fmt rgb24 \
  -s 1080x1920 \
  -r 60 \
  -i - \
  -f lavfi \
  -i anullsrc=channel_layout=stereo:sample_rate=44100 \
  -c:v libx264 \
  -preset ultrafast \
  -tune zerolatency \
  -b:v 4500k \
  -maxrate 5000k \
  -bufsize 9000k \
  -pix_fmt yuv420p \
  -g 120 \
  -c:a aac \
  -b:a 128k \
  -map 0:v -map 1:a \
  -shortest \
  -f flv "rtmps://a.rtmp.youtube.com/live2/$STREAM_KEY"
