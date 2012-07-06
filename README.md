
Overview
========

TTrack is a very simple command-line time-tracking tool written in Python.
It allows you to create tasks and then track time spent working on them.
Aggregate reports of the time spent on tasks can be produced, and arbitrary
tags can be applied to tasks for flexible categorisation.

> **NOTE:** TTrack was written for use on Unix-like platforms, and appears to
> work on both Linux and OSX. It hasn't been tested on Windows at all,
> although I would hope that any compatibility issues would be minor.


Installation
------------

Python 2.5 or later should be sufficient to execute the scripts. If the
parsedatetime library (http://code.google.com/p/parsedatetime/) then this will
be used for more friendly date and time parsing.

Just ensure tracklib.py is available on the PYTHONPATH and run ttrack.py.

When first run, an SQLite database is created in your home directory in a file
called `.timetrackdb`. It's currently not possible to change the name used
for this file, although it would be a simple code change to do so. This file
contains the entire database - removing it will lose all data.

Additionally, the file `.timetrackhistory` is created in the same place to
store command history.


Task Tracking Basics
--------------------

When executed with no arguments, TTrack enters interactive mode. Commands
can be entered at the prompt, and tab-completion should work for command
names and most arguments.

The `help` command can be used to list available commands, providing a
command as an argument provides more detailed help for that command. For
example, try `help create`.

TTrack works on the basis of "tasks", which are referred to with a simple
name. I suggest keeping names lower-case and avoiding spaces, but you can
choose any names you wish. If you wish to include spaces in any name, you'll
need to surround it with double-quotes at the TTrack prompt (or use suitable
shell quoting if using command-line arguments).

Let's run through some basic workflow as an example - don't worry, you can
easily delete your `~/.timetrackdb` file to erase everything you do here.

First, create some tasks:

    create task project1
    create task project2
    create task bug1234

You can now list the tasks that you've created:

    show tasks

You can use the `start` command to start work on a task:

    start project2

If you omit the task name, the most recently-created task will be assumed.

The `status` command shows you what you're working on now, and what you were
working on previous to that, if anything:

    status

Whilst working on a task, you can add "diary" entries to it, which are
intended to be small reminders of your progress. To do this, simply use the
`diary` command, where the remainder of the line becomes your diary entry:

    diary Finished planning on Project 2, next I need to implement phase 1.

Feel free to add more diary entries. Each entry will be marked with the time
at which you add it and the current task that was in effect at that time.
You can display your diary entries for this task with:

    task project2 diary

If you start working on a new task, the old task is automatically stopped:

    start project1

If you use the `status` command now you should see that the current task has
changed and the previous task is now filled in. You can switch between tasks
arbitrarily, and TTrack always allocates your time against the current task.

Since work on tasks can often be interrupted, there is a command which allows
you to easily revert to the previously active task:

    resume

If working on a task, this command will switch you back to the previous task.
This is simply a convenience for the equivalent `start` command, to avoid you
having to type the task name again.

You can also stop allocating your time to anything - for example, when it's
time to leave the office or go to bed:

    stop

If you execute `resume` whilst working on no task, it will restart whatever
task was most recently current.


Tags and Reports
----------------

Tasks can be organised by using tags. A tag is a name which can be applied to
any set of tasks, and reports can be generated based on these. Tags can be
used as categories, but note that a task can have any number of tags applied
to it at once.

The links between tags and tasks can be changed at any point, and this change
is applied retrospectively - in other words, reporting is always based on the
current state of tags, not the state as it was when the tasks were current.
This can be powerful, as it means that you can start recording task time
quickly without worrying too much about how to report on it, and then assign
and change tags later for reporting purposes.

Continuing the example above, create some tags and add them to tasks:

    create tag projects
    create tag commercial
    task project1 tag projects
    task project2 tag projects
    task project2 tag commercial

If you wish to remove a tag at a later stage, you can use `task X untag Y` in
the same way.

As a shortcut, when creating a task you can optionally specify a list of one
or more tags after the task name, which saves additional `task` commands to
add them:

    create task project3 projects commercial

Now you've created some tasks and tags, and allocated some time to them,
it's time to learn how to generate reports based on that time. Reports are
all generated with the `summary` command. It's syntax is a little
complicated, but the examples below should help get you started.

Firstly, reports can be generated split by task or split by tag - hence, the
first argument is either `task` or `tag` to indicate which you want.

The second argument specifies the type of report that you can generate - there
are currently four types:

* `time`: This produces a report of the time spent on each entry.
* `switches`: Shows the number of times the specified task interrupted others.
* `diary`: Shows all diary entries.
* `entries`: Shows raw task times.

Following the report type, the period over which the report should be run is
specified - this can be `day`, `week` or `month`. If no other arguments are
specified, the report for the current day/week/month is displayed. Otherwise,
the next argument can be a number indicating how many days/weeks/months ago
the report should be run. Specifying 0 indicates the current period (the
default if the value is omitted), 1 indicates the previous day/week/month,
2 indicates the period before that, etc.

Finally, if splitting by task (only), a the keyword `tag` followed by a tag
name can be specified at the end of the command. If so, the list of tasks
displayed will be filtered to be those with the specified tag applied.

In case you're thinking that all sounds a bit too complicated, here are some
simple examples which probably cover most of what you need, followed by an
explanation of what will be displayed.

    summary task time week

Display a summary of the time spent on each task so far this week.

    summary tag time day 1

Display a summary of the time spent yesterday on tasks in each tag.

    summary task switches month 1

Display the number of times each task interrupted another one in the previous
month.

    summary task diary month tag projects

Display diary entries recorded so far this month for all tasks with tag
`projects`.

Note that the `entries` summary mode is typically used when fixing up
incorrectly recorded times, as it's the only way of determing the unique
ID of a time entry in the database. This is a more advanced usage which isn't
covered in this basic tutorial.

The `switches` report probably needs a little more explanation. The intention
is to allow you to record interruptions (or "context switches") you suffer
during the day and get some idea of how frequently your flow is interrupted.
For this to work you'll have to create tasks to track all the things which
disturb you - for example, if you are interrupted by calls from customers,
you could create a task `customersupport` to track this.

To count as a context switch and be included in the totals for the `switches`
report, a task must be different to the previous task and start less than a
minute after the first one ended. When reporting by tag rather than task,
the definition is changed to the new task must have at least one tag which
the old task does not. For example, if two different tasks both have only the
`coding` tag then switching between them will count as a context switch in a
`task` report, but not in a `tag` report.


Advanced Usage
--------------

Many of the commands have additional arguments to fix problems when you've
forgotten to start or stop tasks at the correct time - these allow the time
at which the event occurs to be overridden. For example, if you leave work on
Friday and forget to execute `stop`, you can do so on Monday and provide a
timestamp on Friday to the `stop` command.

Unfortunately I haven't had chance to document these more advanced usages
yet, but the `help` command may give you the details you need. TTrack tries
its best to prevent you creating entries which overlap, on the assumption
that you can only be doing one task at a time, but it pays to be a little
cautious if you value the records you have in the database so far. If in
doubt, you can take a copy of the `~/.timetrackdb` file before playing
around, and re-instate the old data by simply copying it back into place
if things seem to be broken.


Contact
-------

Hopefully that should give you enough to get started. If you have any
questions, problems or requests, please get in touch with me at
andy@andy-pearce.com.


