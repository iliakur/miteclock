import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial

import pytest
from click.testing import CliRunner

from miteclock import __version__, cli
from miteclock.mite import StopWatch
from miteclock.settings import MiteSettings, Settings


def test_build_menu(time_entries):
    time_entries += [
        {"id": 3, "project_id": 5, "service_id": 2, "note": "writing some code"},
        {"id": 4, "project_id": 5, "service_id": 2, "note": "reading some code"},
    ]
    keys = "asdf"

    expected_prompt = """
a	daily stand-up
s	juggling
d	catching up on email
f	writing some code
aa	reading some code
Select an entry please
    """.strip()
    expected_default = "aa"
    expected_mapping = {
        "a": {
            "id": 0,
            "project_id": 1,
            "service_id": 6,
            "note": "daily stand-up",
            "updated_at": "2020-06-08T10:15:42.007128",
        },
        "s": {
            "id": 1,
            "project_id": 2,
            "service_id": 4,
            "note": "juggling",
            "updated_at": "2020-06-08T11:05:32.007128",
        },
        "d": {
            "id": 2,
            "project_id": 3,
            "service_id": 6,
            "note": "catching up on email",
            "updated_at": "2020-06-08T11:45:02.044416",
        },
        "f": {"id": 3, "project_id": 5, "service_id": 2, "note": "writing some code"},
        "aa": {"id": 4, "project_id": 5, "service_id": 2, "note": "reading some code"},
    }

    prompt, default, mapping = cli.build_menu(keys, time_entries)
    assert expected_prompt == prompt
    assert expected_default == default
    assert expected_mapping == mapping


def test_build_menu_one_key(time_entries):
    prompt, default, mapping = cli.build_menu(
        key_characters="a", time_entries=time_entries
    )
    assert prompt == ("a\tdaily stand-up\n" "aa\tjuggling\n" "Select an entry please")


class FakeApi:
    def __init__(self, mite_server):
        self.mite_server = mite_server

    def get(self, resource, **kwargs):
        resource = "time_entries" if resource == "daily" else resource
        return self.mite_server[resource]

    def post(self, resource, **kwargs):
        if resource != "time_entries":
            raise ValueError(f"Don't know how to post '{resource}'")
        new_id = (
            max(
                (item["time_entry"]["id"] for item in self.mite_server[resource]),
                default=-1,
            )
            + 1
        )
        new_entry = json.loads(kwargs["data"])
        new_entry["time_entry"]["id"] = new_id
        self.mite_server[resource].append(new_entry)
        return new_entry

    def patch(self, resource, **kwargs):
        resource, r_id = resource.split("/")
        if resource != "tracker":
            raise ValueError(f"Don't know how to patch '{resource}'")
        self.mite_server[resource]["tracker"]["tracking_time_entry"] = {"id": int(r_id)}

    def delete(self, resource, **kwargs):
        resource, r_id = resource.split("/")
        if resource == "tracker":
            self.mite_server[resource] = {"tracker": {}}
        else:
            self.mite_server[resource] = [
                item for item in self.mite_server[resource] if item["id"] != r_id
            ]

    def __call__(self, method, resource, **request_kwargs):
        return getattr(self, method)(resource, **request_kwargs)


@pytest.fixture
def application_context(mite_server, shortcuts, tmp_path):
    api = FakeApi(mite_server)

    return (
        Settings(
            mite=MiteSettings(
                api=api, get=partial(api, "get"), stopwatch=StopWatch(api)
            ),
            menu_keys="asdfjkl;",
            shortcuts=shortcuts,
            config_dir=tmp_path,
        ),
        mite_server,
    )


def test_version(application_context):
    """`--version` prints application version and exits with code 0."""
    settings, _ = application_context
    result = CliRunner().invoke(cli.main, "--version", obj=settings)
    assert result.exit_code == 0
    assert f"miteclock {__version__}" in result.output


