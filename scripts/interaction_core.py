#!/usr/bin/env python3
"""Deterministic Vietnamese dialogue and bounded multimodal arbitration."""
import re
import uuid
from semantic_map import normalize


class Interaction:
    def __init__(self, resolve_route, window=.8):
        self.resolve_route = resolve_route
        self.window = window
        self.candidate = None
        self.choices = None
        self.pending = None
        self.context = False

    def event(self, state, **fields):
        return dict(state=state, **fields)

    def input(self, text, source, now):
        raw = text
        original = normalize(text)
        value = re.sub(r'^(?:robot |hay |vui long )+', '', original)
        raw = ' '.join(raw.split()[len(original.split())-len(value.split()):])
        text = value
        if value in ('dung', 'dung lai', 'huy', 'huy dieu huong'):
            self.candidate = self.choices = self.pending = None
            self.context = False
            return [self.event('stop')]
        if value in ('xac nhan', 'dong y'):
            return self.confirm(None, now)
        if self.pending:
            return [self.event('clarify', prompt='Đang chờ xác nhận lưu. Nói xác nhận hoặc hủy.')]
        for phrase, mode in [('tu dong quet', 'auto'), ('quet tu dong', 'auto'), ('dieu khien thu cong', 'manual'), ('dung quet', 'stop')]:
            if value == phrase:
                self.candidate = None
                return [self.event('mapping_mode', mode=mode)]
        for prefix, action in (('luu diem da chon ', 'save_selected_place'), ('luu ban do ', 'save_map'), ('luu map ', 'save_map'),
                               ('luu dia diem ', 'save_place'), ('day dia diem ', 'save_place'),
                               ('cap nhat dia diem ', 'update_place'), ('xoa dia diem ', 'delete_place')):
            if value.startswith(prefix):
                name = ' '.join(raw.split()[len(prefix.split()):]).strip()
                self.candidate = self.choices = None
                self.context = False
                return [self.event('prepare_save', operation=action, name=name)]
        match=re.fullmatch(r'goi (.+) la (.+)',value)
        if match:
            try:
                route=self.resolve_route('Đi đến '+match.group(1))
                if len(route)!=1:raise ValueError('Choose one place')
                raw_alias=re.split(r'\bla\b',normalize(raw),maxsplit=1)[-1].strip()
                self.candidate=self.choices=None
                return [self.event('prepare_save',operation='alias_place',name=raw_alias,target=route[0])]
            except ValueError:
                return [self.event('clarify',prompt='Địa điểm gốc chưa có. Nói gọi tên địa điểm đã lưu là tên mới.')]
        try:
            route = self.resolve_route(text if value.startswith(('di ', 'dieu huong ')) else 'Đi đến '+text)
            if not route:
                raise ValueError('Thiếu địa điểm')
        except ValueError:
            self.context = True
            return [self.event('clarify', prompt='Bạn muốn đến địa điểm nào? Hãy nói lại tên; để dạy vị trí hiện tại, nói lưu địa điểm và tên.')]
        # Bare destination names are valid only as answers to a question.
        if not value.startswith(('di ', 'dieu huong ')) and not self.context and source != 'gesture':
            return [self.event('clarify', prompt='Hãy nói đi đến và tên địa điểm.')]
        if self.choices:
            if route not in self.choices:
                return [self.event('clarify', prompt='Hãy chọn một trong hai địa điểm vừa yêu cầu.', choices=self.choices)]
            self.choices = None
            self.context = False
            return [self.event('navigate', route=route)]
        self.context = False
        if self.candidate:
            old = self.candidate
            if now > old['deadline']:
                # Caller normally flushes via timer; don't lose a late input.
                out = self.flush(now)
                return out+self.input(text, source, now)
            if route != old['route']:
                self.choices = [old['route'], route]
                self.candidate = None
                self.context = True
                return [self.event('conflict', prompt='Hai lệnh khác nhau. Bạn muốn đến địa điểm nào?', choices=self.choices)]
            return [self.event('merged', route=route)]
        self.candidate = dict(route=route, source=source, deadline=now+self.window)
        return [self.event('collecting', route=route)]

    def flush(self, now):
        if self.candidate and now >= self.candidate['deadline']:
            route = self.candidate['route']
            self.candidate = None
            return [self.event('navigate', route=route)]
        return []

    def prepare(self, operation, name, now, **payload):
        self.pending = dict(request_id=uuid.uuid4().hex, operation=operation, name=name,
                            expires=now+30, **payload)
        return self.event('awaiting_save_confirmation', **self.pending,
                          prompt=f"{dict(save_map='Lưu bản đồ',save_place='Lưu địa điểm',update_place='Cập nhật địa điểm',delete_place='Xóa địa điểm',alias_place='Thêm tên gọi').get(operation,operation)} {name}? Giơ ngón cái, nói xác nhận hoặc bấm nút trong 30 giây.")

    def confirm(self, request_id, now):
        p = self.pending
        if not p or now > p['expires'] or (request_id is not None and request_id != p['request_id']):
            if p and now > p['expires']:
                self.pending = None
            return [self.event('decision_rejected', reason='Không có yêu cầu lưu hợp lệ để xác nhận.')]
        self.pending = None
        return [self.event('commit_save', **p)]

    def expire(self, now):
        if self.pending and now > self.pending['expires']:
            self.pending = None
            return [self.event('save_expired', prompt='Hết thời gian xác nhận, chưa lưu thay đổi.')]
        return []
