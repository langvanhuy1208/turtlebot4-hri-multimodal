from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from keyboard_control import keyboard_velocity


@pytest.mark.parametrize('keys,expected',[(set(),(0,0)),({'w'},(.1,0)),({'s'},(-.1,0)),({'a'},(0,.35)),({'d'},(0,-.35)),({'up'},(.1,0)),({'left'},(0,.35)),({'w','up'},(.1,0)),({'w','s'},(0,0)),({'a','d'},(0,0)),({'w','a'},(.1,.35)),({'space','w'},(0,0))])
def test_bounded_keyboard_commands(keys,expected):
    assert keyboard_velocity(keys)==expected


def test_disabled_never_moves():
    assert keyboard_velocity({'w','a'},False)==(0,0)