def test_help_message(application_context):
    """Invoking without any args and with `--help` should show help message."""
    settings, _ = application_context
    no_args_passed = CliRunner().invoke(cli.main, obj=settings)
    assert no_args_passed.exit_code == 0

    help_flag_passed = CliRunner().invoke(cli.main, "--help", obj=settings)
    assert help_flag_passed.exit_code == 0

    assert no_args_passed.output == help_flag_passed.output


@pytest.mark.parametrize(
    "cmd, stdin, already_tracking, new_tracking",
    [
        ("start daily", None, 0, 0),
        ("start daily", None, 1, 0),
        ("start daily", None, None, 0),
        # For resume it does not make sense to specify a different
        # entry that's being tracked, because the latest one will be started
        # automatically. That's the one being tracked normally.
        ("resume", None, None, 2),
        ("start -l", None, None, 2),
        # Select most recent entry in menu by hitting "enter".
        # There may or may not be a watch already running and it may be for
        # this or a different entry. The result should be the same.
        ("start", "\n", 2, 2),
        ("start", "\n", 1, 2),
        ("start", "\n", None, 2),
        # Use a key to choose entry that is not most recent.
        # Same caveats apply about the presence of a running clock.
        ("start", "q\na", None, 0),
        ("start", "q\na", 0, 0),
        ("start", "q\na", 1, 0),
        # Need here an example of a keyboard interrupt
    ],
)
def test_start_existing_activity(
    cmd, stdin, already_tracking, new_tracking, application_context
):
    settings, mite_server = application_context
    old_entries = deepcopy(mite_server["time_entries"])
    if already_tracking is None:
        assert mite_server["tracker"] == {"tracker": {}}
    else:
        mite_server["tracker"] = {
            "tracker": {"tracking_time_entry": {"id": already_tracking}}
        }

    result = CliRunner().invoke(cli.main, cmd, obj=settings, input=stdin)

    assert result.exit_code == 0
    assert mite_server["tracker"] == {
        "tracker": {"tracking_time_entry": {"id": new_tracking}}
    }
    assert mite_server["time_entries"] == old_entries


def test_start_no_activities_today(application_context):
    settings, mite_server = application_context
    mite_server["time_entries"] = []

    result = CliRunner().invoke(cli.main, "start", obj=settings)

    assert result.exit_code == 0
    assert "No entries found for today, please specify an activity." in result.output


@pytest.mark.parametrize("activity", ["a b c d", "b"])
def test_start_invalid_activity(activity, application_context):
    settings, mite_server = application_context
    mite_server["time_entries"] = []

    result = CliRunner().invoke(cli.main, "start " + activity, obj=settings)
    assert result.exit_code == 1


@pytest.mark.parametrize("already_tracking", [0, None])
def test_start_new_activity(already_tracking, application_context):
    settings, mite_server = application_context
    if already_tracking is None:
        assert mite_server["tracker"] == {"tracker": {}}
    else:
        mite_server["tracker"] = {
            "tracker": {"tracking_time_entry": {"id": already_tracking}}
        }
    new_entry = {
        "time_entry": {
            "id": 3,
            "project_id": 3,
            "service_id": 0,
            "note": "busting out code",
        }
    }
    assert new_entry not in mite_server["time_entries"]

    result = CliRunner().invoke(
        cli.main, ["start", "a", "d", "busting out code"], obj=settings
    )

    assert result.exit_code == 0
    assert mite_server["tracker"] == {"tracker": {"tracking_time_entry": {"id": 3}}}
    assert new_entry in mite_server["time_entries"]


def test_start_trim_whitespace_from_note(application_context):
    """When starting new activity, make sure to trim whitespace from note."""
    settings, mite_server = application_context

    # Start timer for entry that exists already.
    result = CliRunner().invoke(
        cli.main, ["start", "o", "c", " daily stand-up "], obj=settings
    )
    assert result.exit_code == 0
    assert mite_server["tracker"] == {"tracker": {"tracking_time_entry": {"id": 0}}}

    # Start timer for a new entry.
    expected_new_entry = {
        "time_entry": {
            "id": 3,
            "project_id": 1,
            "service_id": 6,
            "note": "juggling",
        }
    }
    result = CliRunner().invoke(
        cli.main, ["start", "o", "c", " juggling "], obj=settings
    )
    assert result.exit_code == 0
    assert expected_new_entry in mite_server["time_entries"]


