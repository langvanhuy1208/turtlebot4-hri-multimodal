import math
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from finger_count import count_fingers,classify_hand


def hand(extended):
    points=[(0,0,0) for _ in range(21)]
    for i,(mcp,pip,dip,tip) in enumerate([(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]):
        x=.6-i*.4
        points[mcp]=(x,1,0);points[pip]=(x,1.6,0)
        points[dip]=(x,2 if i<extended else 1.35,0)
        points[tip]=(x,2.4 if i<extended else 1.1,0)
    return points


@pytest.mark.parametrize('count,label',[(1,'Pointing_Up'),(2,'Victory'),(3,'Three_Fingers')])
def test_counts_override_wrong_builtin_gesture(count,label):
    assert count_fingers(hand(count))==count
    assert classify_hand(hand(count),'Victory')==label


def test_thumb_is_confirmation_and_not_three():
    assert classify_hand(hand(0),'Thumb_Up')=='Thumb_Up'
    assert classify_hand(hand(0),'Closed_Fist')=='Closed_Fist'
    assert classify_hand(hand(3),'Thumb_Up')=='Three_Fingers'


def test_rotation_and_mirror_do_not_change_count():
    for count in (1,2,3):
        points=hand(count)
        rotated=[(-y,x,z) for x,y,z in points]
        mirrored=[(-x,y,z) for x,y,z in points]
        assert count_fingers(rotated)==count_fingers(mirrored)==count


def test_four_fingers_remain_stop_not_destination():
    assert classify_hand(hand(4),'Open_Palm')=='Open_Palm'
    assert classify_hand(hand(4),'NONE')=='NONE'


def test_invalid_geometry_refused():
    with pytest.raises(ValueError):count_fingers([])
    points=hand(3);points[5]=(math.nan,0,0)
    with pytest.raises(ValueError):count_fingers(points)
