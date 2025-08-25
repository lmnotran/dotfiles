import sys
from pathlib import Path

# Allow imports from the same directory as this test file
sys.path.append(str(Path(__file__).resolve().parent))

from app import insert_vtimezone_after_header, rewrite_ics


def test_insert_vtimezone_after_header():
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:1\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    vtz = "BEGIN:VTIMEZONE\r\nTZID:Europe/Copenhagen\r\nEND:VTIMEZONE"
    result = insert_vtimezone_after_header(ics, vtz)

    # VTIMEZONE should be inserted exactly once
    assert result.count("BEGIN:VTIMEZONE") == 1
    # Ensure it appears after the VCALENDAR properties and before the first component
    assert result.index("BEGIN:VTIMEZONE") > result.index("PRODID")
    assert result.index("BEGIN:VTIMEZONE") < result.index("BEGIN:VEVENT")


def test_rewrite_ics_maps_tzid_and_injects_vtimezone_when_missing():
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "DTSTART;TZID=W. Europe Standard Time:20240401T090000\r\n"
        "DTEND;TZID=W. Europe Standard Time:20240401T100000\r\n"
        "SUMMARY:Test Event\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    fixed = rewrite_ics(ics)

    assert "TZID=Europe/Copenhagen" in fixed
    assert "W. Europe Standard Time" not in fixed
    assert fixed.count("BEGIN:VTIMEZONE") == 1
    assert "TZID:Europe/Copenhagen" in fixed


def test_rewrite_ics_skips_vtimezone_if_present():
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//EN\r\n"
        "BEGIN:VTIMEZONE\r\n"
        "TZID:Europe/Copenhagen\r\n"
        "END:VTIMEZONE\r\n"
        "BEGIN:VEVENT\r\n"
        "DTSTART;TZID=W. Europe Standard Time:20240401T090000\r\n"
        "DTEND;TZID=W. Europe Standard Time:20240401T100000\r\n"
        "SUMMARY:Test Event\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    fixed = rewrite_ics(ics)

    assert fixed.count("BEGIN:VTIMEZONE") == 1
    assert "TZID=Europe/Copenhagen" in fixed
    assert "W. Europe Standard Time" not in fixed
