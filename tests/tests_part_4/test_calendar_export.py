import pytest
from datetime import date, datetime, timedelta, timezone
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.output.calendar_ics_exporter import CalendarIcsExporter

CRLF = "\r\n"

# Creates a sample Course object with configurable properties.
# Default values represent a typical university course.
def _course(cid, name="Algorithms", instructor="Dr. Cohen", evaluation="Exam"):
    return Course(
        course_id=cid,
        course_name=name,
        instructor=instructor,
        evaluation_method=evaluation,
        program_info=[ProgramCourseInfo("83101", 1, "FALL", "Obligatory")],
    )

# Creates a Schedule object from a list of (course, exam_date) tuples.
# This simplifies test setup by avoiding repetitive object construction.
def _schedule(*pairs):
    """pairs: (course, exam_date)"""
    return Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in pairs])

# Returns a fresh CalendarIcsExporter instance for each test.
def _exporter():
    return CalendarIcsExporter()

# Splits the generated ICS content into individual lines using the
# CRLF line separator required by the iCalendar specification.
def _lines(ics_text: str):
    return ics_text.split(CRLF)

# ===========================================================================
# SANITY — happy path structure & content
# ===========================================================================
class TestSanity:
    def test_build_calendar_has_required_vcalendar_wrapper(self):
        cal = _exporter().build_calendar(_schedule((_course("10001"), date(2026, 2, 3))))
        lines = _lines(cal)
        assert lines[0] == "BEGIN:VCALENDAR"
        assert "VERSION:2.0" in lines
        assert any(l.startswith("PRODID:") for l in lines)
        assert lines[-2] == "END:VCALENDAR"  # last element after split is "" due to trailing CRLF
        assert cal.endswith(CRLF)

    def test_single_exam_produces_one_vevent_with_correct_all_day_range(self):
        course = _course("10001", name="Data Structures")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        assert cal.count("BEGIN:VEVENT") == 1
        assert cal.count("END:VEVENT") == 1
        assert "DTSTART;VALUE=DATE:20260203" in cal
        # an all-day event's DTEND is exclusive -> the day AFTER the exam
        assert "DTEND;VALUE=DATE:20260204" in cal

    def test_summary_contains_course_id_and_name(self):
        course = _course("10001", name="Data Structures")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        assert any(l.startswith("SUMMARY:") and "10001" in l and "Data Structures" in l
                   for l in _lines(cal))

    def test_multiple_exams_each_get_their_own_vevent(self):
        c1, c2, c3 = _course("10001"), _course("10002"), _course("10003")
        cal = _exporter().build_calendar(_schedule(
            (c1, date(2026, 2, 3)), (c2, date(2026, 2, 10)), (c3, date(2026, 2, 20)),
        ))
        assert cal.count("BEGIN:VEVENT") == 3

    def test_events_are_sorted_by_exam_date_regardless_of_input_order(self):
        c1, c2, c3 = _course("A"), _course("B"), _course("C")
        cal = _exporter().build_calendar(_schedule(
            (c1, date(2026, 2, 20)), (c2, date(2026, 2, 3)), (c3, date(2026, 2, 10)),
        ))
        positions = [cal.index(f"DTSTART;VALUE=DATE:{d}") for d in
                     ("20260203", "20260210", "20260220")]
        assert positions == sorted(positions)

    def test_export_schedule_writes_a_real_file(self, tmp_path):
        course = _course("10001")
        out = tmp_path / "my_schedule.ics"
        path = _exporter().export_schedule(_schedule((course, date(2026, 2, 3))), str(out))
        assert path == str(out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "10001" in content

    def test_calendar_name_is_used_for_x_wr_calname(self):
        cal = _exporter().build_calendar(
            _schedule((_course("10001"), date(2026, 2, 3))),
            calendar_name="My Exams",
        )
        assert "X-WR-CALNAME:My Exams" in cal

    def test_each_event_has_a_uid_and_dtstamp(self):
        cal = _exporter().build_calendar(_schedule((_course("10001"), date(2026, 2, 3))))
        assert any(l.startswith("UID:") for l in _lines(cal))
        assert any(l.startswith("DTSTAMP:") for l in _lines(cal))

    def test_description_includes_instructor_and_evaluation_method(self):
        course = _course("10001", instructor="Dr. Levi", evaluation="Project")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        assert "Dr. Levi" in cal
        assert "Project" in cal

# ===========================================================================
# BOUNDARY — empty / extreme / odd-but-valid inputs
# ===========================================================================
class TestBoundary:
    def test_empty_schedule_produces_a_valid_calendar_with_no_events(self):
        cal = _exporter().build_calendar(Schedule(exams=[]))
        assert "BEGIN:VCALENDAR" in cal
        assert "END:VCALENDAR" in cal
        assert "BEGIN:VEVENT" not in cal

    def test_schedule_with_none_exams_list_is_treated_as_empty(self):
        # Schedule(exams=None) shouldn't crash the exporter.
        cal = _exporter().build_calendar(Schedule(exams=None))
        assert "BEGIN:VEVENT" not in cal

    def test_two_exams_on_the_same_day_both_get_separate_events(self):
        c1, c2 = _course("10001"), _course("10002")
        cal = _exporter().build_calendar(_schedule(
            (c1, date(2026, 2, 3)), (c2, date(2026, 2, 3)),
        ))
        assert cal.count("BEGIN:VEVENT") == 2

    def test_year_boundary_exam_on_dec_31_rolls_dtend_into_next_year(self):
        course = _course("10001")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 12, 31))))
        assert "DTSTART;VALUE=DATE:20261231" in cal
        assert "DTEND;VALUE=DATE:20270101" in cal

    def test_leap_day_exam_is_handled(self):
        course = _course("10001")
        cal = _exporter().build_calendar(_schedule((course, date(2028, 2, 29))))
        assert "DTSTART;VALUE=DATE:20280229" in cal
        assert "DTEND;VALUE=DATE:20280301" in cal

    def test_long_description_line_is_folded_at_75_octets(self):
        course = _course(
            "10001",
            name="A" * 120,  # forces a long SUMMARY/DESCRIPTION line
            instructor="B" * 120,
        )
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        for line in _lines(cal):
            # every *physical* line (continuation lines start with a space) must
            # stay within the 75-octet RFC 5545 folding limit.
            assert len(line.encode("utf-8")) <= 75

    def test_unicode_course_name_is_folded_without_splitting_multibyte_chars(self):
        # Hebrew text encodes to >1 byte/char in UTF-8; folding must not cut
        # a multi-byte character in half.
        course = _course("10001", name="קורס בהנדסת תוכנה ומערכות מבוזרות מתקדמות " * 3)
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        # if a multibyte char had been split, this would raise UnicodeDecodeError
        for line in _lines(cal):
            line.encode("utf-8").decode("utf-8")

    def test_large_number_of_exams_all_present(self):
        pairs = [
            (_course(f"{i:05d}"), date(2026, 2, 1) + timedelta(days=i % 27))
            for i in range(200)
        ]
        cal = _exporter().build_calendar(_schedule(*pairs))
        assert cal.count("BEGIN:VEVENT") == 200

    def test_explicit_generated_at_timestamp_is_normalized_to_utc(self):
        tz_plus2 = timezone(timedelta(hours=2))
        local_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=tz_plus2)
        cal = _exporter().build_calendar(
            _schedule((_course("10001"), date(2026, 2, 3))),
            generated_at=local_time,
        )
        # 10:00 +02:00 == 08:00 UTC
        assert "DTSTAMP:20260101T080000Z" in cal

    def test_naive_generated_at_is_assumed_utc(self):
        naive = datetime(2026, 1, 1, 10, 0, 0)
        cal = _exporter().build_calendar(
            _schedule((_course("10001"), date(2026, 2, 3))),
            generated_at=naive,
        )
        assert "DTSTAMP:20260101T100000Z" in cal

