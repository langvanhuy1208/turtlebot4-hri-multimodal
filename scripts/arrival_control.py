#!/usr/bin/env python3
"""Arrival receipts and one-shot destination gestures, independent of ROS."""
import uuid


class ArrivalReceipt:
    def __init__(self):
        self.pending=None

    def arrive(self, region, remaining):
        if self.pending is not None:
            raise ValueError('Arrival already awaits acknowledgment')
        self.pending=dict(request_id=uuid.uuid4().hex,region=region,remaining=list(remaining))
        return self.pending

    def acknowledge(self, request_id):
        if self.pending is None or request_id!=self.pending['request_id']:
            return False
        self.pending=None
        return True


class DestinationGestures:
    LABELS=('Pointing_Up','Victory','Three_Fingers')

    def __init__(self, destinations):
        if not 1<=len(destinations)<=3 or len(set(destinations))!=len(destinations):
            raise ValueError('Configure 1 to 3 unique gesture destinations')
        self.mapping=dict(zip(self.LABELS,destinations))
        self.armed=False
        self.neutral_since=None
        self.confirmation_event=False

    def receive(self, label, now):
        self.confirmation_event=False
        if label=='NONE':
            if self.neutral_since is None:self.neutral_since=now
            if now-self.neutral_since>=.35:self.armed=True
            return None
        self.neutral_since=None
        if label in ('Open_Palm','Closed_Fist','AMBIGUOUS'):
            self.armed=False
            return None
        if label=='Thumb_Up' and self.armed:
            self.armed=False
            self.confirmation_event=True
            return None
        if label in self.mapping and self.armed:
            self.armed=False
            return self.mapping[label]
        return None
