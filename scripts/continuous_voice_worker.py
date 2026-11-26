#!/usr/bin/env python3
"""Always-listening local microphone -> endpointing -> cached Whisper model."""
import json
import os
from pathlib import Path
import queue
import selectors
import subprocess
import tempfile
import threading
import time


def main():
    import numpy as np
    from faster_whisper import WhisperModel
    from continuous_voice_core import SpeechSegmenter, is_navigation_command
    from voice_audio import pulse_source
    lock=threading.Lock()
    def emit(**item):
        with lock:print(json.dumps(item,ensure_ascii=False),flush=True)
    emit(stage='loading')
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4)
    source=pulse_source()
    chunks=queue.Queue(maxsize=2)
    done=threading.Event()

    def recognize():
        while not done.is_set():
            try:pcm,audio_end=chunks.get(timeout=.2)
            except queue.Empty:continue
            try:
                emit(stage='transcribing')
                audio=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                segments,_=model.transcribe(audio,language='vi',vad_filter=True,
                    beam_size=5,
                    condition_on_previous_text=False)
                accepted_segments=[s for s in segments if s.avg_logprob>-1]
                text=' '.join(s.text.strip() for s in accepted_segments).strip()
                logprob=min((s.avg_logprob for s in accepted_segments),default=-10.)
                # Ordinary conversation is ignored; the ROS controller still
                # validates destinations and requires explicit confirmation.
                if text:
                    item=dict(stage='transcript' if is_navigation_command(text) else 'context_transcript',text=text,source='Live continuous microphone, PulseAudio, Whisper small',
                              avg_logprob=logprob,time_unix=time.time(),audio_end_unix=audio_end,audio_seconds=round(len(audio)/16000,2))
                    if os.environ.get('TB4_LOG_TRANSCRIPTS')=='1':
                        folder=Path(__file__).resolve().parents[1]/'results/live_continuous'
                        folder.mkdir(parents=True,exist_ok=True)
                        with (folder/'transcripts.jsonl').open('a') as stream:
                            stream.write(json.dumps(item,ensure_ascii=False)+'\n')
                    emit(**item)
            except Exception as exc:
                emit(stage='error',message=str(exc))
            finally:
                emit(stage='listening')

    thread=threading.Thread(target=recognize,daemon=True);thread.start()
    segmenter=SpeechSegmenter()
    command=['parec','--raw','--format=s16le','--rate=16000','--channels=1',
             '--latency-msec=60','--client-name=TB4ContinuousVoice','--device='+source]
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                buffer=bytearray();last_data=time.monotonic();frame_bytes=960
                emit(stage='listening')
                while True:
                    if not selector.select(timeout=.25):
                        if time.monotonic()-last_data>5:raise TimeoutError('Micro không trả dữ liệu')
                        continue
                    block=os.read(process.stdout.fileno(),8192)
                    if not block:
                        errors.seek(0)
                        raise RuntimeError('Mất kết nối micro: '+errors.read().decode(errors='replace'))
                    last_data=time.monotonic();buffer.extend(block)
                    while len(buffer)>=frame_bytes:
                        frame=bytes(buffer[:frame_bytes]);del buffer[:frame_bytes]
                        rms=float(np.sqrt(np.mean((np.frombuffer(frame,dtype='<i2').astype(np.float32)/32768)**2)))
                        was_active=segmenter.active
                        pcm=segmenter.feed(frame,rms)
                        if segmenter.active and not was_active:emit(stage='speech')
                        if pcm is not None:
                            if chunks.full():
                                try:chunks.get_nowait()
                                except queue.Empty:pass
                            chunks.put_nowait((pcm,time.time()))
                        elif was_active and not segmenter.active:emit(stage='listening')
        finally:
            done.set();process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            process.stdout.close()


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except Exception as exc:
        print(json.dumps(dict(stage='error',message=str(exc)),ensure_ascii=False),flush=True)
        raise SystemExit(1)
