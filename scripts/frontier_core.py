#!/usr/bin/env python3
"""Frontiers reachable through known free space, with obstacle clearance."""
import math
import cv2
import numpy as np


def frontiers(grid,resolution,robot_cell,clearance=.4,min_cells=3):
    g=np.asarray(grid,dtype=np.int16)
    if g.ndim!=2 or resolution<=0:raise ValueError('Invalid map')
    free=(g>=0)&(g<25);unknown=g<0;obstacle=g>=25
    distance=cv2.distanceTransform((~obstacle).astype('uint8'),cv2.DIST_L2,5)*resolution
    traversable=free&(distance>=clearance)
    x,y=robot_cell
    if not(0<=y<g.shape[0] and 0<=x<g.shape[1]) or not traversable[y,x]:return []
    count,labels=cv2.connectedComponents(traversable.astype('uint8'),connectivity=4)
    reachable=labels==labels[y,x]
    boundary=reachable & (cv2.dilate(unknown.astype('uint8'),np.ones((3,3),'uint8'))>0)
    n,groups,stats,centroids=cv2.connectedComponentsWithStats(boundary.astype('uint8'),connectivity=8)
    result=[]
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]<min_cells:continue
        ys,xs=np.where(groups==i);cx,cy=centroids[i]
        index=int(np.argmin((xs-cx)**2+(ys-cy)**2));tx,ty=int(xs[index]),int(ys[index])
        # Score compact frontiers by distance and information gain; navigation planner handles actual route.
        score=math.hypot(tx-x,ty-y)*resolution-.01*len(xs)
        result.append(dict(x=tx,y=ty,cells=len(xs),score=score))
    return sorted(result,key=lambda p:p['score'])
