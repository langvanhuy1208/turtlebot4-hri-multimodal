#!/usr/bin/env python3
"""Replay existing live-user WAVs through the automatic endpoint/ASR pipeline."""
import json
from pathlib import Path
import sys
import wave

import numpy as np
from faster_whisper import WhisperModel
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from continuous_voice_core import SpeechSegmenter
from lab_catalog import LabCatalog


def main():
    folder=Path((ROOT/'results/latest_slam_run.txt').read_text().strip())
    catalog=LabCatalog(folder/'destinations.yaml')
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4)
    results=[];skipped=[]
    for metadata in sorted((ROOT/'results/live_input').glob('*.json')):
        previous=json.loads(metadata.read_text())
        try:expected=catalog.parse(previous['text'])
        except ValueError:
            skipped.append(dict(file=metadata.name,reason='Legacy transcript has no validated destination; not a labelled command fixture'));continue
        with wave.open(str(metadata.with_suffix('.wav')),'rb') as stream:
            assert stream.getframerate()==16000 and stream.getnchannels()==1
            data=stream.readframes(stream.getnframes())+b'\0'*(16000*2)
        segmenter=SpeechSegmenter();decoded=[]
        for offset in range(0,len(data)-959,960):
            frame=data[offset:offset+960]
            samples=np.frombuffer(frame,dtype='<i2').astype(np.float32)/32768
            pcm=segmenter.feed(frame,float(np.sqrt(np.mean(samples**2))))
            if pcm is not None:
                segments,_=model.transcribe(np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768,
                    language='vi',vad_filter=True,
                    beam_size=5,condition_on_previous_text=False)
                text=' '.join(s.text.strip() for s in segments if s.avg_logprob>-1).strip()
                if text:decoded.append(text)
        print(metadata.name, 'expected:', previous['text'], 'decoded:', decoded, flush=True)
        assert len(decoded)==1,(metadata.name,decoded)
        actual=catalog.parse(decoded[0]);assert actual==expected,(decoded,actual,expected)
        results.append(dict(file=metadata.name,text=decoded[0],route=actual,passed=True))
    assert results,'No speech fixtures available'
    report=dict(source='Replay of previous live-user microphone recordings; not a new live test',
                passed=True,cases=results,skipped=skipped)
    out=ROOT/'results/live_continuous';out.mkdir(exist_ok=True)
    (out/'replay_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
