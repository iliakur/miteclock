"""The main application entrypoint.

This module puts all the others together and uses click to interact with
the terminal and the user input.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from functools import partial, singledispatch
from itertools import chain, combinations, repeat
from operator import attrgetter, itemgetter
from pathlib import Path
from typing import Any, Callable, Dict, List

import attrs
import click
from attrs import asdict
from click_aliases import ClickAliasedGroup

from miteclock import __name__, __version__
from miteclock.activities import to_time_entry_spec
from miteclock.settings import SettingsLoadError, initialize

echo_error = partial(click.secho, fg="red")
echo_success = partial(click.secho, fg="green")


def build_menu(key_characters, time_entries):
    """Construct menu from which to choose one of `time_entries` using key character.

    Return prompt, default key and mapping from keys to time entries.
    """
    menu_keys = chain(
        key_characters,
        (k * 2 for k in key_characters),
        (a + b for a, b in combinations(key_characters, 2)),
    )
    prompt = ""
    mapping = {}
    for key, entry in zip(menu_keys, time_entries):
        # Also considered presenting notes first then the key.
        # This, however, becomes tricky to align nicely.
        prompt += f"{key}\t{entry['note']}\n"
        mapping[key] = entry
    default_key = key
    prompt += "Select an entry please"
    return prompt, default_key, mapping


def _select_an_entry(menu_keys, entries_today):
    """Keep prompting in a loop until user provides a usable key.

    This should be tested once configuration is easier to pass.
    """
    prompt, default_key, keyed_entries = build_menu(menu_keys, entries_today)
    entry = None
    while entry is None:
        entered_key = click.prompt(prompt, default=default_key)
        try:
            entry = keyed_entries[entered_key]
        except KeyError:
            echo_error(
                f"The key you entered ({entered_key}) is not in the menu. Asking again."
            )
    return entry


@attrs.define(frozen=True, eq=True)
class EntrySpec:
    project_id: int
    service_id: int
    note: str = attrs.field(converter=str.strip)


def _idempotent_entry(entries_today, entry_spec, api):
    """Find time entry id given entries already present and specification for an entry.

    If the entry specification does not match any existing entries, create a new
    time entry and return it, otherwise return matched existing entry.
    """
    entry = EntrySpec(**entry_spec)
    existing_specs = {
        EntrySpec(e["project_id"], e["service_id"], e["note"]): e for e in entries_today
    }
    if entry in existing_specs:
        return existing_specs[entry]
    return api("post", "time_entries", data=json.dumps({"time_entry": asdict(entry)}))[
        "time_entry"
    ]


@click.group(cls=ClickAliasedGroup, invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show miteclock's version.")
@click.pass_context
def main(ctx, version):
    """miteclock

    Lets you start and stop the clock in mite quickly from your terminal.

    Pass the '--help' flag to sub-commands to see how to use them.
    """
    if version:
        click.echo(f"miteclock {__version__}")
        sys.exit(0)
    # During testing ctx.obj is constructed externally and passed in, so it's not None.
    if ctx.obj is None or isinstance(ctx.obj, Path):
        try:
            ctx.obj = initialize(config_root=ctx.obj, prompt=click.prompt)
        except SettingsLoadError as err:
            echo_error(str(err))
            sys.exit(1)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(aliases=["pause", "break"])
@click.pass_obj
def stop(settings):
    """Stop current clock.

    Do nothing if no clock is running.
    """
    stopwatch = settings.mite.stopwatch
    tracked_entry = stopwatch.tracking_time_entry()
    if tracked_entry is None:
        click.echo("No clock is running, nothing to do.")
        sys.exit()
    stopwatch.stop(tracked_entry.id)
    echo_success("Stopping clock!")


@main.command()
@click.option(
    "-l",
    "--last",
    is_flag=True,
    default=False,
    help="Start the last clock. Ignored if an activity is specified",
)
@click.argument("activity", nargs=-1)
@click.pass_obj
def start(settings, last, activity):
    """Start the clock for an activity.

    The activity can be specified as a combination of shortcuts and selector
    patterns as well as raw notes.
    Expanding the shortcuts must result in this form:

    <project_pattern> <service_pattern> <note>

    If there are already time entries present for the day, the activity can be
    left empty. This lets you select from a list of existing time entries the one
    you want to start the clock for. To skip this menu and automatically restart
    the last active clock pass the `-l` flag.
    Note that this flag is ignored if you also specify an activity.
    """
    entries_today = [e["time_entry"] for e in settings.mite.get("daily")]
    if activity:
        projects = [p["project"] for p in settings.mite.get("projects")]
        services = [svc["service"] for svc in settings.mite.get("services")]
        try:
            spec = to_time_entry_spec(activity, settings.shortcuts, projects, services)
        except ValueError as e:
            echo_error(str(e))
            sys.exit(1)
        entry = _idempotent_entry(entries_today, spec, settings.mite.api)
    else:
        if not entries_today:
            click.echo("No entries found for today, please specify an activity.")
            sys.exit()
        entries_today = sorted(entries_today, key=itemgetter("updated_at"))
        if last:
            entry = entries_today[-1]
        else:
            entry = _select_an_entry(settings.menu_keys, entries_today)

    settings.mite.stopwatch.start(entry["id"])
    echo_success("Clock started!")


@main.command()
@click.pass_context
def resume(ctx):
    """An alias for `start -l`."""
    ctx.invoke(start, last=True)


@main.command(aliases=["list"])
@click.argument(
    "what",
    type=click.Choice(["shortcuts", "projects", "services"]),
    default="shortcuts",
)
@click.pass_obj
def show(settings, what):
    """Show list of requested items.

    This is useful to remind you which shortcuts you defined. Listing projects
    or services can help you develop selection patterns. Beware that lists of
    projects and services may get too large for you to scan them by sight. In
    that case you can pipe the results to a file or a search program like grep.
    """
    if what in ["projects", "services"]:
        stuff = [item[what[:-1]]["name"] for item in settings.mite.get(what)]
    else:
        stuff = [f"{k} = {v}" for k, v in settings.shortcuts.items()]
    click.echo("\n".join(stuff))


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh"]), default="bash")
@click.pass_obj
def completion(settings, shell):
    """Set up shell autocompletion.

    Note that this will append to your shell rc file!
    """

    from pathlib import Path
    from shutil import copyfile

    completion_src = Path(__file__).parent / "completions" / shell
    completion_dest = settings.config_dir / f"{shell}_completion"
    copyfile(completion_src, completion_dest)
    # Using tilde instead of resolving the full path is more portable for users who
    # synchronize  their rc files between different machines.
    completion_rc_path = "~" / completion_dest.relative_to(Path.home())
    source_completion = f"source {completion_rc_path}"
    rc_file = Path.home() / f".{shell}rc"
    with rc_file.open(mode="r+") as fh:
        if source_completion in fh.read():
            echo_success("Looks like completions are already present.")
            return
        comment = f"# Added by {__name__}"
        fh.write(f"\n{comment}\n{source_completion}")
    echo_success(f"Success! Added {shell} completion loading to {rc_file}.")


@main.command()
@click.option(
    "-f/-s",
    "--full/--short",
    default=False,
    help="Pass '--full' to display all entries for the day. "
    "By default only the currently tracked entry (if any) is displayed.",
    show_default=True,
)
@click.pass_obj
def status(settings, full):
    """Display current state of mite.

    Tells you whether the clock is running or not. If it's running, shows the
    entry that you are tracking. Can also display all entries for the day.
    """
    entries_today = [
        parse_mite_entry(e["time_entry"]) for e in settings.mite.get("daily")
    ]
    for msg in report_status(entries_today, full):
        click.secho(msg.content, **msg.fmt_keywords)


@attrs.frozen
class Entry:
    project_name: str
    service_name: str
    note: str
    minutes: MinuteCount
    created_at: datetime


def _to_message(e: Entry) -> Message:
    return Message(
        "\n".join(
            (
                f"Project: {e.project_name}",
                f"Service: {e.service_name}",
                f"Note: {e.note}",
                f"Time spent: {e.minutes}",
            )
        )
    )


@attrs.frozen
class TrackedEntry(Entry):
    pass


def parse_mite_entry(raw: Dict[str, Any]) -> Entry:
    if "tracking" in raw:
        entry_type = TrackedEntry
        minutes = raw["tracking"]["minutes"]
    else:
        entry_type = Entry
        minutes = raw["minutes"]
    return entry_type(
        project_name=raw.get("project_name", ""),
        service_name=raw.get("service_name", ""),
        note=raw.get("note", ""),
        minutes=MinuteCount(minutes),
        created_at=datetime.strptime(
            re.sub(r"(\+\d\d)\:(\d\d)$", r"\1\2", raw["created_at"]), "%Y-%m-%dT%X%z"
        ),
    )


@attrs.frozen
class Message:
    content: str
    fmt_keywords: Dict[str, Any] = attrs.field(factory=dict)


EmptyMessage = Message("")


@attrs.frozen
class MinuteCount:
    value: int

    def __str__(self) -> str:
        return "{0}h{1}m".format(*divmod(self.value, 60))

    def __add__(self, other: Any) -> MinuteCount:
        if not isinstance(other, MinuteCount):
            return NotImplemented
        return attrs.evolve(self, value=self.value + other.value)


@attrs.frozen
class _Context:
    order: Callable[[List[Entry]], List[Entry]]
    interpret: Callable[[Entry], Message]
    summarize: Callable[[List[Message]], List[Message]]


def _by_creation_time(entries: List[Entry]) -> List[Entry]:
    return sorted(entries, key=attrgetter("created_at"))


def _full_summary(messages: List[Message]) -> List[Message]:
    return (
        [Message("Entries today:")]
        + list(
            chain.from_iterable(zip(repeat(EmptyMessage), messages)),
        )
        if messages
        else [Message("No entries today.")]
    )


def _short_summary(messages: List[Message]) -> List[Message]:
    return [Message("Below is the entry being tracked.")] + messages if messages else []


@singledispatch
def _short_interpret(e: Entry) -> Message:
    return EmptyMessage


@_short_interpret.register
def _(e: TrackedEntry) -> Message:
    return _to_message(e)


@singledispatch
def _full_intrepret(e: Entry) -> Message:
    return _to_message(e)


@_full_intrepret.register
def _(e: TrackedEntry) -> Message:
    return attrs.evolve(_to_message(e), fmt_keywords={"fg": "green", "bold": True})


def report_status(entries: List[Entry], full: bool) -> List[Message]:
    header = Message("The clock is not running", {"fg": "red", "bold": True})
    total_m = MinuteCount(0)
    ctx = (
        _Context(
            order=_by_creation_time,
            interpret=_full_intrepret,
            summarize=_full_summary,
        )
        if full
        else _Context(
            order=lambda entries: entries,
            interpret=_short_interpret,
            summarize=_short_summary,
        )
    )
    body: List[Message] = []
    for e in ctx.order(entries):
        header = _update_header(e, header)
        body.append(ctx.interpret(e))
        total_m += e.minutes
    body = ctx.summarize([m for m in body if m.content])
    body_padded = [EmptyMessage, *body, EmptyMessage] if body else body
    footer = Message(f"Total time clocked in today: {total_m}", {"bold": True})
    return [header, *body_padded, footer]


@singledispatch
def _update_header(e: Entry, hdr: Message) -> Message:
    return hdr


@_update_header.register
def _(e: TrackedEntry, hdr: Message) -> Message:
    return Message("The clock is running!", {"fg": "green", "bold": True})