def test_stop_idempotent(application_context):
    settings, mite_server = application_context
    assert mite_server["tracker"] == {"tracker": {}}

    result = CliRunner().invoke(cli.main, ["stop"], obj=settings)
    assert result.exit_code == 0
    assert mite_server["tracker"] == {"tracker": {}}


def test_stop_running(application_context):
    settings, mite_server = application_context
    mite_server["tracker"] = {"tracker": {"tracking_time_entry": {"id": 0}}}

    result = CliRunner().invoke(cli.main, ["stop"], obj=settings)
    assert result.exit_code == 0
    assert mite_server["tracker"] == {"tracker": {}}


@pytest.mark.parametrize(
    "item_type, output",
    [
        (
            "projects",
            (
                "Company_Internal_2020\n"
                "OCP ED-209\n"
                "ZDF - Rewriting Backend\n"
                "ACME :: Squashing Bugs\n"
                "AT&T/Designing OS\n"
                "AT&T/Designing OS (Customer: AT&T)\n"
            ),
        ),
        (
            "services",
            (
                "Development\n"
                "Design\n"
                "Developer Training\n"
                "DevOps\n"
                "QA\n"
                "Language QA\n"
                "Communication\n"
            ),
        ),
        (
            "shortcuts",
            (
                "o = OCP\n"
                "a = ACME\n"
                "c = Communication\n"
                "d = Development\n"
                "q = {'pattern': 'QA', 'match': 'strict'}\n"
                "daily = ['o', 'c', 'daily stand-up']\n"
                "weekly = ['o', 'c', 'weekly meeting']\n"
                "nested = ['ad', 'hunting for bugs']\n"
                "ad = ['a', 'd']\n"
            ),
        ),
        (
            "",
            (
                "o = OCP\n"
                "a = ACME\n"
                "c = Communication\n"
                "d = Development\n"
                "q = {'pattern': 'QA', 'match': 'strict'}\n"
                "daily = ['o', 'c', 'daily stand-up']\n"
                "weekly = ['o', 'c', 'weekly meeting']\n"
                "nested = ['ad', 'hunting for bugs']\n"
                "ad = ['a', 'd']\n"
            ),
        ),
    ],
)
def test_show(item_type, output, application_context):
    settings, _ = application_context

    result = CliRunner().invoke(cli.main, "show " + item_type, obj=settings)

    assert result.exit_code == 0
    assert result.output == output


HELP_MSG = """Usage: main [OPTIONS] COMMAND [ARGS]...

  miteclock

  Lets you start and stop the clock in mite quickly from your terminal.

  Pass the '--help' flag to sub-commands to see how to use them.

Options:
  --version  Show miteclock's version.
  --help     Show this message and exit.

Commands:
  completion          Set up shell autocompletion.
  resume              An alias for `start -l`.
  show (list)         Show list of requested items.
  start               Start the clock for an activity.
  status              Display current state of mite.
  stop (break,pause)  Stop current clock.
"""


def test_missing_config_dir(tmp_path, testing_url):
    """When config is missing we try to re-create it.

    If valid input is supplied, we succeed.
    """
    result = CliRunner().invoke(
        cli.main, obj=tmp_path, input=f"6d12e0bf974df0e9\n{testing_url}\n"
    )
    assert result.exit_code == 0
    assert result.output == (
        "Key not found, please enter it: 6d12e0bf974df0e9\n"
        + f"Please copy/paste your mite URL: {testing_url}\n"
        + HELP_MSG
    )
    assert (
        tmp_path / ".config" / "miteclock" / "apikey"
    ).read_text() == "6d12e0bf974df0e9\n"


