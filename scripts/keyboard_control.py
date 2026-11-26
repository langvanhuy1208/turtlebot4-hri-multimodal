#!/usr/bin/env python3
"""Bounded keyboard velocities; opposite directions cancel rather than win."""


def keyboard_velocity(keys,enabled=True):
    if not enabled or 'space' in keys:return 0.0,0.0
    forward=bool({'w','up'} & keys);backward=bool({'s','down'} & keys)
    left=bool({'a','left'} & keys);right=bool({'d','right'} & keys)
    return .10*(int(forward)-int(backward)),.35*(int(left)-int(right))
