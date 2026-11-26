import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from social_safety import Safety
from frontier_core import frontiers


def test_person_stop_and_stable_release():
    s=Safety()
    assert s.evaluate(0,0,0,.6,1,0)==(0.,'person_stop')
    assert s.evaluate(1,0,0,2,1,0)==(0.,'waiting_clear')
    assert s.evaluate(1.8,0,0,.7,1,0)==(0.,'person_stop')
    assert s.evaluate(2,0,0,2,1,0)[0]==0
    assert s.evaluate(3.1,0,0,1.2,1,0)==(.35,'person_warning')
    assert s.evaluate(4,0,0,2,1,0)==(1.,'clear')


def test_lost_perception_and_obstacle_always_stop():
    s=Safety(release=0)
    assert s.evaluate(0,0,2,float('inf'),1,0)==(0.,'sensor_stale')
    assert s.evaluate(1,0,0,3,.2,0)==(0.,'obstacle_stop')
    assert s.evaluate(2,0,0,3,2,2)==(0.,'command_stale')
    assert s.evaluate(3,0,0,3,2,0)==(1.,'clear')


def test_frontier_reachability_and_obstacle_clearance():
    grid=np.full((50,70),-1,dtype=np.int16);grid[5:45,5:40]=0
    grid[:,30]=100 # wall separates robot from right frontier
    f=frontiers(grid,.1,(15,25))
    assert f and all(c['x']<26 for c in f)
    assert frontiers(grid,.1,(30,20))==[]


def test_closed_known_room_has_no_frontiers():
    g=np.zeros((40,40),dtype=np.int16);g[[0,-1],:]=100;g[:,[0,-1]]=100
    assert frontiers(g,.1,(20,20))==[]


def test_person_priority_over_idle_command_and_resume_without_command():
    s=Safety(release=1)
    assert s.evaluate(0,0,0,.5,2,10)[1]=='person_stop'
    assert s.evaluate(1,0,0,2,2,10)[1]=='waiting_clear'
    assert s.evaluate(2.1,0,0,2,2,10)[1]=='command_stale'
    assert not s.blocked
    assert s.evaluate(2.2,0,0,2,2,0)[1]=='clear'
