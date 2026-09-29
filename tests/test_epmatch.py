# -*- coding: utf-8 -*-
"""season/episode parser + exact matcher (resources/lib/epmatch.py)"""
import pytest

from resources.lib.epmatch import parse, matches, wanted, filter_items, query_for


@pytest.mark.parametrize('text, se', [
    ('Show S2E5', (2, 5)), ('Show S02E05', (2, 5)), ('show s2 e5', (2, 5)), ('Show S02.E05', (2, 5)),
    ('Show S2Ep5', (2, 5)), ('Show 2x05', (2, 5)), ('Show - Season 2 Episode 5', (2, 5)),
    ('Season 2, Episode 05 - Show', (2, 5)), ('Show season 2 ep. 5', (2, 5)),
    ('Show Season 2', (2, None)), ('Show S02', (2, None)), ('Show Episode 5', (None, 5)), ('Show Ep 5', (None, 5)),
    ('Show Ep.05', (None, 5)), ('Show E05', (None, 5)),
    # Hebrew
    ('הסדרה עונה 2 פרק 5', (2, 5)), ('הסדרה - עונה 2, פרק 05', (2, 5)), ('הסדרה ע2 פ5', (2, 5)),
    ('הסדרה פרק 5', (None, 5)), ('הסדרה עונה 2', (2, None)),
    # Russian
    ('Кухня 2 сезон 5 серия', (2, 5)), ('Кухня Сезон 2 Серия 5', (2, 5)), ('Кухня - 5 серия', (None, 5)),
    ('Кухня серия 5', (None, 5)), ('Кухня 2 сезон', (2, None)),
    # mixed language
    ('Kitchen / Кухня - S02E05 (HD) פרק מלא', (2, 5)),
    # nothing
    ('Show full movie 2020', (None, None)), ('Best moments compilation', (None, None)), ('', (None, None)),
])
def test_parse_formats(text, se):
    assert parse(text) == se


@pytest.mark.parametrize('title', ['Show S2E15', 'Show S2E50', 'Show S2E25', 'Show S2E105', 'Show Episode 15',
                                   'Show 2x15', 'Show עונה 2 פרק 15', 'Кухня 2 сезон 15 серия'])
def test_episode_5_never_matches_15_50_25_105(title):
    assert not matches((2, 5), title)


@pytest.mark.parametrize('title', ['Show S12E05', 'Show S20E05', 'Show Season 12 Episode 5', 'Show 12x05',
                                   'Show עונה 12 פרק 5', 'Кухня 20 сезон 5 серия'])
def test_season_2_never_matches_12_20(title):
    assert not matches((2, 5), title)


def test_zero_padding_equal():
    assert matches((2, 5), 'Show S02E05') and matches((2, 5), 'Show S2E5') and matches((2, 5), 'Show 02x005')


def test_conflicting_numbers_excluded():
    assert not matches((2, 5), 'Show S01E05')
    assert not matches((2, 5), 'Show S02E06')
    assert not matches((2, 5), 'Show Season 1 Episode 5')


def test_no_numbers_excluded_not_guessed():
    assert not matches((2, 5), 'Show - best scenes')
    assert not matches((2, None), 'Show trailer')
    assert not matches((None, 5), 'Show trailer')


def test_title_without_season_does_not_match_season_episode_search():
    assert not matches((2, 5), 'Show Episode 5')        # season not stated: not an exact match


def test_description_used_only_when_title_silent():
    assert matches((2, 5), 'Show - full episode', 'Season 2 Episode 5 of the show')
    assert not matches((2, 5), 'Show S01E01', 'Season 2 Episode 5 mentioned')   # title states another episode


def test_season_only_and_episode_only():
    assert matches((2, None), 'Show S02E09') and not matches((2, None), 'Show S01E09')
    assert matches((None, 5), 'Show S03E05') and not matches((None, 5), 'Show S03E06')


def test_hebrew_and_mixed():
    assert matches((2, 5), 'הסדרה עונה 2 פרק 5 לצפייה ישירה')
    assert matches((2, 5), 'Kitchen / Кухня S02E05 פרק מלא')
    assert not matches((2, 5), 'הסדרה עונה 1 פרק 5')


def test_multiple_exact_matches_all_kept_in_order():
    items = [{'label': 'A S02E05'}, {'label': 'B S01E05'}, {'label': 'C 2x05'}, {'label': 'D S02E15'},
             {'label': 'E Season 2 Episode 5'}, {'label': 'F no numbers'}]
    assert [i['label'][0] for i in filter_items((2, 5), items)] == ['A', 'C', 'E']


def test_no_exact_matches_gives_empty_not_fallback():
    items = [{'label': 'Show S01E01'}, {'label': 'Show S01E02'}]
    assert filter_items((2, 5), items) == []


def test_not_an_episode_search_keeps_everything():
    items = [{'label': 'x'}, {'label': 'y S01E01'}]
    assert filter_items((None, None), items) == items


def test_wanted_explicit_numbers_win():
    assert wanted('Show', 2, 5) == (2, 5)
    assert wanted('Show Season 2 Episode 5') == (2, 5)
    assert wanted('Show S01E01', 2, 5) == (2, 5)
    assert wanted('Show') == (None, None)


def test_query_for():
    assert query_for('Show', 2, 5) == 'Show S02E05'
    assert query_for('Show', 2) == 'Show Season 2'
    assert query_for('Show') == 'Show'


def test_show_name_required_when_known():
    items = [{'label': 'Кухня 2 сезон 5 серия'}, {'label': 'Metal Family Сезон 2 Серия 5'},
             {'label': 'Trick or Treat [2x05]', 'plot': 'The Office season 2'}, {'label': 'Parks and Recreation S02E05'}]
    assert [i['label'] for i in filter_items((2, 5), items, show='Кухня')] == ['Кухня 2 сезон 5 серия']
    assert [i['label'] for i in filter_items((2, 5), items, show='The Office')] == ['Trick or Treat [2x05]']


def test_show_name_whole_words_only():
    from resources.lib.epmatch import mentions
    assert mentions('Кухня', 'Кухня S02E05')
    assert not mentions('Кухня', 'Кухняшка S02E05')
    assert mentions('The Office', 'the office s2e5')


@pytest.mark.parametrize('title', ['Кухня | Сезон 1 | Серия 1 - 10', 'Show S01E01-E03', 'Show S01E01 - 05',
                                   'הסדרה עונה 1 פרק 1-5', 'Show Episode 1 ~ 4'])
def test_episode_ranges_are_not_exact(title):
    assert not matches((1, 1), title)


@pytest.mark.parametrize('title', ['Show S01E01 - 720p', 'Show S01E01 - 1080p HD', 'Show S01E01 - 4K'])
def test_resolution_after_dash_is_not_a_range(title):
    assert matches((1, 1), title)


def test_query_in_show_language():
    assert query_for('Кухня', 2, 5) == 'Кухня 2 сезон 5 серия'
    assert query_for('הסדרה', 2, 5) == 'הסדרה עונה 2 פרק 5'
    assert query_for('The Office', '2', '5') == 'The Office S02E05'
