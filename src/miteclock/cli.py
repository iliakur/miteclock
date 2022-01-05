"""The main application entrypoint.

This module puts all the others together and uses click to interact with
the terminal and the user input.
"""
import json
import sys
from functools import partial
from itertools import chain, combinations
from operator import itemgetter

import attrs
import click
from attrs import asdict
from click_aliases import ClickAliasedGroup

from miteclock import __version__
from miteclock.activities import to_time_entry_spec
from miteclock.config import SettingsLoadError, initialize

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

    Pass the `--help` flag to sub-commands to see how to use them.
    """
    if version:
        click.echo(f"miteclock {__version__}")
        sys.exit(0)
    # During testing ctx.obj is constructed externally and passed in, so it's not None.
    if ctx.obj is None:
        try:
            ctx.obj = initialize(click.prompt)
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
    completion_dest = settings.app.config_dir / f"{shell}_completion"
    copyfile(completion_src, completion_dest)
    # Using a tilde notation is more portable for users who sync their
    # rc files between different machines. It's also easier to read.
    completion_rc_path = "~" / completion_dest.relative_to(Path.home())
    source_completion = f"source {completion_rc_path}"
    rc_file = Path.home() / f".{shell}rc"
    with rc_file.open(mode="r+") as fh:
        if source_completion not in fh.read():
            comment = f"# Added by {settings.app.name}"
            fh.write(f"\n{comment}\n{source_completion}")
    echo_success(f"Success! Added {shell} completion loading to {rc_file}.")


@attrs.define
class TimedEntry:
    proj_name: str
    svc_name: str
    note: str
    minutes: int
    tracked: bool = False

    def __str__(self):
        return "\n".join(
            [
                f"Project: {self.proj_name}",
                f"Service: {self.svc_name}",
                f"Note: {self.note}",
                f"Time spent: {_to_hours_and_minutes(self.minutes)}",
            ]
        )


@main.command()
@click.option(
    "-f/-s",
    "--full/--short",
    default=False,
    help="Pass '--full' to display all entries for the day.",
    show_default=True,
)
@click.pass_obj
def status(settings, full):
    """Display current state of mite.

    Tells you whether the clock is running or not. If it's running, shows the
    entry that you are tracking. Can also display all entries for the day.
    """
    entries_today = [e["time_entry"] for e in settings.mite.get("daily")]

    tracker_running = False
    entries_for_display = []
    total_minutes_today = 0
    for e in sorted(entries_today, key=itemgetter("created_at")):
        if "tracking" in e:
            tracker_running = True
            entry_minutes = e["tracking"]["minutes"]
            entries_for_display.append(
                TimedEntry(
                    e["project_name"],
                    e["service_name"],
                    e["note"],
                    entry_minutes,
                    tracked=True,
                )
            )
        else:
            entry_minutes = e["minutes"]
            if full:
                entries_for_display.append(
                    TimedEntry(
                        e["project_name"], e["service_name"], e["note"], entry_minutes
                    )
                )
        total_minutes_today += entry_minutes

    if tracker_running:
        echo_success("The clock is running!", bold=True)
    else:
        echo_error("The clock is not running.", bold=True)

    if full:
        click.echo("Entries today:")
        for timed_e in entries_for_display:
            echo_func = echo_success if timed_e.tracked else click.echo
            echo_func("\n" + str(timed_e))
    elif tracker_running:
        click.echo("Tracking the following entry.")
        click.echo(str(entries_for_display[0]))
    click.secho(
        f"\nTotal time clocked in today: {_to_hours_and_minutes(total_minutes_today)}",
        bold=True,
    )


def _to_hours_and_minutes(minutes):
    return "{0}h{1}m".format(*divmod(minutes, 60))
