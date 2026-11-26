#!/usr/bin/env python3
"""Atomic map persistence, partitioned by simulation scene or physical robot."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
from datetime import datetime
import numpy as np
from PIL import Image
import yaml
from lab_catalog import LabCatalog,create_catalog


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.json')
    try:
        with os.fdopen(fd,'w') as out:json.dump(data,out,ensure_ascii=False,indent=2);out.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def context(mode,scene,namespace=''):
    return dict(mode=mode,scene=scene if mode=='sim' else '',namespace=namespace.strip('/') if mode=='robot' else '')


def index_path(root,ctx):
    key=hashlib.sha256(json.dumps(ctx,sort_keys=True).encode()).hexdigest()[:16]
    return Path(root)/'results'/'session_maps'/(key+'.json')


def remember(root,catalog,ctx,kind='named'):
    c=LabCatalog(catalog)
    atomic_json(index_path(root,ctx),dict(context=ctx,catalog=str(c.path),kind=kind))


def latest(root,ctx):
    try:
        data=json.loads(index_path(root,ctx).read_text())
        if data['context']!=ctx:return None
        return LabCatalog(data['catalog']).path
    except (OSError,ValueError,KeyError,TypeError):return None


def recovery(root,ctx,cells,resolution,origin,spawn):
    root=Path(root);grid=np.asarray(cells)
    if grid.ndim!=2 or not np.any(grid>=0):raise ValueError('No observed map to save')
    parent=root/'maps/recovery';parent.mkdir(parents=True,exist_ok=True)
    dest=parent/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    with tempfile.TemporaryDirectory(dir=parent,prefix='.pending_') as temp:
        folder=Path(temp)
        image=np.full(grid.shape,205,dtype=np.uint8);image[(grid>=0)&(grid<20)]=254;image[grid>=65]=0
        Image.fromarray(image[::-1]).save(folder/'map.pgm')
        (folder/'map.yaml').write_text(yaml.safe_dump(dict(image='map.pgm',mode='trinary',resolution=float(resolution),origin=list(origin),negate=0,occupied_thresh=.65,free_thresh=.196),sort_keys=False))
        create_catalog(folder/'map.yaml',folder/'destinations.yaml')
        atomic_json(folder/'map_metadata.json',dict(name='Map tự lưu phục hồi',kind='recovery',context=ctx,spawn_initial_pose=spawn,note='Occupancy snapshot, not a serialized SLAM pose graph.'))
        # All internal map references are relative, so renaming preserves the catalog hash.
        os.replace(folder,dest)
    remember(root,dest/'destinations.yaml',ctx,kind='recovery')
    return dest/'destinations.yaml'
