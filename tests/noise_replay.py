#!/usr/bin/env python3
"""Measure additive-noise ASR replay; does not claim multi-speaker recognition."""
import json
import math
from pathlib import Path
import sys
import wave
import numpy as np
from faster_whisper import WhisperModel
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lab_catalog import LabCatalog


def main():
    catalog=LabCatalog(Path((ROOT/'results/latest_slam_run.txt').read_text().strip())/'destinations.yaml')
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=2)
    fixtures=[]
    for meta in sorted((ROOT/'results/live_input').glob('*.json')):
        old=json.loads(meta.read_text())
        try:expected=catalog.parse(old['text'])
        except ValueError:continue
        if expected:fixtures.append((meta,expected))
    if not fixtures:raise ValueError('No labeled recordings')
    results=[];rng=np.random.default_rng(123)
    for meta,expected in fixtures[:2]:
        with wave.open(str(meta.with_suffix('.wav')),'rb') as f:
            assert f.getframerate()==16000 and f.getnchannels()==1
            a=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
        power=float(np.mean(a*a))
        for snr in (None,20,10,0):
            noisy=a if snr is None else np.clip(a+rng.normal(0,math.sqrt(power/(10**(snr/10))),len(a)).astype(np.float32),-1,1)
            segments,_=model.transcribe(noisy,language='vi',vad_filter=True,beam_size=5,condition_on_previous_text=False)
            segments=list(segments);text=' '.join(s.text.strip() for s in segments if s.avg_logprob>-1)
            try:actual=catalog.parse(text)
            except ValueError:actual=None
            confidence=min((s.avg_logprob for s in segments),default=-10.)
            results.append(dict(file=meta.name,snr_db=snr,text=text,correct=actual==expected,avg_logprob=confidence,noisy_mode_confidence_pass=confidence>=-.8))
            print(results[-1],flush=True)
    (ROOT/'results/noise_replay_results.json').write_text(json.dumps(dict(source='Previously recorded speech plus deterministic Gaussian noise; no live crowded-room or speaker-identity validation',cases=results),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
