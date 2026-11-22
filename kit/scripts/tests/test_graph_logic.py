"""Pure logic of kit/integrations/microsoft-graph/graph.py: grouping, board limits, the
repeat check and the organizer journal. No network: apply and undo run on a fake mailbox."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

GRAPH_PY = Path(__file__).resolve().parents[2] / "integrations" / "microsoft-graph" / "graph.py"


@pytest.fixture()
def graph(tmp_path, monkeypatch):
    monkeypatch.setenv("NEST_GRAPH_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location("nest_graph", GRAPH_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def msg(i: int, address: str, name: str = "", read: bool = True) -> dict:
    return {"id": f"id{i}", "subject": f"subject {i}", "isRead": read, "receivedDateTime": f"2026-11-{10 + i % 9:02d}T08:00:00Z",
            "from": {"emailAddress": {"name": name, "address": address}}}


INBOX = [
    msg(1, "news@n.shop-a.com", "Shop A"), msg(2, "orders@shop-a.com", "Shop A", read=False), msg(3, "deals@shop-a.com", "Shop A"),
    msg(4, "friend.one@gmail.com", "Friend One"), msg(5, "friend.two@gmail.com", "Friend Two"),
    msg(6, "info@mail.example.co.uk", "Example UK"), msg(7, "info_at_vip_pizza_nl_abc_def@privaterelay.appleid.com", "Pizza"),
]
FOLDERS = [
    {"id": "f-inbox", "name": "Inbox", "total": 7, "unread": 1, "well_known": "inbox"},
    {"id": "f-del", "name": "Verwijderde items", "total": 3, "unread": 0, "well_known": "deleteditems"},
    {"id": "f-junk", "name": "Junk Email", "total": 0, "unread": 0, "well_known": "junkemail"},
    {"id": "f-sent", "name": "Sent Items", "total": 9, "unread": 0, "well_known": "sentitems"},
    {"id": "f-shop", "name": "Shopping", "total": 12, "unread": 0, "well_known": ""},
]


def make_scan(graph, rules=None) -> dict:
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"), "inbox_total": len(INBOX),
            "groups": graph.group_messages(INBOX), "folders": [dict(f) for f in FOLDERS], "rules": rules or []}


def gid(scan: dict, key: str) -> str:
    return next(g for g, v in scan["groups"].items() if v["key"] == key)


# --- grouping ---------------------------------------------------------------------


def test_company_groups_by_registrable_domain(graph):
    assert graph.sender_key("news@n.shop-a.com") == ("shop-a.com", ["shop-a.com"])
    assert graph.sender_key("info@mail.example.co.uk") == ("example.co.uk", ["example.co.uk"])


def test_freemail_groups_per_address(graph):
    assert graph.sender_key("Friend.One@Gmail.com") == ("friend.one@gmail.com", ["friend.one@gmail.com"])


def test_apple_relay_unwrapped_to_real_domain(graph):
    key, tokens = graph.sender_key("info_at_vip_pizza_nl_abc_def@privaterelay.appleid.com")
    assert key == "pizza.nl"
    assert tokens == ["pizza.nl", "pizza_nl"]


def test_groups_sorted_by_size_with_counts(graph):
    groups = graph.group_messages(INBOX)
    first = groups["g1"]
    assert first["key"] == "shop-a.com" and first["count"] == 3 and first["unread"] == 1
    assert first["ids"] == ["id1", "id2", "id3"]
    assert {g["key"] for g in groups.values()} == {"shop-a.com", "friend.one@gmail.com", "friend.two@gmail.com", "example.co.uk", "pizza.nl"}
    assert groups[next(g for g, v in groups.items() if v["key"] == "friend.one@gmail.com")]["person"] is True


# --- the board ----------------------------------------------------------------------


def test_plan_counts_and_unplaced_mail_stays(graph):
    scan = make_scan(graph)
    board = graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com")], "rule": True}]})
    assert board["moving"] == 3 and board["new_folders"] == 0
    assert board["stay"] == {"groups": 4, "mails": 4}
    assert board["buckets"][0]["rule_mode"] == "new" and board["buckets"][0]["rule_add"] == ["shop-a.com"]


@pytest.mark.parametrize("target", ["Deleted Items", "deleteditems", "trash", "Verwijderde items", "Inbox", "Sent Items"])
def test_protected_folders_refused_as_target(graph, target):
    scan = make_scan(graph)
    with pytest.raises(graph.PlanError):
        graph.check_plan(scan, {"buckets": [{"folder": target, "groups": [gid(scan, "shop-a.com")], "note": "x"}]})


def test_junk_is_allowed_as_target(graph):
    scan = make_scan(graph)
    board = graph.check_plan(scan, {"buckets": [{"folder": "Junk", "groups": [gid(scan, "pizza.nl")]}]})
    assert board["buckets"][0]["folder"] == "Junk Email"


def test_group_in_two_folders_refused(graph):
    scan = make_scan(graph)
    g = gid(scan, "shop-a.com")
    with pytest.raises(graph.PlanError, match="two folders"):
        graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [g]}, {"folder": "Deals", "groups": [g], "note": "deals"}]})


def test_unknown_group_refused(graph):
    with pytest.raises(graph.PlanError, match="Unknown group"):
        graph.check_plan(make_scan(graph), {"buckets": [{"folder": "Shopping", "groups": ["g99"]}]})


def test_new_folder_needs_note_and_is_flat(graph):
    scan = make_scan(graph)
    g = gid(scan, "pizza.nl")
    with pytest.raises(graph.PlanError, match="note"):
        graph.check_plan(scan, {"buckets": [{"folder": "Food", "groups": [g]}]})
    with pytest.raises(graph.PlanError, match="flat"):
        graph.check_plan(scan, {"buckets": [{"folder": "Food/Pizza", "groups": [g], "note": "food"}]})


def test_max_new_folders(graph):
    many = [msg(100 + i, f"x@brand{i}.com") for i in range(graph.MAX_NEW_FOLDERS + 1)]
    scan = make_scan(graph)
    scan["groups"] = graph.group_messages(many)
    buckets = [{"folder": f"Brand {i}", "groups": [g], "note": "brand"} for i, g in enumerate(scan["groups"])]
    with pytest.raises(graph.PlanError, match="more than"):
        graph.check_plan(scan, {"buckets": buckets})
    graph.check_plan(scan, {"buckets": buckets[: graph.MAX_NEW_FOLDERS]})


def test_rule_strings_only_from_scan(graph):
    scan = make_scan(graph)
    plan = {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com")], "rule": True, "senders": ["@"], "from_contains": ["."]}]}
    board = graph.check_plan(scan, plan)
    assert board["buckets"][0]["rule_add"] == ["shop-a.com"]


def test_rule_sender_limit(graph):
    many = [msg(200 + i, f"x@sender{i}.com") for i in range(graph.MAX_RULE_SENDERS + 1)]
    scan = make_scan(graph)
    scan["groups"] = graph.group_messages(many)
    with pytest.raises(graph.PlanError, match="senders"):
        graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": list(scan["groups"]), "rule": True}]})


def test_existing_rule_is_extended_not_duplicated(graph):
    rules = [{"id": "r1", "conditions": {"senderContains": ["shop-a.com"]}, "actions": {"moveToFolder": "f-shop"}}]
    scan = make_scan(graph, rules)
    board = graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com")], "rule": True}]})
    assert board["buckets"][0]["rule_mode"] == ""  # already covered
    board = graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com"), gid(scan, "pizza.nl")], "rule": True}]})
    assert board["buckets"][0]["rule_mode"] == "extend" and board["buckets"][0]["rule_add"] == ["pizza.nl", "pizza_nl"]


# --- repeats ------------------------------------------------------------------------

START = date(2026, 12, 1)


@pytest.mark.parametrize("rrule", ["FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20270601", "FREQ=DAILY;COUNT=30", "RRULE:FREQ=WEEKLY;COUNT=52", "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR;COUNT=26"])
def test_rrule_allowed(graph, rrule):
    ok, why = graph.check_rrule(rrule, START)
    assert ok, why


@pytest.mark.parametrize("rrule,reason", [
    ("FREQ=MONTHLY;COUNT=3", "daily or weekly"),
    ("FREQ=WEEKLY;BYDAY=MO", "needs an end"),
    ("FREQ=DAILY;COUNT=400", "at most a year"),
    ("FREQ=WEEKLY;COUNT=53", "at most a year"),
    ("FREQ=WEEKLY;UNTIL=20280101", "at most a year"),
    ("FREQ=DAILY;UNTIL=20261101", "before the start"),
    ("FREQ=DAILY;COUNT=5;UNTIL=20261210", "not both"),
    ("FREQ=WEEKLY;BYSETPOS=1;COUNT=3", "Not supported"),
    ("FREQ=DAILY;BYDAY=MO;COUNT=3", "BYDAY"),
])
def test_rrule_refused(graph, rrule, reason):
    ok, why = graph.check_rrule(rrule, START)
    assert not ok and reason in why


def test_recurrence_shape(graph):
    r = graph.recurrence("FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20270601", START)
    assert r == {"pattern": {"type": "weekly", "interval": 1, "daysOfWeek": ["monday", "wednesday"]},
                 "range": {"startDate": "2026-12-01", "type": "endDate", "endDate": "2027-06-01"}}
    assert graph.recurrence("FREQ=DAILY;COUNT=3", START)["range"]["numberOfOccurrences"] == 3


# --- apply, journal, undo ---------------------------------------------------------------


class FakeOps:
    def __init__(self, scan: dict):
        self.where = {i: "f-inbox" for g in scan["groups"].values() for i in g["ids"]}
        self.folders = {f["id"]: f["name"] for f in scan["folders"]}
        self.rules = {r["id"]: r for r in scan["rules"]}
        self.n = 0

    def inbox_id(self):
        return "f-inbox"

    def create_folder(self, name):
        self.n += 1
        self.folders[f"new{self.n}"] = name
        return f"new{self.n}"

    def move(self, ids, folder_id):
        assert folder_id != "f-del"
        moved = [i for i in ids if i in self.where]
        for i in moved:
            self.where[i] = folder_id
        return moved, [i for i in ids if i not in self.where]

    def add_rule(self, name, folder_id, senders):
        self.n += 1
        self.rules[f"r{self.n}"] = {"id": f"r{self.n}", "conditions": {"senderContains": list(senders)}, "actions": {"moveToFolder": folder_id}}
        return f"r{self.n}"

    def set_rule_conditions(self, rule_id, conditions):
        self.rules[rule_id]["conditions"] = json.loads(json.dumps(conditions))

    def drop_rule(self, rule_id):
        self.rules.pop(rule_id, None)

    def drop_empty_folder(self, folder_id):
        if any(f == folder_id for f in self.where.values()):
            return False
        self.folders.pop(folder_id)
        return True


def test_apply_then_undo_restores_everything(graph):
    rules = [{"id": "r0", "conditions": {"senderContains": ["shop-a.com"]}, "actions": {"moveToFolder": "f-shop"}}]
    scan = make_scan(graph, rules)
    ops = FakeOps(scan)
    before_where, before_rules, before_folders = dict(ops.where), json.loads(json.dumps(ops.rules)), dict(ops.folders)
    plan = {"buckets": [
        {"folder": "Shopping", "groups": [gid(scan, "shop-a.com"), gid(scan, "example.co.uk")], "rule": True},
        {"folder": "Food", "groups": [gid(scan, "pizza.nl")], "rule": True, "note": "Takeaway and delivery"},
    ]}
    now = datetime.now(UTC)
    result = graph.run_apply(ops, scan, graph.check_plan(scan, plan), now)
    assert result["moved"] == 5 and result["inbox_left"] == 2 and result["rules"] == 2
    assert result["new_folders"][0]["folder"] == "Food"
    assert ops.where["id4"] == "f-inbox" and ops.where["id5"] == "f-inbox"  # people stay
    assert ops.rules["r0"]["conditions"]["senderContains"] == ["shop-a.com", "example.co.uk"]

    undone = graph.run_undo(ops, now + timedelta(hours=1))
    assert undone["back_in_inbox"] == 5 and undone["removed_folders"] == ["Food"]
    assert ops.where == before_where and ops.rules == before_rules and ops.folders == before_folders
    with pytest.raises(graph.PlanError, match="already undone"):
        graph.run_undo(ops, now + timedelta(hours=2))


def test_undo_refused_after_24_hours(graph):
    scan = make_scan(graph)
    ops = FakeOps(scan)
    now = datetime.now(UTC)
    graph.run_apply(ops, scan, graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com")]}]}), now)
    with pytest.raises(graph.PlanError, match="24 hours"):
        graph.run_undo(ops, now + timedelta(hours=25))


def test_undo_keeps_a_new_folder_that_got_other_mail(graph):
    scan = make_scan(graph)
    ops = FakeOps(scan)
    now = datetime.now(UTC)
    graph.run_apply(ops, scan, graph.check_plan(scan, {"buckets": [{"folder": "Food", "groups": [gid(scan, "pizza.nl")], "note": "food"}]}), now)
    new_id = next(k for k, v in ops.folders.items() if v == "Food")
    ops.where["later-mail"] = new_id
    assert graph.run_undo(ops, now)["kept_folders"] == ["Food"]


def test_journal_is_private_and_outside_workspace(graph, tmp_path):
    scan = make_scan(graph)
    graph.run_apply(FakeOps(scan), scan, graph.check_plan(scan, {"buckets": [{"folder": "Shopping", "groups": [gid(scan, "shop-a.com")]}]}), datetime.now(UTC))
    files = list((tmp_path / "organizer").glob("run-*.json"))
    assert len(files) == 1
    if sys.platform != "win32":  # Windows has no POSIX modes; the user data dir is per-user there
        assert oct(files[0].stat().st_mode)[-3:] == "600"


# --- never send -------------------------------------------------------------------------


def test_no_send_scope_and_no_send_call(graph):
    assert "Mail.Send" not in graph.SCOPES
    source = GRAPH_PY.read_text()
    assert "/send" not in source and "sendMail" not in source


def test_refs_survive_between_runs(graph, tmp_path):
    refs = graph.Refs(tmp_path / "refs.json")
    r = refs.ref("m", "LONG-ID-1")
    assert r == "m1" and refs.ref("m", "LONG-ID-1") == "m1"
    refs.save()
    assert graph.Refs(tmp_path / "refs.json").resolve("m1") == "LONG-ID-1"
    with pytest.raises(graph.GraphError):
        refs.resolve("m99")


# --- what the audit of 1.0.0 found -----------------------------------------------------------

class FakeGraph:
    """Records the calls a command makes; answers a stored event for GET."""

    def __init__(self, event=None):
        self.calls, self.event = [], event or {}
        self.tz = "Europe/Berlin"

    def find_id(self, name):
        return "f-inbox"

    def call(self, method, path, params=None, body=None, prefer=""):
        self.calls.append((method, path, params, body))
        if method == "GET" and "/events/" in path:
            return self.event
        return {"value": []} if method == "GET" else {**self.event, **(body or {}), "id": "e1"}


def args(**kw):
    import argparse
    return argparse.Namespace(**kw)


def test_unread_filter_names_the_order_property_first(graph, tmp_path):
    g = FakeGraph()
    graph.cmd_mail(args(cmd="list", limit=10, unread=True, folder="inbox"), g, graph.Refs(tmp_path / "refs.json"))
    params = g.calls[0][2]
    assert params["$orderby"] == "receivedDateTime desc"
    assert params["$filter"].startswith("receivedDateTime ge ") and "isRead eq false" in params["$filter"]


def test_update_with_only_a_new_end(graph, tmp_path):
    event = {"id": "e1", "subject": "Dentist", "isAllDay": False, "start": {"dateTime": "2026-12-03T14:30:00"},
             "end": {"dateTime": "2026-12-03T15:00:00"}}
    refs = graph.Refs(tmp_path / "refs.json")
    ref = refs.ref("c", "e1")
    g = FakeGraph(event)
    graph.cmd_calendar(args(cmd="update", ref=ref, title=None, start=None, end="2026-12-03T16:00"), g, refs)
    body = [c for c in g.calls if c[0] == "PATCH"][0][3]
    assert body["start"]["dateTime"] == "2026-12-03T14:30:00" and body["end"]["dateTime"] == "2026-12-03T16:00:00"
    with pytest.raises(graph.GraphError):
        graph.cmd_calendar(args(cmd="update", ref=ref, title=None, start=None, end="2026-12-03T14:00"), FakeGraph(event), refs)


def test_every_failure_is_one_json_line(graph, monkeypatch, capsys):
    def offline(*a, **k):
        raise ConnectionError("no route")

    monkeypatch.setattr(graph, "access_token", offline)
    assert graph.main(["mail", "list"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert "Could not reach Microsoft" in out["error"]
    monkeypatch.setattr(graph, "access_token", lambda: (_ for _ in ()).throw(ValueError("Invalid isoformat string: 'tomorrow'")))
    assert graph.main(["mail", "list"]) == 1
    assert "ISO" in json.loads(capsys.readouterr().out)["error"]


def test_the_sign_in_message_is_the_command_to_type(graph, capsys):
    assert graph.main(["mail", "list"]) == 1
    assert "uv run scripts/graph.py login" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_private_files_are_never_world_readable(graph, tmp_path):
    target = tmp_path / "deep" / "token-cache.json"
    graph._write_private(target, "{}")
    assert target.stat().st_mode & 0o077 == 0 and target.parent.stat().st_mode & 0o077 == 0
    assert not target.with_name("token-cache.json.tmp").exists()


def test_the_lock_is_taken_released_and_never_hangs(graph, tmp_path):
    path = tmp_path / "refs.lock"
    with graph._Lock(path) as lock:
        assert lock.held and path.exists()
        with graph._Lock(path, wait=0.3) as second:      # busy: carries on without, after the wait
            assert not second.held
        assert path.exists()                              # the second one did not take the first one's lock away
    assert not path.exists()
    path.write_text("", encoding="utf-8")
    import os
    os.utime(path, (1, 1))                                # left behind long ago by a run that was killed
    with graph._Lock(path) as lock:
        assert lock.held