def test_missing_config_dir_invalid_input(tmp_path):
    """Config dir is missing and we received invalid input to one of the required fields.

    This should result in a crash and a clear error message.
    """
    result = CliRunner().invoke(
        cli.main, obj=tmp_path, input="6d12e0bf974df0e9\nhttps://google.com\n"
    )
    assert result.exit_code == 1
    assert result.output == (
        "Key not found, please enter it: 6d12e0bf974df0e9\n"
        "Please copy/paste your mite URL: https://google.com\n"
        "Detected the following problems with your configuration:\n"
        "url: Make sure you are using a mite url.\n"
    )


def test_bash_completion(application_context, tmp_path):
    rc_path = tmp_path / ".bashrc"
    rc_path.write_text("")
    settings, _ = application_context
    result = CliRunner().invoke(
        cli.main, ["completion", "bash"], obj=settings, env={"HOME": str(tmp_path)}
    )
    assert result.exit_code == 0
    assert result.output == f"Success! Added bash completion loading to {rc_path}.\n"
    # The path to source in the text below is relative to the tmp_path as both HOME and
    # settings.config_dir
    assert rc_path.read_text() == "\n# Added by miteclock\nsource ~/bash_completion"


def test_bash_completion_idempotent(application_context, tmp_path):
    rc_path = tmp_path / ".bashrc"
    rc_path.write_text("source ~/bash_completion")
    settings, _ = application_context
    result = CliRunner().invoke(
        cli.main, ["completion", "bash"], obj=settings, env={"HOME": str(tmp_path)}
    )
    assert result.exit_code == 0
    assert result.output == "Looks like completions are already present.\n"
    assert rc_path.read_text() == "source ~/bash_completion"


@pytest.mark.parametrize(
    "full, content",
    [
        (True, [cli.EmptyMessage, cli.Message("No entries today."), cli.EmptyMessage]),
        (False, []),
    ],
)
def test_status_no_entries(full, content):
    assert cli.report_status([], full) == [
        cli.Message("The clock is not running", {"fg": "red", "bold": True}),
        *content,
        cli.Message("Total time clocked in today: 0h0m", {"bold": True}),
    ]


@pytest.fixture
def entries():
    """Some time entries to test with.

    The order matters: we want them NOT to follow creation time so that we can
    test the sorting for "full status".
    """
    return [
        cli.Entry(
            project_name="a",
            service_name="work",
            customer_name="",
            note="test",
            minutes=cli.MinuteCount(7),
            created_at=datetime(2022, 1, 16, hour=9, minute=10),
        ),
        cli.Entry(
            project_name="a",
            service_name="work",
            customer_name="",
            note="",
            minutes=cli.MinuteCount(4),
            created_at=datetime(2022, 1, 16, hour=9, minute=5),
        ),
        cli.Entry(
            project_name="a",
            service_name="work",
            customer_name="ACME Inc.",
            note="test",
            minutes=cli.MinuteCount(55),
            created_at=datetime(2022, 1, 16, hour=15, minute=5),
        ),
    ]


@pytest.mark.parametrize(
    "full, content",
    [
        pytest.param(False, [], id="Display no entries if not full report."),
        pytest.param(
            True,
            [
                cli.EmptyMessage,
                cli.Message("Entries today:"),
                cli.EmptyMessage,
                cli.Message(("Project: a\nService: work\nNote: \nTime spent: 0h4m")),
                cli.EmptyMessage,
                cli.Message(
                    ("Project: a\nService: work\nNote: test\nTime spent: 0h7m")
                ),
                cli.EmptyMessage,
                cli.Message(
                    (
                        "Project: a\n"
                        "Customer: ACME Inc.\n"
                        "Service: work\n"
                        "Note: test\n"
                        "Time spent: 0h55m"
                    )
                ),
                cli.EmptyMessage,
            ],
            id="Display all entries for full report.",
        ),
    ],
)
def test_status_untracked_entries(full, content, entries):
    assert cli.report_status(entries, full=full) == [
        cli.Message("The clock is not running", {"fg": "red", "bold": True}),
        *content,
        cli.Message("Total time clocked in today: 1h6m", {"bold": True}),
    ]


