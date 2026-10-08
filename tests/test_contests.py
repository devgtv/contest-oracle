import datetime

from contests import (
    classify_contest,
    filter_upcoming,
    format_announcement,
    format_list_entry,
    sort_by_start_time,
)


def make_contest(cid=1, name="Codeforces Round 2000 (Div. 2)", phase="BEFORE", start=1_700_000_000):
    return {"id": cid, "name": name, "phase": phase, "startTimeSeconds": start}


def test_classify_blue_divisions():
    assert classify_contest("Codeforces Round 1 (Div. 1)") == "🔵"
    assert classify_contest("Codeforces Round 1 (Div. 2)") == "🔵"
    assert classify_contest("Codeforces Round 1 (Div. 1 + Div. 2)") == "🔵"


def test_classify_green_and_yellow():
    assert classify_contest("Codeforces Round 1 (Div. 3)") == "🟢"
    assert classify_contest("Codeforces Round 1 (Div. 4)") == "🟡"


def test_classify_unclassified():
    assert classify_contest("Codeforces Round 1") is None
    assert classify_contest("") is None
    assert classify_contest("ICPC World Finals 2026") is None


def test_filter_upcoming_only_before_and_classified():
    contests = [
        make_contest(cid=1, name="Codeforces Round 1 (Div. 2)"),
        make_contest(cid=2, name="Codeforces Round 2 (Div. 3)"),
        make_contest(cid=3, name="Codeforces Round 3 (Div. 4)", phase="FINISHED"),
        make_contest(cid=4, name="ICPC Finals"),
    ]
    result = filter_upcoming(contests)
    assert [c["id"] for c, _ in result] == [1, 2]
    assert [emoji for _, emoji in result] == ["🔵", "🟢"]


def test_sort_by_start_time():
    contests = [(make_contest(cid=1, start=300), "🔵"), (make_contest(cid=2, start=100), "🟢")]
    result = sort_by_start_time(contests)
    assert [c["id"] for c, _ in result] == [2, 1]


def test_format_announcement_with_role_and_without():
    start = datetime.datetime.fromtimestamp(1_700_000_000, datetime.timezone.utc).strftime("%d/%m %H:%M UTC")
    expected_without = (
        f"\n📢 New contest detected!\nCodeforces Round 2000 (Div. 2)\nStarts: {start}\nhttps://codeforces.com/contest/1"
    )
    assert format_announcement(make_contest(), "🔵") == expected_without

    with_role = format_announcement(make_contest(), "🔵", role_id=123)
    assert with_role.startswith("<@&123>\n")


def test_format_list_entry():
    entry = format_list_entry(make_contest(), "🟢")
    assert "Div 3" in entry
    assert "https://codeforces.com/contest/1" in entry
