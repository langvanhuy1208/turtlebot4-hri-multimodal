#!/usr/bin/env python3
"""Endpoint microphone speech from energy, with preroll and bounded memory."""
from collections import deque
import math
import re
import unicodedata


class SpeechSegmenter:
    def __init__(self, frame_ms=30, silence_ms=600, minimum_ms=180, maximum_ms=8000):
        if not 0 < minimum_ms < maximum_ms or frame_ms <= 0 or silence_ms <= 0:
            raise ValueError('Invalid speech timing')
        self.silence_frames=math.ceil(silence_ms/frame_ms)
        self.minimum_frames=math.ceil(minimum_ms/frame_ms)
        self.maximum_frames=math.ceil(maximum_ms/frame_ms)
        self.preroll=deque(maxlen=max(1,math.ceil(600/frame_ms)))
        self.noise=.001
        self.active=False
        self.frames=[]
        self.speech_frames=0
        self.quiet_frames=0

    def feed(self, frame, rms):
        if not math.isfinite(rms) or rms < 0:
            raise ValueError('Invalid audio level')
        threshold=max(.0035,self.noise*(1.8 if self.active else 3.0))
        speech=rms>=threshold
        if not self.active:
            if not speech:
                self.noise=.98*self.noise+.02*rms
                self.preroll.append(frame)
                return None
            self.active=True
            self.frames=list(self.preroll)
            self.preroll.clear()
            self.speech_frames=self.quiet_frames=0
        self.frames.append(frame)
        if speech:
            self.speech_frames+=1;self.quiet_frames=0
        else:
            self.quiet_frames+=1
        if self.quiet_frames < self.silence_frames and len(self.frames)<self.maximum_frames:
            return None
        result=b''.join(self.frames) if self.speech_frames>=self.minimum_frames else None
        self.active=False
        self.preroll.extend(self.frames[-self.preroll.maxlen:])
        self.frames=[]
        self.speech_frames=self.quiet_frames=0
        return result


def is_navigation_command(text):
    text=unicodedata.normalize('NFD',text.lower().replace('đ','d'))
    text=''.join(c for c in text if unicodedata.category(c)!='Mn')
    text=' '.join(re.sub(r'[^a-z0-9\s]',' ',text).split())
    text=re.sub(r'^(?:robot |hay |vui long )+','',text)
    return text.startswith(('goi ', 'di ', 'dieu huong ', 'luu ', 'day dia diem ', 'cap nhat dia diem ', 'xoa dia diem ', 'ban ', 'phong ', 'quay ', 'tu dong quet', 'quet tu dong', 'dieu khien thu cong', 'dung quet')) or text in ('dung', 'dung lai', 'huy', 'huy dieu huong', 'xac nhan', 'dong y')
