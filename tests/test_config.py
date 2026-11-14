from config import DEFAULT_PREFS, MARGIN_NAMES, MARGINS, VIEWS, palette


def test_palette_all_views_distinct_and_contrasting():
    seen = set()
    for eink, theme in VIEWS:
        bg, fg = palette({'eink': eink, 'theme': theme})
        assert bg != fg
        assert abs(sum(bg[:3]) - sum(fg[:3])) > 1.5      # достатній контраст
        seen.add((bg, fg))
    assert len(seen) == len(VIEWS)


def test_palette_dark_is_darker_than_light():
    for eink in (True, False):
        dark_bg = palette({'eink': eink, 'theme': 'dark'})[0]
        light_bg = palette({'eink': eink, 'theme': 'light'})[0]
        assert sum(dark_bg[:3]) < sum(light_bg[:3])


def test_defaults_are_consistent():
    assert len(MARGINS) == len(MARGIN_NAMES)
    assert 0 <= DEFAULT_PREFS['margin'] < len(MARGINS)
    assert (DEFAULT_PREFS['eink'], DEFAULT_PREFS['theme']) in VIEWS
