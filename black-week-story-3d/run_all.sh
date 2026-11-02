#!/bin/bash
cd "$(dirname "$0")"
N=1140; W=4; STEP=$(( (N + W - 1) / W ))
pids=()
for i in $(seq 0 $((W-1))); do s=$((i*STEP)); e=$((s+STEP)); [ $e -gt $N ] && e=$N
  node render.js $s $e chunks/c$i.mp4 > chunks/log$i.txt 2>&1 & pids+=($!); done
rc=0; for p in "${pids[@]}"; do wait $p || rc=1; done
echo "ALL_DONE rc=$rc"
