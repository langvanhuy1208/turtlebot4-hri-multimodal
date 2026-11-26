import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from session_storage import context,recovery,latest,remember,index_path
from lab_catalog import LabCatalog,add_destination


def make_map(root,ctx):
    grid=np.zeros((70,80),dtype=np.int16);grid[[0,-1],:]=100;grid[:,[0,-1]]=100;grid[5:10,5:10]=-1
    return recovery(root,ctx,grid,.05,(0,0,0),dict(x=1.,y=1.,yaw=0.))


def test_recovery_valid_after_atomic_directory_rename(tmp_path):
    ctx=context('sim','maze');file=make_map(tmp_path,ctx)
    c=LabCatalog(file)
    assert c.regions=={} and c.map.width==80
    assert latest(tmp_path,ctx)==file
    assert json.loads((file.parent/'map_metadata.json').read_text())['kind']=='recovery'
    assert not list((tmp_path/'maps/recovery').glob('.pending_*'))


def test_scene_and_robot_contexts_do_not_mix(tmp_path):
    ctx=context('sim','maze');make_map(tmp_path,ctx)
    assert latest(tmp_path,context('sim','lab')) is None
    assert latest(tmp_path,context('robot','maze','robot3')) is None
    assert context('robot','lab','/robot3')==context('robot','maze','robot3')


def test_deleted_place_stays_deleted_on_reload(tmp_path):
    ctx=context('sim','maze');file=make_map(tmp_path,ctx)
    add_destination(file,'quay','Quầy',['tiếp tân'],1,1,0)
    remember(tmp_path,file,ctx)
    from lab_catalog import write_yaml
    data=LabCatalog(file).data;data['regions']=[];write_yaml(file,data)
    assert LabCatalog(latest(tmp_path,ctx)).regions=={}


def test_changed_or_missing_maps_are_not_restored(tmp_path):
    ctx=context('sim','maze');file=make_map(tmp_path,ctx)
    (file.parent/'map.pgm').write_bytes(b'broken image')
    assert latest(tmp_path,ctx) is None
