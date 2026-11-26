"""Transactions and map-bound destinations: no ROS or physical robot required."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hri_confirmation import ButtonEdges, ConfirmationGate
from lab_catalog import LabCatalog, add_destination, create_catalog


@pytest.fixture
def lab(tmp_path):
    image = np.full((100, 100), 254, dtype=np.uint8)
    image[0:10, :] = 0
    image[40:50, 40:50] = 205
    cv2.imwrite(str(tmp_path / 'map.pgm'), image)
    (tmp_path / 'map.yaml').write_text(yaml.safe_dump(dict(image='map.pgm', resolution=0.05,
        origin=[0, 0, 0], negate=0, occupied_thresh=0.65, free_thresh=0.196)))
    path = tmp_path / 'destinations.yaml'
    create_catalog(tmp_path / 'map.yaml', path)
    return path


def test_named_destination_and_strict_parser(lab):
    add_destination(lab, 'ban_2', 'Bàn số 2', ['bàn hai', 'bàn 2'], 1, 1, 0)
    catalog = LabCatalog(lab)
    assert catalog.parse('Đi đến bàn số 2') == ['ban_2']
    assert catalog.parse('Đi đến bàn hai') == ['ban_2']
    assert catalog.parse('Dừng lại') == []
    with pytest.raises(ValueError):
        catalog.parse('Đi đến bàn 3')


@pytest.mark.parametrize('pose', [(0.01, 1, 0), (1, 4.8, 0), (2.2, 2.7, 0),
                                  (-1, 1, 0), (1, 1, float('nan'))])
def test_reject_bad_destination_without_changing_catalog(lab, pose):
    before = lab.read_bytes()
    with pytest.raises(ValueError):
        add_destination(lab, 'bad', 'Sai', [], *pose)
    assert lab.read_bytes() == before


def test_alias_collision_is_atomic(lab):
    add_destination(lab, 'a', 'Bàn 1', ['bàn một'], 1, 1, 0)
    before = lab.read_bytes()
    with pytest.raises(ValueError):
        add_destination(lab, 'b', 'Bàn 2', ['ban mot'], 2, 1, 0)
    assert lab.read_bytes() == before


def test_changed_map_rejected(lab):
    (lab.parent / 'map.yaml').write_text((lab.parent / 'map.yaml').read_text().replace('0.05', '0.06'))
    with pytest.raises(ValueError, match='thay đổi'):
        LabCatalog(lab)


def test_existing_catalog_never_overwritten(lab):
    with pytest.raises(ValueError):
        create_catalog(lab.parent / 'map.yaml', lab)


def test_confirm_once_and_reject_stale_transaction():
    gate = ConfirmationGate()
    old = gate.request('Đi đến A', ['A'], 0)['request_id']
    assert gate.confirm('wrong', 1) is None
    assert gate.confirm(old, 1) == 'Đi đến A'
    assert gate.confirm(old, 1) is None
    new = gate.request('Đi đến B', ['B'], 2)['request_id']
    assert old != new
    assert gate.confirm(old, 3) is None
    assert gate.confirm(new, 3) == 'Đi đến B'


def test_expired_request_cannot_move():
    gate = ConfirmationGate(timeout=2)
    request = gate.request('Đi đến A', ['A'], 0)
    assert gate.confirm(request['request_id'], 2) is None
    assert gate.pending is None


def test_no_overlapping_requests():
    gate = ConfirmationGate()
    gate.request('Đi đến A', ['A'], 0)
    with pytest.raises(ValueError):
        gate.request('Đi đến B', ['B'], 1)


def test_held_thumb_cannot_confirm():
    gate = ConfirmationGate()
    gate.request('Đi đến A', ['A'], 0)
    for now in (0.1, 0.5, 1):
        assert gate.gesture('Thumb_Up', now) is None
    assert gate.gesture('NONE', 1.1) is None
    assert gate.gesture('NONE', 1.5) is None
    assert gate.gesture('Thumb_Up', 1.6) == 'Đi đến A'
    gate.request('Đi đến B', ['B'], 2)
    assert gate.gesture('Thumb_Up', 2.5) is None


def test_neutral_must_be_continuous():
    gate = ConfirmationGate()
    gate.request('Đi đến A', ['A'], 0)
    gate.gesture('NONE', 0.1)
    gate.gesture('TRANSITION', 0.2)
    gate.gesture('NONE', 0.4)
    assert gate.gesture('Thumb_Up', 0.5) is None


def test_button_held_on_startup_not_a_new_press():
    edge = ButtonEdges()
    assert edge.update([1, 0]) == []
    assert edge.update([1, 0]) == []
    assert edge.update([0, 0]) == []
    assert edge.update([1, 0]) == [0]
    assert edge.update([1, 0]) == []


def test_gestures_follow_teaching_without_shuffling_existing_slots():
    from lab_catalog import gesture_slots
    assert gesture_slots(['quay'],['unconfigured'])==['quay']
    assert gesture_slots(['quay','cua'],['quay'])==['quay','cua']
    assert gesture_slots(['cua','quay','ban'],['quay','cua'])==['quay','cua','ban']
    assert gesture_slots(['cua','ban','moi'],['quay','cua','ban'])==['moi','cua','ban']
