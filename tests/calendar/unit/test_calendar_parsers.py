from __future__ import annotations

from datetime import date, datetime

import pytest

from agent.api.routine_events import (
    _tis_item_to_events,
    _validate_optional_hex_color,
)


pytestmark = pytest.mark.unit


def test_routine_color_validator_accepts_hex_only():
    assert _validate_optional_hex_color("#abc") == "#abc"
    assert _validate_optional_hex_color("#AABBCCDD") == "#AABBCCDD"
    assert _validate_optional_hex_color(None) is None

    for value in ["red", "123456", "#12", "#GGGGGG", "url(javascript:alert(1))"]:
        with pytest.raises(ValueError):
            _validate_optional_hex_color(value)


@pytest.mark.xfail(
    reason="Known issue: TIS SKSJ periods_text is parsed into detail but not period window.",
    strict=True,
)
def test_tis_schedule_item_parser_uses_class_days_and_period_windows():
    item = {
        "KEY": "xq1",
        "SKSJ": "Software Engineering\n[Dr. Ada]\nignored\n[1-16][Room 101][3-4]",
    }
    events = _tis_item_to_events(
        item,
        datetime(2026, 5, 1),
        datetime(2026, 5, 31, 23, 59, 59),
        {(2026, 5): {date(2026, 5, 4), date(2026, 5, 5)}},
    )

    assert len(events) == 1
    assert events[0]["event_name"] == "Software Engineering"
    assert "Teacher: Dr. Ada" in str(events[0]["detail"])
    assert "Location: Room 101" in str(events[0]["detail"])
    assert int(events[0]["time_"]) < int(events[0]["end_time_"])
