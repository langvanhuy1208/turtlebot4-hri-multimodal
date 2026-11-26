#!/usr/bin/env python3
"""Short spoken feedback on state changes; serial queue bounded to two messages."""
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String,Bool


class Feedback(Node):
    def __init__(self):
        super().__init__('hri_feedback');self.work=queue.Queue(maxsize=2);self.last={}
        self.active=self.create_publisher(Bool,'/hri/speech_active',10)
        self.create_subscription(String,'/hri/status',self.status,20)
        self.create_subscription(String,'/hri/safety',self.safety,20)
        threading.Thread(target=self.worker,daemon=True).start()

    def say(self,text):
        now=time.monotonic()
        if not text or now-self.last.get(text,-1e9)<10:return
        self.last[text]=now
        if len(self.last)>100:self.last={text:now}
        if self.work.full():
            try:self.work.get_nowait()
            except queue.Empty:pass
        self.work.put_nowait(text)

    def status(self,msg):
        try:
            d=json.loads(msg.data);state=d['state']
            if state in ('arrived','clarify','conflict','saved','awaiting_save_confirmation','save_expired','waiting_safety','resuming'):
                self.say(d.get('prompt'))
            elif state=='navigating':self.say('Đang đi đến '+d.get('destination',d.get('region','')))
            elif state in ('save_failed','failed','rejected'):self.say(d.get('reason'))
        except (ValueError,KeyError):pass

    def safety(self,msg):
        try:
            d=json.loads(msg.data);self.say(dict(person_warning='Có người ở gần. Robot giảm tốc.',person_stop='Có người trong vùng an toàn. Robot dừng chờ.',obstacle_stop='Có vật cản quá gần. Robot dừng.',sensor_stale='Chưa đủ dữ liệu cảm biến. Robot chờ.').get(d['state']))
        except (ValueError,KeyError):pass

    def worker(self):
        while rclpy.ok():
            try:text=self.work.get(timeout=.2)
            except queue.Empty:continue
            self.active.publish(Bool(data=True))
            try:subprocess.run(['/usr/bin/python3',str(Path(__file__).with_name('local_speech.py')),text],timeout=25,check=True,capture_output=True)
            except Exception as e:self.get_logger().warning('Speech unavailable: '+str(e))
            finally:self.active.publish(Bool(data=False))


def main():
    rclpy.init();n=Feedback()
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
