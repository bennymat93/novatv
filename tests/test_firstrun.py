# -*- coding: utf-8 -*-
"""first-run answers survive a restart: kept in firstrun.json, not only in Kodi's add-on settings"""
from resources.lib import common, profiles


def test_flag_persists_in_file(tmp_path, monkeypatch):
    monkeypatch.setattr(common, '_path', lambda n: str(tmp_path / n))
    assert not common.flag('device_profile')
    common.flag('device_profile', 'tv')
    common.flag('brand_offer', 'done')
    # a "restart": Kodi's settings forgot everything, the file did not
    monkeypatch.setattr(common.ADDON, 'getSetting', lambda k: '', raising=False)
    assert common.flag('device_profile') == 'tv' and common.flag('brand_offer') == 'done'
    assert profiles.current() == 'tv'
