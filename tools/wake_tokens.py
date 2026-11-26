"""Spell new wake phrases in the keyword model's word pieces, for KWS_PHRASES in pi/app/config.py.

    pip install sentencepiece
    python -X utf8 tools/wake_tokens.py <model dir> "HEY CHITTI" "HELLO CHITTI"

The model dir is sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01 (it contains bpe.model and tokens.txt).
"""
import sys

import sentencepiece as spm

model_dir, phrases = sys.argv[1], sys.argv[2:]
sp = spm.SentencePieceProcessor(model_file=f"{model_dir}/bpe.model")
known = {line.split()[0] for line in open(f"{model_dir}/tokens.txt", encoding="utf-8")}
for p in phrases:
    pieces = sp.encode(p.upper(), out_type=str)
    missing = [x for x in pieces if x not in known]
    print(f'    "{" ".join(pieces)}",   # {p.lower()}' + (f"   (unknown pieces: {missing})" if missing else ""))
