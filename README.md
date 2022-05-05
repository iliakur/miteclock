# miteclock

A command-line for [mite](https://mite.yo.lk/) that gets out of your way!

Do you track time in mite, but wish you could control the clock with a few keystrokes
from the nearest terminal window? Then give miteclock a try!

## Motivation

The goal of this program is to address aspects of using mite that I, as a terminal and
keyboard user, have found inconvenient in daily use:

- Having to search for the mite browser tab or opening a new one when I always have
  terminal windows handy.
- Having to switch between mouse (for projects/services) and keyboard (for notes) to
  create an new entry.
- Surprising narrow-by-typing behavior in the projects/services menus.
- Inflexible support for templates, no ability to compose an entry from pre-defined
  parts.

See [here](#why-yet-another-mite-cli) for more context.

## Installation and Setup

This program is tested with Python versions 3.7-3.10. It doesn't have many dependencies
so it is no big deal to install directly in your system Python environment. It's wiser
though to install it into a dedicated virtualenv and then add a symbolic link to the
executable somewhere in your `PATH`. An even better option is to use the
[pipx](https://github.com/pipxproject/pipx) wrapper which automatically takes care of
these two steps.

Install with a standard pip command:

```sh
pip install miteclock
```

Now you should be able to run the following in your terminal:

```sh
m
```

The first time you run it, it will prompt you for your account information and create a
[TOML](https://github.com/toml-lang/toml) configuration file in your home directory
named `~/.config/miteclock/config.toml`. Then it will show you the help message for the
program. This message and the help for sub-commands should provide enough general
documentation, so the rest of this README is a tutorial to get you started.

## Tutorial

### Controlling the Clock

There are only two commands to interact with the timer: `m start` starts a clock,
`m stop` stops it. That's it, _that simple_. `m stop` is self-explanatory (run it with
`--help`), so here we focus on `m start`.

#### Tracking a New Entry

Let's say your mite account has the following projects:

- ACME &#x2013; Self-healing container deployments
- OCP: ED-209
- CHAZ 2020

In these projects you perform the following services (Dienstleistungen):

- Development
- Regular Maintenance
- Irregular Maintenance
- QA

From your experience with the mite webapp, you know that a time entry has the following
three fields:

1. project
1. service
1. note

What if instead of selecting the project and the service from a drop-down you did so by
pressing just one key? This is much faster, especially if you have more realistic (i.e.
larger) sets of projects and services that you'd have to sift through with the
drop-down.

These keys are known as shortcuts and you can define them in your configuration file.
For our example here, let's create a few mappings from keys to project/service names. We
open our `~/.config/miteclock/config.toml` in a text editor and add the following in the
`[shortcuts]` table:

```toml
[shortcuts]
# Shortcuts for projects.
a = "ACME -- Self-healing container deployments"
o = "OCP: ED-209"
h = "CHAZ 2020"
t = "Team-Internal"
#  Shortcuts for services.
d = "Development"
r = "Regular Maintenance"
i = "Irregular Maintenance"
q = "QA"
c = "Communication/Coordination"
```

Now we can add an activity and start the clock for it with this one command:

```sh
m start a d 'writing some code'
```

The first two arguments to `start` are expanded into "ACME &#x2013; Self-healing
container deployments" and "Development" respectively. The last argument is the note. We
put it in quotes so that it is treated as a single argument.

Note that **order matters** for the expanded items. It **must** be like in the webapp:

1. project
1. service
1. note

If you want to leave any field unspecified, enter an empty string for it. For example if
you're working for "ACME" but haven't narrowed your work down to an exact service or
task, run this:

```sh
m start a '' ''
```

Leaving notes empty and filling them out later is so common, that an empty note can be
completely omitted. We can shorten the command above to:

```sh
m start a ''
```

Another way to avoid writing out a note is to put it into a shortcut definition. This
works well for recurring meetings or tasks where the note stays the same. Let's add some
shortcuts that describe recurring activities for many programmers:

```toml
daily = ["t", "c", "daily stand-up"]
retro = ["t", "c", "retrospective"]
server = ['a', 'r', "regular server maintenance"]
```

Notice how we used the shortcuts we had already defined to create new shortcuts? _It's
shortcuts all the way down!_

These nested shortcuts can span any **consecutive** part of an activity definition. This
is valid&#x2026;

```toml
kickoff = ["c", "kickoff meeting for project"]
```

&#x2026; and can be used with all your projects, for example:

```sh
m start h kickoff  # Tracks kickoff meeting for CHAZ 2020
m start o kickoff  # Tracks kickoff meeting for OCP: ED-209
```

This is also valid:

```toml
acmedev = ["a", "d"]
```

This, however, is invalid:

```toml
invalid = ["a", "some ACME-related note"]
```

#### Resume Tracking an Existing Entry

Often you might have to stop the clock for some activity and then start it back up
later.

If you have clocked in some entries for the day and run `m start` without any arguments,
you will be presented with a list of the activities you recorded for the day paired with
keys you can press to select one of the entries. Note that unlike in the mite webapp,
time entries are sorted by the time they were updated last not by the time when they
were created.

You can skip this menu by passing the `-l` flag (or `--last` if you like typing) which
automatically starts the last entry for which you had a clock running.

You can even run the same exact command a second time, e.g.

```sh
m start a d 'writing some code'
# ... some other commands...
m start a d 'writing some code'
```

There is also `m resume` which is just an alias for `m start -l`.

### Reporting Commands

`m status` will report the current status of the tracker: whether or not the clock is
running and for which entry, which entries have been created today.

`m show` and `m list` show you a list of shortcuts. You can also request a list of
`projects` or `services` by providing these as arguments to the command. Note that
especially the list of projects has known to be long enough that you may want to pipe it
to a file or filter it with `grep`.

## Contributing

If you find a problem with the program, please don't hesitate to open an issue
[here](https://github.com/iliakur/miteclock/issues).

If you want to submit changes, fork this repo, create a branch in your fork that
contains your work, open a pull request against the `master` branch in this repo.

For local development, install the dependencies using
[poetry](https://github.com/python-poetry/poetry).

```sh
poetry install
poetry run pre-commit install
```

Please make sure to add tests for any code changes. Assuming the commands above
succeeded, run this:

```sh
poetry run pytest
```

You can also use `tox` to test your changes against all supported Python versions:

```sh
poetry run tox
```

## Why yet another mite CLI?

There already are almost half a dozen command-line interfaces in several languages
([Ruby](https://github.com/Overbryd/mite.cmd),
[JavaScript](https://github.com/Ephigenia/mite-cli),
[Go](https://github.com/leanovate/mite-go),
[Python](https://github.com/port-zero/mite-cli)). There's even a
[PHP wrapper library](https://github.com/derpaschi/Mitey). What is the need for yet
another cli?

I find that all the existing interfaces provide both too much functionality and too
little. They try to cover all **possible** tasks, exposing all the gory details of the
underlying data along the way. If you regularly import and export time records or manage
projects and services for an account, these tools can be very helpful.

The way most of us use mite though is to start and stop the clock for activities "on the
go" throughout the day. This takes advantage of mite's built-in tracking capabilities. A
lot of the activities are recurring, like check-in meetings with clients or team
members. Moreover, most activities on a given day revolve around a handful of projects
and services.

This program aims to reduce the book-keeping cost of specifying activities. It lets the
user focus on their work while instructing mite to do what it does best: track time. We
deliberately expose a simple interface and deal only in relevant concepts.

## Acknowledgements

This project would not have been possible at all without the folks
[who run mite](https://mite.yo.lk/) making their API accessible. Many thanks to them for
that. I am also grateful to the people who wrote client libraries and cli tools based on
the API. This provided context to my efforts and thus helped me define what I wanted to
focus on.

## Licence

MIT
