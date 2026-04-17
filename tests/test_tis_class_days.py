from datetime import date, datetime

from agent.api import routine_events


def test_month_start_window_covers_current_month_plus_minus_three_months():
    result = routine_events._month_start_window(date(2026, 4, 18))

    assert result == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
    ]


def test_parse_tis_class_day_payload_groups_dates_by_month():
    payload = [
        {"Y": "2026", "M": "04", "D": "08", "LBMC": "课表"},
        {"Y": "2026", "M": "04", "D": "10", "LBMC": "课表"},
        {"Y": "2026", "M": "05", "D": "01", "LBMC": "课表"},
    ]

    result = routine_events._parse_tis_class_day_payload(payload)

    assert result == {
        (2026, 4): {date(2026, 4, 8), date(2026, 4, 10)},
        (2026, 5): {date(2026, 5, 1)},
    }


def test_tis_item_to_events_filters_dates_when_month_has_explicit_class_days():
    item = {
        "KEY": "xq3_jc2",
        "KSJC": 3,
        "JSJC": 4,
        "SKSJ": "软件工程\n[陶伊达]\n[软件工程-01班-英文]\n[1-2周][智华楼207][3-4节]",
    }
    start = datetime(2026, 2, 16, 0, 0, 0)
    end = datetime(2026, 6, 7, 23, 59, 59)
    class_days_by_month = {
        (2026, 1): {date(2026, 1, 28)},
        (2026, 2): {date(2026, 2, 25)},
        (2026, 3): {date(2026, 3, 4), date(2026, 3, 5)},
    }

    events = routine_events._tis_item_to_events(
        item,
        start,
        end,
        class_days_by_month,
    )

    assert len(events) == 2
    assert [event["time_"] for event in events] == [
        routine_events.local_ymdhms_to_unix_sec(2026, 2, 25, 10, 20, 0),
        routine_events.local_ymdhms_to_unix_sec(2026, 3, 4, 10, 20, 0),
    ]
    assert [event["end_time_"] for event in events] == [
        routine_events.local_ymdhms_to_unix_sec(2026, 2, 25, 12, 10, 0),
        routine_events.local_ymdhms_to_unix_sec(2026, 3, 4, 12, 10, 0),
    ]
