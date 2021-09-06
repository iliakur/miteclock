import json
from copy import deepcopy
from functools import partial

import pytest
from click.testing import CliRunner

from miteclock import __version__, cli
from miteclock.config import MiteSettings, Settings
from miteclock.mite import StopWatch, TrackedTimeEntry


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
def application_context(mite_server, shortcuts):
    api = FakeApi(mite_server)

    return (
        Settings(
            mite=MiteSettings(
                api=api, get=partial(api, "get"), stopwatch=StopWatch(api)
            ),
            account="test",
            menu_keys="asdfjkl;",
            shortcuts=shortcuts,
        ),
        mite_server,
    )


def test_version():
    """`--version` prints application version and exits with code 0."""
    result = CliRunner().invoke(cli.main, "--version")
    assert result.exit_code == 0
    assert f"miteclock {__version__}" in result.output


def test_help_message():
    """Invoking without any args and with `--help` should show help message."""
    no_args_passed = CliRunner().invoke(cli.main)
    assert no_args_passed.exit_code == 0

    help_flag_passed = CliRunner().invoke(cli.main, "--help")
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
    settings, mite_server = application_context

    result = CliRunner().invoke(cli.main, "show " + item_type, obj=settings)

    assert result.exit_code == 0
    assert result.output == output
