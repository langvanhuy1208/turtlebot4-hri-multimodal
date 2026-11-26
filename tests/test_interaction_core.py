import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from interaction_core import Interaction


def resolve(text):
    from semantic_map import normalize
    text=normalize(text)
    for n in range(1,4):
        if text.endswith(('ban '+str(n),'ban so '+str(n))):return ['ban_'+str(n)]
    raise ValueError('unknown')


def test_arrival_needs_no_dialogue_receipt():
    d=Interaction(resolve);assert d.input('Đi đến bàn 1','voice',0)[0]['state']=='collecting'
    assert d.flush(.8)==[dict(state='navigate',route=['ban_1'])]
    assert d.pending is None


def test_conflict_requires_explicit_choice():
    d=Interaction(resolve);d.input('Đi đến bàn 1','voice',0)
    assert d.input('Đi đến bàn 2','gesture',.4)[0]['state']=='conflict'
    assert d.flush(5)==[]
    assert d.input('bàn 3','voice',6)[0]['state']=='clarify'
    assert d.input('bàn 2','voice',7)==[dict(state='navigate',route=['ban_2'])]


def test_merge_dispatches_once_and_stop_clears_window():
    d=Interaction(resolve);d.input('Đi đến bàn 1','voice',0)
    assert d.input('Đi đến bàn 1','gesture',.1)[0]['state']=='merged'
    assert len(d.flush(1))==1 and d.flush(2)==[]
    d.input('Đi đến bàn 2','voice',3)
    assert d.input('Dừng lại','voice',3.2)==[dict(state='stop')]
    assert d.flush(4)==[]


def test_save_uuid_expiry_and_no_replay():
    d=Interaction(resolve)
    assert d.confirm(None,0)[0]['state']=='decision_rejected'
    p=d.prepare('save_place','quầy',1,pose={'x':1})
    assert d.confirm('wrong',2)[0]['state']=='decision_rejected'
    assert d.confirm(p['request_id'],3)[0]['state']=='commit_save'
    assert d.confirm(p['request_id'],4)[0]['state']=='decision_rejected'
    d.prepare('save_map','lab',5)
    assert d.confirm(None,40)[0]['state']=='decision_rejected'


def test_unknown_command_clarifies_instead_of_learning():
    d=Interaction(resolve)
    assert d.input('Đi đến sao hỏa','voice',0)[0]['state']=='clarify'
    assert d.pending is None
    assert d.input('bàn 2','voice',1)[0]['state']=='collecting'
    assert d.input('Lưu địa điểm tiếp tân','voice',2)[0]['operation']=='save_place'


def test_alias_learning_is_explicit_not_automatic():
    d=Interaction(resolve)
    e=d.input('Gọi bàn 1 là quầy tiếp tân','voice',0)[0]
    assert e['state']=='prepare_save' and e['operation']=='alias_place'
    assert e['target']=='ban_1' and d.pending is None


def test_selected_point_voice_intent_requires_explicit_save():
    d=Interaction(resolve)
    e=d.input('Lưu điểm đã chọn quầy lễ tân','voice',0)[0]
    assert e['state']=='prepare_save' and e['operation']=='save_selected_place'
    assert e['name']=='quầy lễ tân' and d.pending is None
