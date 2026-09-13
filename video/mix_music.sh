#!/usr/bin/env bash
# 把 ElevenLabs 配樂混進 Remotion 成品：講解段用 talk.mp3（-16 dB），Demo 段（$DEMO_FROM–$DEMO_TO）換 demo.mp3（-15 dB），交接處 1.5 s 淡入淡出。
# 只處理音訊，視訊 -c:v copy，不吃記憶體。用法：bash mix_music.sh in.mp4 out.mp4 [demo_from demo_to]
set -euo pipefail
IN=$1; OUT=$2; DEMO_FROM=${3:-122.5}; DEMO_TO=${4:-223.1}
M=$(dirname "$0")/assets/generated/music
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
TALK_GAIN=0.16   # ≈ -16 dB：配樂 mean ≈ -34 dB，旁白 -19 dB，差 15 dB
DEMO_GAIN=0.18
A_LEN=$DEMO_FROM; B_LEN=$(python3 -c "print($DEMO_TO-$DEMO_FROM)"); C_LEN=$(python3 -c "print($DUR-$DEMO_TO)")
ffmpeg -y -v error -i "$IN" -i "$M/talk.mp3" -i "$M/demo.mp3" -filter_complex "
[1:a]atrim=0:$A_LEN,asetpts=PTS-STARTPTS,afade=t=in:d=1.5,afade=t=out:st=$(python3 -c "print($A_LEN-1.5)"):d=1.5,volume=$TALK_GAIN[ta];
[2:a]atrim=0:$B_LEN,asetpts=PTS-STARTPTS,afade=t=in:d=1.5,afade=t=out:st=$(python3 -c "print($B_LEN-1.5)"):d=1.5,volume=$DEMO_GAIN,adelay=$(python3 -c "print(int($DEMO_FROM*1000))")|$(python3 -c "print(int($DEMO_FROM*1000))")[tb];
[1:a]atrim=$DEMO_TO:$DUR,asetpts=PTS-STARTPTS,afade=t=in:d=1.5,afade=t=out:st=$(python3 -c "print($C_LEN-3)"):d=3,volume=$TALK_GAIN,adelay=$(python3 -c "print(int($DEMO_TO*1000))")|$(python3 -c "print(int($DEMO_TO*1000))")[tc];
[0:a][ta][tb][tc]amix=inputs=4:duration=first:normalize=0[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart "$OUT"
echo "mixed → $OUT ($DUR s)"
