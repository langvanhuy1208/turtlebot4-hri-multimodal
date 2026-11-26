import math
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from continuous_voice_core import SpeechSegmenter


def test_silence_produces_no_utterance():
    segmenter=SpeechSegmenter()
    for _ in range(1000):assert segmenter.feed(b'quiet',.0005) is None
    assert not segmenter.active and not segmenter.frames


def test_speech_ends_after_silence_and_preserves_preroll():
    segmenter=SpeechSegmenter()
    for _ in range(25):segmenter.feed(b'p',.0005)
    for _ in range(8):assert segmenter.feed(b's',.02) is None
    result=None
    for _ in range(20):result=segmenter.feed(b'q',.0005)
    assert result==b'p'*20+b's'*8+b'q'*20
    assert not segmenter.active


def test_short_click_does_not_become_a_command():
    segmenter=SpeechSegmenter()
    segmenter.feed(b'click',.1)
    for _ in range(30):assert segmenter.feed(b'quiet',.0001) is None


def test_two_utterances_are_separate():
    segmenter=SpeechSegmenter();results=[]
    for _ in range(2):
        for rms in [.02]*10+[.0001]*25:
            value=segmenter.feed(b'x',rms)
            if value is not None:results.append(value)
    assert len(results)==2


def test_continuous_sound_is_bounded():
    segmenter=SpeechSegmenter();results=[]
    for _ in range(600):
        value=segmenter.feed(b'x',.02)
        if value is not None:results.append(value)
        assert len(segmenter.frames)<=267
    assert len(results)==2


def test_invalid_energy_rejected():
    for value in (math.nan,math.inf,-1):
        with pytest.raises(ValueError):SpeechSegmenter().feed(b'x',value)


def test_only_navigation_utterances_enter_command_pipeline():
    from continuous_voice_core import is_navigation_command
    for text in ('Đi đến bàn số 2','Robot hãy đi đến bàn 1','Dừng lại!','Hủy điều hướng'):
        assert is_navigation_command(text)
    for text in ('Hãy subscribe cho kênh','Hôm nay trời đẹp','Vui lòng đăng ký kênh',''):
        assert not is_navigation_command(text)
