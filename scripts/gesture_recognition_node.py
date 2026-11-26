#!/usr/bin/env python3
"""OpenCV webcam + MediaPipe Tasks Gesture Recognizer, one operator hand."""
import json
import os
import time
from pathlib import Path

import cv2
import mediapipe as mp
import rclpy
from rclpy.node import Node
from std_msgs.msg import String,Bool

from gesture_core import GestureFilter, GESTURES
from finger_count import classify_hand


class GestureRecognitionNode(Node):
    def __init__(self):
        super().__init__('gesture_recognition_node')
        for key, value in {'model_path': '', 'camera_index': 0,
                           'confidence_threshold': 0.65, 'hold_seconds': 0.35,
                           'hri_mode': False}.items():
            self.declare_parameter(key, value)
        p = lambda name: self.get_parameter(name).value
        model = Path(p('model_path')).expanduser()
        if not model.is_file():
            raise FileNotFoundError('Missing .task model; run scripts/download_gesture_model.py')
        self.threshold = p('confidence_threshold')
        if not 0 < self.threshold <= 1 or not 0 < p('hold_seconds') < 0.7:
            raise ValueError('confidence must be in (0,1]; hold_seconds in (0,0.7)')
        self.filter = GestureFilter(p('hold_seconds'))
        self.publisher = self.create_publisher(String, '/detected_gesture', 1)
        self.robot_status = 'Waiting for robot_behavior_node'
        self.hri_mode = p('hri_mode')
        self.create_subscription(String, '/hri/status' if self.hri_mode else '/robot_behavior/status', self.on_status, 10)
        options = mp.tasks.vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6)
        self.recognizer = mp.tasks.vision.GestureRecognizer.create_from_options(options)
        self.camera = cv2.VideoCapture(p('camera_index'), cv2.CAP_V4L2)
        if not self.camera.isOpened():
            self.recognizer.close()
            self.camera.release()
            raise RuntimeError('Cannot open webcam; check camera_index and /dev/video*')
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.enabled=True
        self.camera_index=p('camera_index')
        self.create_subscription(Bool,'/hri/camera_enabled',self.set_enabled,10)
        if os.environ.get('TB4_AUTO_CAMERA','1')!='1':self.set_enabled(Bool(data=False))
        self.timestamp = -1
        self.create_timer(1.0 / 20.0, self.on_frame)

    def on_status(self, msg):
        try:
            s = json.loads(msg.data)
            self.robot_status = (s['state'] + ' | ' + ', '.join(s.get('route', [])) if self.hri_mode
                                 else f"{s['state']} | {s['selected'] or '-'} | {s['reason']}")
        except (ValueError, KeyError, TypeError):
            self.robot_status = 'Invalid status'

    def set_enabled(self,msg):
        if msg.data==self.enabled:return
        self.enabled=msg.data
        self.publisher.publish(String(data='TRANSITION'))
        if not self.enabled:
            self.camera.release();cv2.destroyAllWindows()
        else:
            self.camera.open(self.camera_index,cv2.CAP_V4L2)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,640);self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT,480)

    def on_frame(self):
        if not self.enabled:return
        ok, frame = self.camera.read()
        if not ok:
            self.publisher.publish(String(data='NONE'))
            self.filter.update('NONE', 0.0, time.monotonic())
            return
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        now = time.monotonic()
        self.timestamp = max(self.timestamp + 1, int(now * 1000))
        result = self.recognizer.recognize_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self.timestamp)
        raw, score, center = 'NONE', 0.0, 0.0
        # Two hands are ambiguous: refuse control instead of switching operators.
        if len(result.hand_landmarks) == 1:
            if result.gestures and result.gestures[0]:
                category = result.gestures[0][0]
                score = float(category.score)
                if category.category_name in GESTURES and score >= self.threshold:
                    raw = category.category_name
            landmarks = result.hand_landmarks[0]
            if self.hri_mode:
                world_landmarks=getattr(result,'hand_world_landmarks',[])
                geometry=world_landmarks[0] if world_landmarks else landmarks
                try:raw=classify_hand(geometry,raw)
                except ValueError:raw='NONE'
            center = sum(landmarks[i].x for i in (0, 5, 9, 13, 17)) / 5
            for point in landmarks:
                cv2.circle(frame, (int(point.x * frame.shape[1]),
                                   int(point.y * frame.shape[0])), 3, (0, 230, 255), -1)
        label = self.filter.update(raw, center, now)
        if len(result.hand_landmarks)>1:label='AMBIGUOUS'
        self.publisher.publish(String(data=label))
        instructions = ('1 / 2 / 3 fingers: desk 1 / 2 / 3 | Thumb: confirm saving'
                        if self.hri_mode else 'Select: wave / 1 finger / V; confirm: thumb up')
        method='finger landmarks + model' if self.hri_mode else f'model confidence {score:.2f}'
        lines = [f'Gesture: {raw} | {method}', f'Published: {label}',
                 self.robot_status, instructions,
                 'STOP: palm/fist | Clear hand between commands | Thumb NEVER selects a desk']
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (10, 25 + i * 24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.46, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.imshow('TurtleBot 4 - Camera HRI', frame)
        # Window events only: no keyboard controls.
        cv2.waitKey(1)
        if cv2.getWindowProperty('TurtleBot 4 - Camera HRI', cv2.WND_PROP_VISIBLE) < 1:
            self.publisher.publish(String(data='NONE'))
            raise SystemExit

    def close(self):
        if rclpy.ok():
            self.publisher.publish(String(data='NONE'))
        self.camera.release()
        self.recognizer.close()
        cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = GestureRecognitionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
