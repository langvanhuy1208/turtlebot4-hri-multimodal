#!/usr/bin/env python3
import argparse,json,sys,time
from pathlib import Path
import numpy as np
import rclpy
from std_msgs.msg import String
from geometry_msgs.msg import PointStamped
from rclpy.qos import QoSProfile,DurabilityPolicy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lab_catalog import LabCatalog
import session_storage as storage


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['save','restore']);a=p.parse_args()
    rclpy.init();n=rclpy.create_node('persistence_scenario');v=n.create_publisher(String,'/hri/voice',10);d=n.create_publisher(String,'/hri/decision',10);point=n.create_publisher(PointStamped,'/clicked_point',10)
    states=[];live=[]
    n.create_subscription(String,'/hri/status',lambda m:states.append(json.loads(m.data)),50)
    n.create_subscription(String,'/hri/catalog',lambda m:live.append(json.loads(m.data)),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    def wait(f,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.05)
            if f():return
        raise TimeoutError(str(states[-6:]))
    def command(text,state):
        start=len(states);v.publish(String(data=text));wait(lambda:any(s['state']==state for s in states[start:]));return start
    checks=[];report={};error=None
    try:
        if a.phase=='save':
            ctx=storage.context('sim','lab')
            wait(lambda:storage.latest(ROOT,ctx) is not None and live and live[-1]['mapping_session'],200)
            auto=storage.latest(ROOT,ctx);meta=json.loads((auto.parent/'map_metadata.json').read_text())
            assert meta['kind']=='recovery',meta
            checks.append('Actual autonomous exploration completion writes a valid recovery map without confirmation')
            report['recovery_catalog']=str(auto)
            command('Lưu bản đồ kiểm thử lưu lại '+time.strftime('%Y%m%d %H%M%S'),'awaiting_save_confirmation')
            start=command('Xác nhận','saved')
            path=Path(next(s['path'] for s in states[start:] if s['state']=='saved' and s.get('path')))/'destinations.yaml'
            wait(lambda:live and not live[-1]['mapping_session'] and live[-1].get('ready_to_save'),100)
            c=LabCatalog(path);pixels=np.argwhere(c.map.free & (c.map.clearance>.6));assert len(pixels)>1
            for idx,name in [(len(pixels)//3,'cần xóa'),(len(pixels)*2//3,'cần giữ')]:
                y,x=pixels[idx];wx,wy=c.map.pixel_to_world(int(x),int(y))
                m=PointStamped();m.header.frame_id='map';m.point.x=float(wx);m.point.y=float(wy);start=len(states);point.publish(m)
                wait(lambda:any(s['state']=='point_selected' for s in states[start:]))
                d.publish(String(data=json.dumps(dict(action='prepare_selected_place',name=name))))
                wait(lambda:any(s['state']=='awaiting_save_confirmation' for s in states[start:]));command('Xác nhận','saved')
            command('Xóa địa điểm cần xóa','awaiting_save_confirmation');assert 'can_xoa' in LabCatalog(path).regions
            command('Xác nhận','saved')
            assert set(LabCatalog(path).regions)=={'can_giu'}
            checks.append('Delete request preserves location until confirmation, then removes it from disk and live catalog')
            assert storage.latest(ROOT,ctx)==path.resolve()
            report['named_catalog']=str(path)
        else:
            previous=json.loads((ROOT/'results/persistence_save_results.json').read_text());path=Path(previous['results']['named_catalog'])
            wait(lambda:live and not live[-1]['mapping_session'] and live[-1].get('ready_to_save'),120)
            assert [r['id'] for r in live[-1]['places']]==['can_giu'],live[-1]
            assert 'slam_toolbox' not in n.get_node_names()
            folder=Path((ROOT/'results/latest_project_session.txt').read_text().strip());session=json.loads((folder/'session_report.json').read_text())
            assert session['catalog']==str(path)
            assert any(p['state']=='session_restoring' for p in session['phases'])
            assert not any(p['state']=='session_mapping' for p in session['phases'])
            checks.append('Default startup restores the last map and retained place without running SLAM')
            checks.append('Deleted place stays deleted after closing and reopening')
            command('Xóa địa điểm cần giữ','awaiting_save_confirmation');command('Xác nhận','saved')
            wait(lambda:live[-1]['places']==[])
            assert LabCatalog(path).regions=={}
            checks.append('Deleting final place empties the live list and persisted catalog')
            report['catalog']=str(path)
    except Exception as e:error=str(e);raise
    finally:
        (ROOT/'results'/('persistence_'+a.phase+'_results.json')).write_text(json.dumps(dict(passed=error is None,error=error,checks=checks,results=report),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
