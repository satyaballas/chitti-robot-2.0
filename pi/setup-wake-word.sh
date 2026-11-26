#!/bin/bash
# Install the "Hey Chitti" keyword spotter (sherpa-onnx) into Chitti's Python env and download its model.
# Runs as the pi user (no sudo):  bash ~/chitti/setup-wake-word.sh
set -e
MODEL=sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01
DIR=~/chitti/models/kws
~/chitti/venv/bin/pip install --quiet sherpa-onnx
mkdir -p "$DIR"
if [ ! -d "$DIR/$MODEL" ]; then
  cd "$DIR"
  curl -sSL -o kws.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/$MODEL.tar.bz2"
  tar xjf kws.tar.bz2 && rm kws.tar.bz2
  rm -f "$MODEL"/*-epoch-12-avg-2-chunk-16-left-64.onnx     # keep only the smaller int8 models
fi
~/chitti/venv/bin/python -c "import sherpa_onnx; print('sherpa-onnx', sherpa_onnx.__version__, 'ready')"
ls "$DIR/$MODEL"
echo "Done. Restart Chitti (sudo systemctl restart chitti) and say \"Hey Chitti\"."
