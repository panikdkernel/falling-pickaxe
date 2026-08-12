#!/bin/bash

# Script to run Pygame with BOTH video and audio on a headless Linux server
# Usage: STREAM_KEY="your-stream-key" ./scripts/stream_linux_server.sh

# PREREQUISITES (Run this on your Ubuntu server first):
# sudo apt-get update
# sudo apt-get install -y xvfb pulseaudio ffmpeg dbus-x11

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

if [ -z "$STREAM_KEY" ]; then
  echo "Error: STREAM_KEY environment variable is not set."
  echo "Usage: STREAM_KEY=\"xxxx-xxxx-xxxx-xxxx-xxxx\" ./scripts/stream_linux_server.sh"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Error: Virtual environment .venv not found. Run ./scripts/run.sh once first."
  exit 1
fi

# Cleanup function to kill background processes on exit
cleanup() {
    echo "Stopping stream and cleaning up..."
    [ -n "$GAME_PID" ] && kill $GAME_PID 2>/dev/null
    [ -n "$XVFB_PID" ] && kill $XVFB_PID 2>/dev/null
    pactl unload-module module-null-sink 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "Setting up virtual audio (PulseAudio)..."
pulseaudio -D --exit-idle-time=-1 2>/dev/null || true
pactl load-module module-null-sink sink_name=virtual_speaker 2>/dev/null || true

export PULSE_SINK=virtual_speaker
export PULSE_SOURCE=virtual_speaker.monitor

echo "Setting up virtual display (Xvfb)..."
export DISPLAY=:99
# Force kill any lingering Xvfb sessions that might have wrong resolutions
killall Xvfb 2>/dev/null || true
sleep 1
Xvfb :99 -screen 0 1080x1920x24 -ac &
XVFB_PID=$!
sleep 2

echo "Starting Pygame..."
source .venv/bin/activate
# Note: No 'dummy' drivers used here! Pygame will render to the virtual screen & audio
export HEADLESS_FULLSCREEN=1
python ./src/main.py &
GAME_PID=$!
sleep 3

echo "Starting FFmpeg stream to YouTube..."
ffmpeg -y \
  -f x11grab -video_size 1080x1920 -framerate 60 -i :99.0 \
  -f pulse -i virtual_speaker.monitor \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -aspect 9:16 -b:v 4500k \
  -maxrate 5000k -bufsize 9000k -pix_fmt yuv420p -g 120 \
  -c:a aac -b:a 128k -ar 44100 \
  -map 0:v -map 1:a \
  -f flv "rtmps://a.rtmp.youtube.com:443/live2/$STREAM_KEY"
