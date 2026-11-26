#!/usr/bin/env python3
"""Project laser returns into base coordinates before checking the forward sector."""
import math


def nearest_forward_obstacle(ranges, angle_min, angle_increment, range_min, range_max,
                             sensor_x, sensor_y, sensor_yaw, half_angle=.5):
    nearest=math.inf;valid=False
    c,s=math.cos(sensor_yaw),math.sin(sensor_yaw)
    for i,value in enumerate(ranges):
        if math.isnan(value) or value<=range_min:continue
        valid=True
        value=min(value,range_max)
        a=angle_min+i*angle_increment
        lx,ly=value*math.cos(a),value*math.sin(a)
        bx,by=sensor_x+c*lx-s*ly,sensor_y+s*lx+c*ly
        if abs(math.atan2(by,bx))<half_angle:
            nearest=min(nearest,math.hypot(bx,by))
    return nearest if valid else None
