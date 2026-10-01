# -*- coding: utf-8 -*-
"""binary add-on platform check (root cause of YouTube not playing on iPhone / iPad)"""
from resources.lib import binfix


def test_windows_build_does_not_fit_apple_or_linux():
    for plat in ('ios', 'tvos', 'osx', 'linux', 'android'):
        assert not binfix.platform_fits('windows-x86_64', plat, 'aarch64')


def test_right_builds_fit():
    assert binfix.platform_fits('windows-x86_64', 'windows', 'x86_64')
    assert binfix.platform_fits('ios-aarch64', 'ios', 'aarch64')
    assert binfix.platform_fits('tvos-aarch64', 'tvos')
    assert binfix.platform_fits('android-aarch64', 'android', 'aarch64')
    assert not binfix.platform_fits('android-aarch64', 'android', 'armv7')
    assert binfix.platform_fits('all', 'ios')
    assert binfix.platform_fits(None, 'linux')
