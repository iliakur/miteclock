# miteclock

Clock in and out of [mite](https://mite.yo.lk/) within seconds!

Do you like tracking time in mite, but find it more convenient to grab any terminal (or
pop a new one) and type in a few characters rather than rummage through your browser
tabs and click on the same 2 drop-down boxes every time you switch activities throughout
the day? `miteclock` is here to help!

## Installation and Setup

This package should work with Python version 3.6 and higher. It doesn't have many
dependencies so it should not be a huge deal to install directly in your global
environment. Still, it's probably a better idea to create a dedicated virtualenv for it
and then symlink the executable somewhere in your `PATH`. You could also use the
[pipx](https://github.com/pipxproject/pipx) wrapper which automatically takes care of
virtualenv creation.

Whether inside a virtualenv or not, install with a standard pip command:

```sh
pip install miteclock
```

After installing (and symlinking) you should be able to run the following command in
your terminal:

```sh
m
```

The first time you run it, it will prompt you for your account information and create a
[TOML](https://github.com/toml-lang/toml) configuration file in your home directory
named `~/.config/miteclock/config.toml`. Invoking `m` after that will show you the help
message for the program.

### Shell Auto-completion

If you'd like to enable auto-completion for your shell, run this command:

```sh
m completion
```

By default this sets up `bash` completion, but `zsh` is can also be specified. Pass the
`--help` flag to learn more about the command.

## Usage

There are only two core commands: `m start` starts a clock, `m stop` stops it. That's
it, _that simple_. The help message for `m stop` contains all you need to know about
that command, so here we focus on `m start`.

### Tracking a New Entry

Let's say your mite account has the following projects:

- ACME &#x2013; Self-healing container deployments
- OCP: ED-209
- CHAZ 2020

In these projects you perform the following services (Dienstleistungen):

- Development
- Regular Maintenance
- Irregular Maintenance
- QA

  From your experience with the mite webapp, you know that in order to add an entry and
  start the clock for it you need to specify the following three fields:

  - project
  - service
  - note

However, what if instead of selecting the project and the service from a drop-down you
did so by pressing just one key? This is much faster, especially if you have more
realistic (i.e. larger) sets of projects and services that you'd have to sift through
with the drop-down.

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
container deployments" and "Development" respectively. The last argument is the note and
should be quoted to ensure it is interpreted together. Note that the order of the
arguments is currently fixed to keep things simple.

While most activities will likely require you to enter a unique note to describe them,
there are also some recurring appointments and tasks for which the notes don't need to
vary either. Wouldn't it be nice to have shortcuts for those too? Let's add some
shortcuts that describe recurring activities of many programmers:

```toml
daily = ["t", "c", "daily stand-up"]
retro = ["t", "c", "retrospective"]
server = ['a', 'r', "regular server maintenance"]
```

Notice how we used the shortcuts we had already defined to create new shortcuts? Like
they say, _it's shortcuts all the way down_!

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

This is also valid (though not so useful):

```toml
acmedev = ["a", "d"]
```

This, however, is invalid:

```toml
invalid = ["a", "something ACME-related  ¯\_(ツ)_/¯"]
```

### Resume Tracking an Existing Entry

Often you might have to stop the clock for some activity and then start it back up it
later.

If you have clocked in some entries for the day and run `m start` without any arguments,
you will be presented with a list of the activities you recorded for the day paired with
keys you can press to select one of the entries. Note that unlike in the mite webapp,
time entries are sorted by the time they were updated last not by the time when they
were created.

You can skip this menu by passing the `-l` flag (or `--last` if you like typing) which
automatically starts the last entry for which you had a clock running.

### Helper Commands

#### resume

`m resume` is just an alias for `m start -l`.

#### show/list

`m show` and `m list` show you a list of shortcuts. You can also request a list of
`projects` or `services` by providing these as arguments to the command. Note that
especially the list of projects has known to be long enough that you may want to pipe it
to a file or filter it with `grep`.

## Contributing

Very simple in terms of git: fork this repo, create a branch in your fork that contains
your work, open a pull request against the `master` branch in this repo.

For local development, install the dependencies using
[poetry](https://github.com/python-poetry/poetry).

```sh
poetry install
poetry shell
pre-commit install
```

Please make sure to add tests for any code changes.

## Why yet another mite CLI?

There are almost half a dozen command-line interfaces already in several languages
([Ruby](https://github.com/Overbryd/mite.cmd),
[JavaScript](https://github.com/Ephigenia/mite-cli),
[Go](https://github.com/leanovate/mite-go),
[Python](https://github.com/port-zero/mite-cli)). There's even a
[PHP wrapper library](https://github.com/derpaschi/Mitey). What is the need for yet
another cli?

In my opinion all the existing interfaces provide both too much functionality and too
little. They try to cover the complete range of tasks that **can** be performed with
mite and expose all the gory details of the data, like the IDs of the objects involved.
Indeed if you regularly have to import and export time records, or if your workflow
includes managing projects and services for an account, these tools can arguably help
you with your work.

However the way I see mite used most often involves starting and stopping the clock for
activities "on the go" throughout the day. Quite a few of these activities are
recurring, like check-in meetings with clients or team members. Moreover, most
activities that a particular person specifies on a given day tend to revolve around just
a handful of projects and services. Lastly, the active mite users I know seem to clock
in and out throughout their day rather than enter all their time entries already with
times attached, thus taking advantage of mite's built-in tracking capabilities.

This program aims to reduce the book-keeping cost of specifying activities and let the
user focus on their work while instructing mite to do what it does best: track time. It
deliberately exposes a very simple interface and deals in abstractions relevant
primarily to someone only using mite to track their time.

## Acknowledgements

This project would not have been possible at all without the folks
[who run mite](https://mite.yo.lk/) making their API accessible. Many thanks to them for
that. I am also grateful to the many people who wrote client libraries and cli tools
based on the API. This provided context to my efforts and thus helped me define what I
wanted to focus them on.

## Licence

MIT