# ===========================================================================
# NEGATIVE — invalid input / malformed data must not silently corrupt output
# ===========================================================================
class TestNegative:
    def test_non_schedule_argument_raises_type_error(self):
        with pytest.raises(TypeError):
            _exporter().build_calendar("not-a-schedule")

    def test_none_schedule_raises_type_error(self):
        with pytest.raises(TypeError):
            _exporter().build_calendar(None)

    def test_export_schedule_with_non_string_destination_raises_type_error(self):
        with pytest.raises(TypeError):
            _exporter().export_schedule(_schedule((_course("10001"), date(2026, 2, 3))), 12345)

    def test_export_schedule_with_empty_destination_raises_value_error(self):
        with pytest.raises(ValueError):
            _exporter().export_schedule(_schedule((_course("10001"), date(2026, 2, 3))), "   ")

    def test_entries_missing_a_course_are_silently_skipped_not_crashed(self):
        # A malformed ScheduledExam (no course) must not blow up export; it is
        # simply excluded from the output rather than corrupting the calendar.
        good = ScheduledExam(course=_course("10001"), exam_date=date(2026, 2, 3))
        bad = ScheduledExam(course=None, exam_date=date(2026, 2, 5))
        cal = _exporter().build_calendar(Schedule(exams=[good, bad]))
        assert cal.count("BEGIN:VEVENT") == 1

    def test_entries_with_non_date_exam_date_are_silently_skipped(self):
        good = ScheduledExam(course=_course("10001"), exam_date=date(2026, 2, 3))
        bad = ScheduledExam(course=_course("10002"), exam_date="2026-02-05")  # wrong type
        cal = _exporter().build_calendar(Schedule(exams=[good, bad]))
        assert cal.count("BEGIN:VEVENT") == 1

    def test_special_characters_in_course_name_are_escaped_per_rfc5545(self):
        # commas, semicolons and backslashes are structural in RFC 5545 TEXT
        # values and MUST be escaped, or the resulting .ics is invalid.
        course = _course("10001", name='Intro; to, Algorithms\\Advanced')
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        assert r"Intro\; to\, Algorithms\\Advanced" in cal
        # the raw unescaped separators must not appear as literal field breaks
        assert "Intro; to, Algorithms\\Advanced" not in cal

    def test_newline_in_course_name_is_escaped_not_a_raw_line_break(self):
        course = _course("10001", name="Algorithms\nPart 2")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        assert r"Algorithms\nPart 2" in cal
        # must not have introduced a *raw* CRLF inside the SUMMARY content itself
        summary_line = next(l for l in _lines(cal) if l.startswith("SUMMARY:"))
        assert "\n" not in summary_line

    def test_excluded_dates_concept_never_leaks_into_export(self):
        # The exporter's contract is "exams only" — Schedule simply carries no
        # excluded-date concept, so nothing related to exclusions can ever
        # appear in the .ics regardless of how the board was produced.
        course = _course("10001")
        cal = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        for forbidden_token in ("EXCLUDED", "HOLIDAY", "METRICS"):
            assert forbidden_token not in cal.upper().replace("X-WR-CALNAME", "")

    def test_uids_are_unique_across_same_day_different_courses(self):
        c1, c2 = _course("10001"), _course("10002")
        cal = _exporter().build_calendar(_schedule(
            (c1, date(2026, 2, 3)), (c2, date(2026, 2, 3)),
        ))
        uids = [l for l in _lines(cal) if l.startswith("UID:")]
        assert len(uids) == 2
        assert uids[0] != uids[1]

    def test_uid_is_deterministic_for_identical_input(self):
        # Re-exporting the same board must yield the same UIDs (idempotent
        # exports — re-importing into a calendar app should update, not
        # duplicate, the same event).
        course = _course("10001")
        cal1 = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        cal2 = _exporter().build_calendar(_schedule((course, date(2026, 2, 3))))
        uid1 = next(l for l in _lines(cal1) if l.startswith("UID:"))
        uid2 = next(l for l in _lines(cal2) if l.startswith("UID:"))
        assert uid1 == uid2