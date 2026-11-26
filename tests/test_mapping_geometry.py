import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mapping_geometry import nearest_forward_obstacle


def test_rotated_sensor_side_ray_is_not_forward():
    value=nearest_forward_obstacle([.2],0,.01,.1,12,0,0,math.pi/2)
    assert math.isinf(value)


def test_rotated_sensor_negative_quarter_turn_detects_front():
    value=nearest_forward_obstacle([.3],-math.pi/2,.01,.1,12,0,0,math.pi/2)
    assert abs(value-.3)<1e-9


def test_sensor_translation_included():
    value=nearest_forward_obstacle([.4],0,.01,.1,12,.1,0,0)
    assert abs(value-.5)<1e-9


def test_invalid_scan_refused_and_infinite_range_is_clear():
    assert nearest_forward_obstacle([math.nan,0],0,.01,.1,12,0,0,0) is None
    assert nearest_forward_obstacle([math.inf],0,.01,.1,12,0,0,0)==12
