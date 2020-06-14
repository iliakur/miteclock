"""The main application entrypoint.

This module puts all the others together and uses click to interact with
the terminal and the user input.
"""
import json
import sys
from collections import namedtuple
from functools import partial
from itertools import chain, combinations
from operator import itemgetter

import click
from click_aliases import ClickAliasedGroup

from miteclock.activities import to_time_entry_spec
from miteclock.config import load_settings

echo_error = partial(click.secho, fg="red")
echo_success = partial(click.secho, fg="green")


def _init_account():
    """Prompt user for account information and return it for config to save."""
    click.echo("Seems like you haven't set up miteclock yet. Let's do that now.")
    account_name = click.prompt(
        "Please provide an account name. This is the first part of your mite URL"
    )
    account_key = click.prompt(
        "Please enter or paste your API key.\n"
        "You can find it in the 'My User'/'Mein Benutzer' tab in mite.\n"
        "If necessary, check the box 'Allow API Access'/'Zugriff Aktivieren'"
    ).strip()
    echo_success("Setup complete!\n\n")
    return account_name, account_key


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
        mapping[key] = entry["id"]
    default_key = key
    prompt += "Select an entry please"
    return prompt, default_key, mapping


def _select_an_entry(menu_keys, entries_today):
    """Keep prompting in a loop until user provides a usable key.

    This should be tested once configuration is easier to pass.
    """
    prompt, default_key, keyed_entries = build_menu(menu_keys, entries_today)
    entry_id = None
    while entry_id is None:
        entered_key = click.prompt(prompt, default=default_key)
        try:
            entry_id = keyed_entries[entered_key]
        except KeyError:
            echo_error(
                f"The key you entered ({entered_key}) is not in the menu. Asking again."
            )
    return entry_id


EntrySpec = namedtuple("EntrySpec", "project_id, service_id, note")


def _idempotent_entry_id(entries_today, entry_spec, api):
    """Find time entry id given entries already present and specification for an entry.

    If the entry specification does not match any existing entries, create a new
    time entry and return its ID, otherwise return ID of matched existing entry.
    """
    entry = EntrySpec(**entry_spec)
    by_data = {
        EntrySpec(e["project_id"], e["service_id"], e["note"]): e["id"]
        for e in entries_today
    }
    entry_id = by_data.get(entry)
    if entry_id is None:
        entry_id = api(
            "post", "time_entries", data=json.dumps({"time_entry": entry_spec})
        )["time_entry"]["id"]
    return entry_id


@click.group(cls=ClickAliasedGroup, invoke_without_command=True)
@click.pass_context
def main(ctx):
    """miteclock

    Lets you start and stop the mite timer quickly from the command line.

    Pass the `--help` flag to sub-commands to see how to use them.
    """
    # During testing ctx.obj is constructed externally and passed in, so it's not None.
    if ctx.obj is None:
        ctx.obj = load_settings(_init_account)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.pass_obj
def stop(settings):
    """Stop current clock.

    Do nothing if no clock is running.
    """
    stopwatch = settings.mite.stopwatch
    tracked_entry = stopwatch.tracking_time_entry()
    if tracked_entry is None:
        click.echo("No timer running, nothing to do.")
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
    The result of expanding the shortcuts must, however, result in this form:

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
        entry_id = _idempotent_entry_id(entries_today, spec, settings.mite.api)
    else:
        if not entries_today:
            click.echo("No entries found for today, please specify an activity.")
            sys.exit()
        entries_today = sorted(entries_today, key=itemgetter("updated_at"))
        if last:
            entry_id = entries_today[-1]["id"]
        else:
            entry_id = _select_an_entry(settings.menu_keys, entries_today)

    settings.mite.stopwatch.start(entry_id)
    echo_success("Timer started!")


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
    """Show a list of requested items (e.g. shortcuts or projects/services).

    This is useful as a reminder of which shortcuts you have defined.
    It can also help developing selection patterns as you can test them out
    on the lists of projects and services.
    Beware that your lists may get too large for you to scan them by sight.
    In that case you can pipe the results to a file or a search program like grep.
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
