#!/usr/bin/env python3
"""Real DDS/action checks for direct commands and post-arrival buttons; fake Nav2."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer,CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String
from lab_catalog import create_catalog,add_destination
from lab_hri_node import LabHRI
from semantic_map import RegionCatalog


def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='tb4_arrival_') as tmp:
        catalog=Path(tmp)/'destinations.yaml';reference=RegionCatalog(root/'maps/bai7/regions.yaml')
        create_catalog(reference.map.path,catalog)
        for i,r in enumerate(reference.regions.values(),1):
            add_destination(catalog,f'ban_{i}',f'Bàn số {i}',[f'bàn {i}'],**r['goal'])
        rclpy.init(args=['--ros-args','-p',f'regions_file:={catalog}','-p','require_localization:=false','-p','require_stationary_save:=false','-p','enable_joy_buttons:=true',
            '-r','navigate_to_pose:=/arrival_test/navigate_to_pose',
            '-r','/voice_command:=/arrival_test/voice','-r','/voice_nav/status:=/arrival_test/status',
            '-r','/hri/decision:=/arrival_test/decision','-r','/detected_gesture:=/arrival_test/gesture',
            '-r','/semantic_regions:=/arrival_test/regions','-r','/voice_nav/route:=/arrival_test/route',
            '-r','/joy:=/arrival_test/joy'])
        controller=LabHRI();probe=Node('arrival_test_probe')
        states,goals,results=[],[],[];mode={'value':'success'}
        point_pub=probe.create_publisher(PointStamped,'/clicked_point',10)
        listening_pub=probe.create_publisher(String,'/hri/listening_state',10)
        safety_pub=probe.create_publisher(String,'/hri/safety',10)
        voice=probe.create_publisher(String,'/voice_command',10)
        buttons=probe.create_publisher(String,'/hri/decision',10)
        gesture=probe.create_publisher(String,'/detected_gesture',1)
        joy=probe.create_publisher(Joy,'/joy',1)
        probe.create_subscription(String,'/voice_nav/status',lambda m:states.append(json.loads(m.data)),100)
        def execute(handle):
            goals.append(handle.request.pose)
            until=time.monotonic()+(2 if mode['value']=='slow' else .12)
            while time.monotonic()<until:
                if handle.is_cancel_requested:
                    handle.canceled();return NavigateToPose.Result()
                time.sleep(.01)
            if mode['value']=='abort':handle.abort()
            else:handle.succeed()
            return NavigateToPose.Result()
        server=ActionServer(probe,NavigateToPose,'navigate_to_pose',execute,
            callback_group=ReentrantCallbackGroup(),cancel_callback=lambda _:CancelResponse.ACCEPT)
        executor=MultiThreadedExecutor(num_threads=4);executor.add_node(controller);executor.add_node(probe)
        thread=threading.Thread(target=executor.spin,daemon=True);thread.start()
        def wait(predicate,timeout=7):
            until=time.monotonic()+timeout
            while time.monotonic()<until:
                if predicate():return
                time.sleep(.02)
            raise AssertionError(str(states[-8:]))
        def has(state,start):return any(s['state']==state for s in states[start:])
        def receipt(start):
            wait(lambda:has('awaiting_arrival_confirmation',start))
            return next(s['request_id'] for s in states[start:] if s['state']=='awaiting_arrival_confirmation')
        def ack(token):buttons.publish(String(data=json.dumps(dict(action='confirm_arrival',request_id=token))))
        def fresh_gesture(label):
            for _ in range(10):gesture.publish(String(data='NONE'));time.sleep(.05)
            gesture.publish(String(data=label))
        def passed(name):results.append(name);print('PASS:',name,flush=True)
        try:
            wait(lambda:voice.get_subscription_count() and buttons.get_subscription_count()
                 and gesture.get_subscription_count() and controller.client.server_is_ready())
            start=len(states);ack('early');wait(lambda:has('decision_rejected',start));assert not goals
            passed('Arrival confirmation rejected; save confirmation only')
            before=len(goals);fresh_gesture('Thumb_Up');time.sleep(.2)
            assert len(goals)==before
            passed('Thumb never navigates')
            for label,number in [('Pointing_Up',1),('Victory',2),('Three_Fingers',3)]:
                start=len(states);before=len(goals);fresh_gesture(label)
                wait(lambda:has('completed',start));assert len(goals)==before+1 and not controller.busy
                assert not has('awaiting_arrival_confirmation',start)
                for _ in range(5):gesture.publish(String(data=label));time.sleep(.03)
                assert len(goals)==before+1
                passed(f'{label}: direct travel and automatic completion, held gesture ignored')
            start=len(states);before=len(goals)
            voice.publish(String(data='Đi đến bàn số 1'));time.sleep(.15);fresh_gesture('Victory')
            wait(lambda:has('conflict',start));time.sleep(1);assert len(goals)==before
            voice.publish(String(data='bàn số 2'));wait(lambda:has('completed',start));assert len(goals)==before+1
            passed('Conflicting voice/gesture waits for explicit choice')
            start=len(states);before=len(goals)
            voice.publish(String(data='Đi đến bàn số 1'));time.sleep(.15);fresh_gesture('Pointing_Up')
            wait(lambda:has('completed',start));assert len(goals)==before+1
            passed('Matching modalities send one goal')
            start=len(states);before=len(goals)
            listening_pub.publish(String(data='transcribing'));time.sleep(.1);fresh_gesture('Pointing_Up')
            time.sleep(1.2);assert len(goals)==before
            voice.publish(String(data='Đi đến bàn số 2'));wait(lambda:has('conflict',start))
            listening_pub.publish(String(data='listening'));voice.publish(String(data='bàn số 2'))
            wait(lambda:has('completed',start));assert len(goals)==before+1
            passed('Gesture waits for in-progress ASR; delayed conflicting voice still asks before movement')
            mode['value']='slow';start=len(states)
            voice.publish(String(data='Đi đến bàn số 1'));wait(lambda:has('navigating',start))
            gesture.publish(String(data='Open_Palm'));wait(lambda:has('cancelled',start));assert not controller.busy
            passed('Stop cancels active action')
            mode['value']='slow';start=len(states);before=len(goals)
            voice.publish(String(data='Đi đến bàn số 1'));wait(lambda:has('navigating',start))
            safety_pub.publish(String(data=json.dumps(dict(state='person_stop'))))
            wait(lambda:has('paused_safety',start));assert controller.busy and controller.pause_waiting
            time.sleep(2.5);assert len(goals)==before+1 and not has('completed',start)
            safety_pub.publish(String(data=json.dumps(dict(state='command_stale'))))
            wait(lambda:has('resuming',start));wait(lambda:has('completed',start));assert len(goals)==before+2
            passed('Long safety wait cancels old action before resuming same destination')
            mode['value']='slow';start=len(states)
            voice.publish(String(data='Đi đến bàn số 1'));wait(lambda:has('navigating',start))
            safety_pub.publish(String(data=json.dumps(dict(state='person_stop'))));wait(lambda:has('paused_safety',start))
            voice.publish(String(data='Dừng lại'));wait(lambda:has('cancelled',start))
            before=len(goals);safety_pub.publish(String(data=json.dumps(dict(state='clear'))));time.sleep(.5)
            assert len(goals)==before and not controller.busy
            passed('User stop while safety-paused prevents automatic resume')
            mode['value']='success';start=len(states)
            voice.publish(String(data='Đi đến sao hỏa'));wait(lambda:has('clarify',start))
            voice.publish(String(data='bàn số 2'));wait(lambda:has('completed',start))
            passed('Unknown destination asks again; answer dispatches')
            start=len(states);position=controller.catalog.regions['ban_2']['goal']
            point=PointStamped();point.header.frame_id='map';point.point.x=position['x'];point.point.y=position['y']
            point_pub.publish(point);wait(lambda:has('point_selected',start))
            buttons.publish(String(data=json.dumps(dict(action='prepare_selected_place',name='điểm tự chọn'))))
            wait(lambda:has('awaiting_save_confirmation',start));assert 'diem_tu_chon' not in controller.catalog.regions
            voice.publish(String(data='Xác nhận'));wait(lambda:has('saved',start))
            stored=controller.catalog.regions['diem_tu_chon']['goal']
            assert stored['x']==position['x'] and stored['y']==position['y']
            passed('Arbitrary RViz point is persisted only after naming and confirmation')
            start=len(states);point.point.x=-1000.;point_pub.publish(point)
            wait(lambda:has('save_failed',start));assert controller.selected_pose is None
            passed('Invalid/occupied map point clears selection and cannot be saved')
            mode['value']='abort';start=len(states)
            voice.publish(String(data='Đi đến bàn số 1'));wait(lambda:has('failed',start))
            assert not controller.busy and not has('arrived',start) and not has('completed',start)
            passed('Failed navigation reports failure and never announces arrival')
            mode['value']='success'
            # Deletion exercises a real atomic catalog transaction without requiring fake TF poses.
            start=len(states);voice.publish(String(data='Xóa địa điểm bàn số 3'))
            wait(lambda:has('awaiting_save_confirmation',start));assert 'ban_3' in controller.catalog.regions
            token=controller.dialogue.pending['request_id']
            buttons.publish(String(data=json.dumps(dict(action='confirm_save',request_id='wrong'))))
            wait(lambda:has('decision_rejected',start));assert 'ban_3' in controller.catalog.regions
            fresh_gesture('Thumb_Up');wait(lambda:has('saved',start));assert 'ban_3' not in controller.catalog.regions
            passed('Save transaction rejects stale ID and commits exactly once with fresh thumb')
            start=len(states);voice.publish(String(data='Xóa địa điểm bàn số 2'))
            wait(lambda:has('awaiting_save_confirmation',start));voice.publish(String(data='Xác nhận'))
            wait(lambda:has('saved',start));assert 'ban_2' not in controller.catalog.regions
            passed('Voice confirmation commits pending save')
            report=dict(source='ROS DDS/actions with fake Nav2, no robot movement',passed=True,checks=results)
            (root/'results/interaction_ros_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        finally:
            executor.shutdown();thread.join(timeout=3);server.destroy()
            controller.destroy_node();probe.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
