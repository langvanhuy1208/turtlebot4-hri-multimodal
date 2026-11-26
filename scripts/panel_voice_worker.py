#!/usr/bin/env python3
"""One explicit microphone capture for the desktop panel; local Whisper only."""
import argparse
import json
from pathlib import Path
import time
import wave


def emit(**data):
    print(json.dumps(data,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=5)
    args=parser.parse_args()
    import numpy as np
    from voice_audio import record_audio
    emit(stage='recording',seconds=args.seconds)
    audio=record_audio(args.seconds,backend='pulse')
    rms=float(np.sqrt(np.mean(audio**2)))
    if rms<.003:raise RuntimeError('Âm thanh quá nhỏ; kiểm tra đúng micro và nói gần hơn')
    folder=Path(__file__).resolve().parents[1]/'results/live_input'
    folder.mkdir(parents=True,exist_ok=True)
    wav=folder/f'microphone_{time.time_ns()}.wav'
    with wave.open(str(wav),'wb') as stream:
        stream.setparams((1,2,16000,0,'NONE','not compressed'))
        stream.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
    emit(stage='transcribing')
    from faster_whisper import WhisperModel
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4)
    segments,_=model.transcribe(str(wav),language='vi',vad_filter=True,beam_size=5,
                                condition_on_previous_text=False)
    text=' '.join(s.text.strip() for s in segments if s.no_speech_prob<.6 and s.avg_logprob>-1).strip()
    if not text:raise RuntimeError('Chưa nhận được lời nói rõ ràng; thử thu lại')
    evidence=dict(stage='transcript',text=text,wav=str(wav),source='Live user microphone, PulseAudio, Whisper small',rms=rms)
    wav.with_suffix('.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    emit(**evidence)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        emit(stage='error',message=str(exc))
        raise SystemExit(1)
