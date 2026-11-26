#!/usr/bin/env python3
"""Confirmation transaction logic, independent of ROS and hardware."""
import math
import uuid


class ConfirmationGate:
    def __init__(self, timeout=20.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('confirmation_timeout_sec must be positive')
        self.timeout = timeout
        self.pending = None
        self.neutral_since = None
        self.gesture_armed = False

    def request(self, text, route, now):
        if self.pending:
            raise ValueError('Đang chờ xác nhận; hãy xác nhận hoặc hủy lệnh trước')
        self.pending = dict(request_id=uuid.uuid4().hex, text=text,
                            route=list(route), deadline=now + self.timeout)
        self.neutral_since, self.gesture_armed = None, False
        return dict(self.pending)

    def expire(self, now):
        if self.pending and now >= self.pending['deadline']:
            self.clear()
            return True
        return False

    def clear(self):
        self.pending = None
        self.neutral_since, self.gesture_armed = None, False

    def confirm(self, request_id, now):
        if self.expire(now) or not self.pending or request_id != self.pending['request_id']:
            return None
        command = self.pending['text']
        self.clear()
        return command

    def gesture(self, label, now):
        if self.expire(now) or not self.pending:
            return None
        # A thumb held before the request never confirms it. Require visible
        # neutral samples AFTER the request, then a fresh stable thumb pose.
        if label == 'NONE':
            if self.neutral_since is None:
                self.neutral_since = now
            if now - self.neutral_since >= 0.35:
                self.gesture_armed = True
        else:
            self.neutral_since = None
        if label == 'Thumb_Up' and self.gesture_armed:
            return self.confirm(self.pending['request_id'], now)
        return None


class ButtonEdges:
    """Require an observed release before treating any physical press as new."""
    def __init__(self):
        self.previous = None

    def update(self, values):
        values = tuple(bool(v) for v in values)
        if self.previous is None or len(values) != len(self.previous):
            self.previous = values
            return []
        rising = [i for i, value in enumerate(values) if value and not self.previous[i]]
        self.previous = values
        return rising
