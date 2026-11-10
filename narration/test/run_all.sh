#!/bin/bash
# 試しを全部走らせる（試しA・B＝正解つき、h2・h3＝人の生声）
cd "$(dirname "$0")/.."
P=.venv/bin/python
for n in a b; do
  nice -n 15 $P henshu.py test/tts1/raw_$n.wav test/tts1/daihon.txt test/out_$n > test/out_$n.log 2>&1
  $P hyouka.py test/tts1/raw_$n.truth.json test/out_$n/kiroku.json > test/out_$n.hyouka.txt 2>&1
done
for n in h2 h3; do
  nice -n 15 $P henshu.py test/hito/$n.wav test/hito/$n.txt test/out_$n > test/out_$n.log 2>&1
done
echo done
