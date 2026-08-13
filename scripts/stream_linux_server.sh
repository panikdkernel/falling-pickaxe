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

if [ ! -d ".venv" ]; then
  echo "Error: Virtual environment .venv not found. Run ./scripts/run.sh once first."
  exit 1
fi

echo "======================================"
echo "    Falling Pickaxe Server Setup      "
echo "======================================"

# Prompt for STREAM_KEY if not already set
if [ -z "$STREAM_KEY" ]; then
    read -p "Enter your YouTube STREAM_KEY: " INPUT_KEY
    if [ -n "$INPUT_KEY" ]; then
        export STREAM_KEY="$INPUT_KEY"
    else
        echo "Error: STREAM_KEY is required."
        exit 1
    fi
fi

# Run Python script to interactively update config.json
.venv/bin/python -c "
import json, os

config_path = 'config.json'
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
except Exception as e:
    print('Failed to load config.json')
    exit(1)

print(f'\nCurrent YouTube API_KEY: {config.get(\"API_KEY\", \"\")}')
new_api = input('Enter new API_KEY (press Enter to keep current): ').strip()
if new_api:
    config['API_KEY'] = new_api

print(f'\nCurrent CHANNEL_ID: {config.get(\"CHANNEL_ID\", \"\")}')
new_channel = input('Enter new CHANNEL_ID (press Enter to keep current): ').strip()
if new_channel:
    config['CHANNEL_ID'] = new_channel

print(f'\nCurrent LIVESTREAM_ID: {config.get(\"LIVESTREAM_ID\", \"\")}')
new_stream = input('Enter new LIVESTREAM_ID (press Enter to keep current): ').strip()
if new_stream:
    config['LIVESTREAM_ID'] = new_stream

with open(config_path, 'w') as f:
    config['CHAT_CONTROL'] = True
    json.dump(config, f, indent=4)
print('\nconfig.json updated successfully (CHAT_CONTROL automatically enabled)!')
"

# Cleanup function to kill background processes on exit
cleanup() {
    echo "Stopping stream and cleaning up..."
    [ -n "$GAME_PID" ] && kill $GAME_PID 2>/dev/null
    [ -n "$XVFB_PID" ] && kill $XVFB_PID 2>/dev/null
    pactl unload-module module-null-sink 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "Cleaning up previous PulseAudio instances..."
pulseaudio --kill 2>/dev/null || true
killall -9 pulseaudio 2>/dev/null || true
rm -rf /tmp/pulse-* ~/.config/pulse/* 2>/dev/null || true
sleep 1

echo "Setting up virtual audio (PulseAudio)..."
# Ensure XDG_RUNTIME_DIR is set, which pulseaudio needs
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp}

pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
sleep 1
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
export SDL_AUDIODRIVER=pulseaudio

# Increase this if the game runs too slow on your server (e.g. CPU bottleneck dropping frames). 
# 1.5 = 50% faster physics simulation per frame
export LINUX_SERVER_SPEED_BOOST=1.5

python ./src/main.py &
GAME_PID=$!
sleep 3

echo "Checking for background music..."
MUSIC_DIR="./music"
HAS_MUSIC=false

if [ -d "$MUSIC_DIR" ]; then
    # Generate concat playlist of all mp3 and wav files
    find "$MUSIC_DIR" -type f \( -name "*.mp3" -o -name "*.wav" \) -exec echo "file '{}'" \; > playlist.txt
    if [ -s playlist.txt ]; then
        echo "Found music files. Will loop background music."
        HAS_MUSIC=true
    fi
fi

echo "Starting FFmpeg stream to YouTube..."

FFMPEG_CMD=(ffmpeg -y -f x11grab -video_size 1080x1920 -framerate 60 -i :99.0 -f pulse -i virtual_speaker.monitor)

if [ "$HAS_MUSIC" = true ]; then
    # Add music input, amix filter (game audio full volume, music at 30% volume), and map the new audio track
    FFMPEG_CMD+=(-stream_loop -1 -f concat -safe 0 -i playlist.txt -filter_complex "[1:a][2:a]amix=inputs=2:duration=first:weights=1.0 0.3[aout]" -map 0:v -map "[aout]")
else
    FFMPEG_CMD+=(-map 0:v -map 1:a)
fi

FFMPEG_CMD+=(-c:v libx264 -preset ultrafast -tune zerolatency -aspect 9:16 -b:v 4500k -maxrate 5000k -bufsize 9000k -pix_fmt yuv420p -g 120 -c:a aac -b:a 128k -ar 44100 -f flv "rtmps://a.rtmp.youtube.com:443/live2/$STREAM_KEY")

"${FFMPEG_CMD[@]}"
