#!/usr/bin/env python3
"""Fail-closed velocity arbitration, independent of ROS or perception model."""
import math


class Safety:
    def __init__(self, warning=1.5, stop=.8, release=1.0, timeout=1.0):
        if not 0<stop<warning or release<0 or timeout<=0:raise ValueError('Invalid safety zones')
        self.warning=warning;self.stop=stop;self.release=release;self.timeout=timeout
        self.clear_since=None
        self.blocked=True

    def evaluate(self,now,scan_age,people_age,nearest_person,nearest_obstacle,command_age):
        if not all(math.isfinite(v) and v>=0 for v in (now,scan_age,people_age,command_age)):
            reason='sensor_stale'
        elif scan_age>self.timeout or people_age>self.timeout:reason='sensor_stale'
        elif nearest_obstacle<.35:reason='obstacle_stop'
        elif nearest_person<self.stop:reason='person_stop'
        else:reason=None
        if reason:
            self.blocked=True;self.clear_since=None
            return 0.,reason
        if self.blocked:
            if self.clear_since is None:self.clear_since=now
            if now-self.clear_since<self.release:return 0.,'waiting_clear'
            self.blocked=False
        if command_age>.5:return 0.,'command_stale'
        return (.35,'person_warning') if nearest_person<self.warning else (1.,'clear')