@pytest.mark.parametrize(
    "full, content",
    [
        pytest.param(
            False,
            [
                cli.Message("Below is the entry being tracked."),
                cli.Message("Project: a\nService: work\nNote: \nTime spent: 0h4m"),
            ],
            id="Display only tracked entry if not full report.",
        ),
        pytest.param(
            True,
            [
                cli.Message("Entries today:"),
                cli.EmptyMessage,
                cli.Message(
                    "Project: a\nService: work\nNote: \nTime spent: 0h4m",
                    fmt_keywords={"fg": "green", "bold": True},
                ),
                cli.EmptyMessage,
                cli.Message("Project: a\nService: work\nNote: test\nTime spent: 0h7m"),
                cli.EmptyMessage,
                cli.Message(
                    "Project: a\n"
                    "Customer: ACME Inc.\n"
                    "Service: work\n"
                    "Note: test\n"
                    "Time spent: 0h55m"
                ),
            ],
            id="Display all entries for full report.",
        ),
    ],
)
def test_status_with_tracked(full, content, entries):
    to_be_tracked = entries[1]
    entries[1] = cli.TrackedEntry(
        to_be_tracked.project_name,
        to_be_tracked.service_name,
        to_be_tracked.customer_name,
        to_be_tracked.note,
        to_be_tracked.minutes,
        to_be_tracked.created_at,
    )
    assert cli.report_status(entries, full=full) == [
        cli.Message("The clock is running!", {"fg": "green", "bold": True}),
        cli.EmptyMessage,
        *content,
        cli.EmptyMessage,
        cli.Message("Total time clocked in today: 1h6m", {"bold": True}),
    ]


@pytest.mark.parametrize(
    "tracking, entry_type, minutes",
    [
        ({}, cli.Entry, 15),
        (
            {"tracking": {"since": "2015-10-16T12:44:17+02:00", "minutes": 12}},
            cli.TrackedEntry,
            12,
        ),
    ],
)
def test_parse_mite_entry(tracking, entry_type, minutes):
    # Taken from mite API docs.
    raw = {
        "id": 36159117,
        "minutes": 15,
        "date_at": "2015-10-16",
        "note": "Rework description of authentication process",
        "billable": True,
        "locked": False,
        "revenue": None,
        "hourly_rate": 0,
        "user_id": 211,
        "user_name": "Noah Scott",
        "project_id": 88309,
        "project_name": "API Docs",
        "customer_id": 3213,
        "customer_name": "King Inc.",
        "service_id": 12984,
        "service_name": "Writing",
        "created_at": "2015-10-16T12:39:00+02:00",
        "updated_at": "2015-10-16T12:39:00+02:00",
    }
    raw.update(tracking)
    assert cli.parse_mite_entry(raw) == entry_type(
        project_name="API Docs",
        service_name="Writing",
        customer_name="King Inc.",
        note="Rework description of authentication process",
        minutes=cli.MinuteCount(minutes),
        created_at=datetime(2015, 10, 16, 12, 39, tzinfo=timezone(timedelta(hours=2))),
    )


def test_parse_mite_entry_missing_fields():
    assert cli.parse_mite_entry(
        {"minutes": 5, "created_at": "2015-10-16T12:39:00+02:00"}
    ) == cli.Entry(
        project_name="",
        service_name="",
        customer_name="",
        note="",
        minutes=cli.MinuteCount(5),
        created_at=datetime(2015, 10, 16, 12, 39, tzinfo=timezone(timedelta(hours=2))),
    )


def test_minute_count_addition():
    with pytest.raises(TypeError) as excinfo:
        cli.MinuteCount(3) + 3
    assert (
        str(excinfo.value)
        == "unsupported operand type(s) for +: 'MinuteCount' and 'int'"
    )
