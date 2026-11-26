from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from arrival_control import ArrivalReceipt,DestinationGestures


def test_receipt_only_exists_after_arrival():
    receipt=ArrivalReceipt()
    assert not receipt.acknowledge('anything')
    token=receipt.arrive('ban_1',[])['request_id']
    assert not receipt.acknowledge('wrong')
    assert receipt.pending is not None
    assert receipt.acknowledge(token)
    assert receipt.pending is None
    assert not receipt.acknowledge(token)


def test_each_arrival_has_a_new_token():
    receipt=ArrivalReceipt();a=receipt.arrive('a',['b'])['request_id']
    assert receipt.pending['remaining']==['b']
    assert receipt.acknowledge(a)
    b=receipt.arrive('b',[])['request_id']
    assert b!=a and not receipt.acknowledge(a)
    assert receipt.acknowledge(b)


def test_pending_arrival_cannot_be_overwritten():
    receipt=ArrivalReceipt();receipt.arrive('a',[])
    with pytest.raises(ValueError):receipt.arrive('b',[])


@pytest.mark.parametrize('label,rid',[('Pointing_Up','a'),('Victory','b'),('Three_Fingers','c')])
def test_independent_gesture_commands(label,rid):
    gestures=DestinationGestures(['a','b','c'])
    assert gestures.receive(label,0) is None
    gestures.receive('NONE',1);gestures.receive('NONE',1.4)
    assert gestures.receive(label,1.5)==rid
    for i in range(20):assert gestures.receive(label,2+i*.05) is None
    gestures.receive('NONE',4);gestures.receive('NONE',4.4)
    assert gestures.receive(label,4.5)==rid


def test_transition_does_not_erase_armed_gesture():
    gestures=DestinationGestures(['a'])
    gestures.receive('NONE',0);gestures.receive('NONE',.4)
    gestures.receive('TRANSITION',.5)
    assert gestures.receive('Pointing_Up',.9)=='a'


def test_short_neutral_does_not_rearm():
    gestures=DestinationGestures(['a'])
    gestures.receive('NONE',0);gestures.receive('NONE',.1)
    assert gestures.receive('Pointing_Up',.2) is None


def test_invalid_gesture_configuration():
    for targets in ([],['a','a'],['a','b','c','d']):
        with pytest.raises(ValueError):DestinationGestures(targets)


def test_stop_requires_fresh_neutral_before_another_destination():
    gestures=DestinationGestures(['a'])
    gestures.receive('NONE',0);gestures.receive('NONE',.4)
    gestures.receive('Open_Palm',.5)
    assert gestures.receive('Pointing_Up',.6) is None
    gestures.receive('NONE',1);gestures.receive('NONE',1.4)
    assert gestures.receive('Pointing_Up',1.5)=='a'


def test_thumb_never_selects_a_destination():
    gestures=DestinationGestures(['a','b','c'])
    gestures.receive('NONE',0);gestures.receive('NONE',.4)
    assert gestures.receive('Thumb_Up',.5) is None
    assert gestures.confirmation_event
    for i in range(10):
        assert gestures.receive('Thumb_Up',1+i*.1) is None
        assert not gestures.confirmation_event


def test_held_thumb_requires_release_before_new_confirmation():
    gestures=DestinationGestures(['a'])
    gestures.receive('NONE',0);gestures.receive('NONE',.4)
    gestures.receive('Thumb_Up',.5)
    assert gestures.confirmation_event
    gestures.receive('Thumb_Up',1);assert not gestures.confirmation_event
    gestures.receive('NONE',2);gestures.receive('NONE',2.4)
    gestures.receive('Thumb_Up',2.5);assert gestures.confirmation_event
