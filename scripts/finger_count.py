#!/usr/bin/env python3
"""Count extended index/middle/ring/little fingers using 3D joint geometry."""
import math


def point(value):
    return (value.x,value.y,value.z) if hasattr(value,'x') else tuple(value)


def joint_angle(a,b,c):
    u=[x-y for x,y in zip(a,b)];v=[x-y for x,y in zip(c,b)]
    product=math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
    if product<1e-10:return 0.0
    return math.degrees(math.acos(max(-1.0,min(1.0,sum(x*y for x,y in zip(u,v))/product))))


def count_fingers(landmarks):
    if len(landmarks)!=21:raise ValueError('Expected 21 hand landmarks')
    points=[point(p) for p in landmarks]
    if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError('Invalid hand coordinates')
    wrist=points[0];count=0
    for mcp,pip,dip,tip in [(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]:
        if (joint_angle(points[mcp],points[pip],points[dip])>=155
                and joint_angle(points[pip],points[dip],points[tip])>=150
                and math.dist(wrist,points[tip])>1.10*math.dist(wrist,points[pip])):
            count+=1
    return count


def classify_hand(landmarks,model_label):
    count=count_fingers(landmarks)
    # Thumb is never counted as a destination digit. A lone thumb confirms.
    if count==0 and model_label in ('Thumb_Up','Closed_Fist'):return model_label
    if count in (1,2,3):return {1:'Pointing_Up',2:'Victory',3:'Three_Fingers'}[count]
    if count==4 and model_label=='Open_Palm':return 'Open_Palm'
    return 'NONE'
