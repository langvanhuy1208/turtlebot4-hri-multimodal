#!/usr/bin/env python3
"""Teach/update/alias a place using live TF after reloading a user-saved map."""
import json
from pathlib import Path
import time
import rclpy
from std_msgs.msg import String


def main():
    root=Path(__file__).resolve().parents[1];folder=Path((root/'results/latest_user_map.txt').read_text().strip())
    rclpy.init();n=rclpy.create_node('place_learning_scenario')
    voice=n.create_publisher(String,'/hri/voice',10);gesture=n.create_publisher(String,'/detected_gesture',10)
    states=[];n.create_subscription(String,'/hri/status',lambda m:states.append(json.loads(m.data)),50)
    def spin(t):
        end=time.monotonic()+t
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.04)
    def wait(p,timeout=25):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.04)
            if p():return
        raise TimeoutError(str(states[-5:]))
    def command(text,state,timeout=25):
        start=len(states);voice.publish(String(data=text))
        wait(lambda:any(s['state']==state for s in states[start:]),timeout)
        return start
    error=None;checks=[]
    try:
        wait(lambda:voice.get_subscription_count()>0);spin(5)
        command('Lưu địa điểm quầy thử nghiệm','awaiting_save_confirmation')
        command('Xác nhận','saved');checks.append('Teach current live TF pose; voice confirms save')
        command('Cập nhật địa điểm quầy thử nghiệm','awaiting_save_confirmation')
        for _ in range(10):gesture.publish(String(data='NONE'));spin(.05)
        gesture.publish(String(data='Thumb_Up'));wait(lambda:states[-1]['state']=='saved')
        checks.append('Update stored pose; fresh thumb confirms save')
        command('Gọi quầy thử nghiệm là bàn kiểm tra','awaiting_save_confirmation')
        command('Xác nhận','saved');checks.append('Learn alternate spoken name with explicit confirmation')
        start=command('Đi đến bàn kiểm tra','navigating')
        wait(lambda:any(s['state']=='completed' for s in states[start:]),60)
        assert any(s['state']=='arrived' for s in states[start:])
        assert not any(s['state']=='awaiting_arrival_confirmation' for s in states[start:])
        checks.append('New alias resolves persisted place and Nav2 automatically completes arrival')
        import sys
        sys.path.insert(0,str(root/'scripts'))
        from lab_catalog import LabCatalog
        catalog=LabCatalog(folder/'destinations.yaml')
        assert catalog.parse('Đi đến bàn kiểm tra')==catalog.parse('Đi đến quầy thử nghiệm')
        checks.append('Catalog reload preserves learned names and map fingerprint')
    except Exception as e:error=str(e);raise
    finally:
        voice.publish(String(data='Dừng lại'));spin(.2)
        (root/'results/place_learning_gazebo_results.json').write_text(json.dumps(dict(passed=error is None,error=error,checks=checks,events=states,catalog=str(folder/'destinations.yaml')),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
