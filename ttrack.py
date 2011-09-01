#!/usr/bin/python

import atexit
import cmd
import datetime
import logging
import optparse
import os
import readline
import shlex
import sys
import textwrap

import tracklib



VERSION = "1.0"
APP_NAME = "TimeTrack"
BANNER = "\n%s %s\n\nType 'help' to list commands.\n" % (APP_NAME, VERSION)
HISTORY_FILE = os.path.expanduser("~/.timetrackhistory")



def get_option_parser():

    usage = "Usage: %prog [options] [<cmd>]"
    parser = optparse.OptionParser(usage=usage,
                                   version="%s %s" % (APP_NAME, VERSION))
    parser.add_option("-d", "--debug", dest="debug", action="store_true",
                      help="enable debug output on stderr")
    parser.add_option("-H", "--skip-history", dest="skip_history",
                      action="store_true",
                      help="don't try to read/write command history")
    parser.set_defaults(debug=False, skip_history=False)
    return parser



class ApplicationError(Exception):
    pass



def format_duration(secs):
    if secs < 60:
        return "%d sec%s" % (secs, "" if secs == 1 else "s")
    elif secs < 3600:
        return "%d min%s" % (secs // 60, "" if (secs//60)==1 else "s")
    else:
        return ("%d hour%s %d min%s" % (secs // 3600,
                                        "" if (secs//3600)==1 else "s",
                                        (secs // 60) % 60,
                                        "" if ((secs//60)%60)==1 else "s"))



def format_duration_since_datetime(dt):
    now = datetime.datetime.now()
    delta = now - dt
    return format_duration(delta.days * 3600 * 24 + delta.seconds)



def format_datetime(dt):
    now = datetime.datetime.now()
    if now.date() == dt.date():
        return dt.strftime("%H:%M")
    elif (now - dt).days < 5:
        return dt.strftime("%a %H:%M")
    else:
        return dt.strftime("%a %b %d %H:%M %Y")



def display_summary(summary_dict, format_func):
    """Displays a summary object as a list."""

    max_item_len = len("TOTAL")
    total = None
    item_strs = []
    for item, value in sorted(summary_dict.items()):
        max_item_len = max(max_item_len, len(item))
        item_strs.append((item, format_func(value), value))
        if total is None:
            total = value
        else:
            total += value
    if total is None:
        print "No activity to summarise.\n"
        return
    for item, value, raw in item_strs:
        padding = max_item_len - len(item) + 2
        percent = int(round((raw * 100.0) / total, 0)) if total else 0
        print "%s %s [%2d%%] %s" % (item, "." * padding, percent, value)
    padding = max_item_len - len("TOTAL") + 2
    if total is not None:
        print "\nTOTAL %s...... %s\n" % ("." * padding, format_func(total))



def display_diary(diary):
    """Displays list of diary entries by task."""

    print
    for name, entries in diary.items():
        if not entries:
            continue
        print "+----[ %s ]----" % (name,)
        print "|"
        for entry_time, entry_task, entry_desc in entries:
            date_str = format_datetime(entry_time)
            print "| +---- %s ----[ %s ]----" % (date_str, entry_task)
            print textwrap.fill(entry_desc, initial_indent="| | ",
                                subsequent_indent="| | ")
            print "|"
        print



class CommandHandler(cmd.Cmd):

    def __init__(self, logger):
        self.logger = logger
        self.db = tracklib.TimeTrackDB(self.logger)
        readline.set_completer_delims(" \t\n")
        cmd.Cmd.__init__(self)
        self.identchars += "-"
        self.prompt = "TimeTrack>>> "


    def _complete_task(self, text):
        return [i for i in self.db.tasks if i.startswith(text)]


    def _complete_tag(self, text):
        return [i for i in self.db.tags if i.startswith(text)]


    def _complete_list(self, text, candidates):
        return [i for i in candidates if i.startswith(text)]


    def _complete_all_chars(self, complete_func, text, line, begidx, endidx):
        items = shlex.split(line[:endidx])
        if not items or len(text) >= len(items[-1]):
            prefix = text
        else:
            prefix = items[-1]
        candidates = complete_func(prefix)
        if prefix == text:
            return candidates
        else:
            offset = len(prefix) - len(text)
            print "<<<%r>>>" % ([i[offset:] for i in candidates],)
            return [i[offset:] for i in candidates]


    def complete_create(self, text, line, begidx, endidx):
        items = shlex.split(line[:begidx])
        if len(items) == 1:
            return self._complete_list(text, ("tag", "task"))
        elif len(items) > 2 and items[1] == "task":
            return self._complete_tag(text)
        else:
            return []


    def do_create(self, args):
        """
create (tag <name> | task <name> [<tag> [...]]) - create new tag or task.

When creating a task, an optional list of one or more tags may be specified
to apply those tags to the new task without requiring other 'task' commands.
"""

        items = shlex.split(args)
        if len(items) < 2:
            self.logger.error("create cmd takes at least two arguments")
            return
        if items[0] not in ("task", "tag"):
            self.logger.error("create cmd takes 'task' or 'tag' as first arg")
            return
        if not items[1]:
            self.logger.error("name invalid")
            return
        if items[0] != "task" and len(items) > 2:
            self.logger.error("may specify tags only when creating tasks")
            return

        try:
            if items[0] == "task":
                self.db.tasks.add(items[1])
                print "Created task '%s'" % (items[1],)
                for tag in items[2:]:
                    self.db.add_task_tag(items[1], tag)
                    print "Tagged task '%s' with '%s'" % (items[1], tag)
            elif items[0] == "tag":
                self.db.tags.add(items[1])
                print "Created tag '%s'" % (items[1],)
        except tracklib.TimeTrackError, e:
            self.logger.error("create error: %s", e)


    def complete_delete(self, text, line, begidx, endidx):
        items = shlex.split(line[:begidx])
        if len(items) == 1:
            return ["task", "tag"]
        elif len(items) == 2:
            if items[1] == "task":
                return self._complete_task(text)
            elif items[1] == "tag":
                return self._complete_tag(text)
        return []


    def do_delete(self, args):
        """
delete (task|tag) <name> - delete and existing tag or task.

WARNING: Deleting a tag will remove it from all tasks. Deleting a
         task will also remove associated diary and log entries.
"""

        items = shlex.split(args)
        if len(items) != 2:
            self.logger.error("delete cmd takes two arguments")
            return
        if items[0] not in ("task", "tag"):
            self.logger.error("delete cmd takes 'task' or 'tag' as first arg")
            return

        try:
            if items[0] == "task":
                self.db.tasks.discard(items[1])
            elif items[0] == "tag":
                self.db.tags.discard(items[1])
            print "Deleted %s '%s'" % (items[0], items[1])
        except tracklib.TimeTrackError, e:
            self.logger.error("delete error: %s", e)


    def do_diary(self, args):
        """
diary <entry> - add a new diary entry to the current task.
"""

        args = args.strip()
        if not args:
            self.logger.error("diary cmd requires entry as argument")

        try:
            task = self.db.get_current_task()
            if task is None:
                self.logger.error("no current task to add diary entry")
                return
            self.db.add_diary_entry(args)
            print "Entry added to task '%s'" % (task,)
        except tracklib.TimeTrackError, e:
            self.logger.error("diary error: %s", e)


    def complete_show(self, text, line, begidx, endidx):
        if line[:begidx].strip() == "show":
            return self._complete_list(text, ("tasks", "tags"))
        else:
            return []


    def complete_rename(self, text, line, begidx, endidx):
        items = shlex.split(line[:begidx])
        if len(items) == 1:
            return self._complete_list(text, ("task", "tag"))
        elif len(items) == 2:
            if items[1] == "task":
                return self._complete_task(text)
            elif items[0] == "tag":
                return self._complete_tag(text)
            else:
                return []
        else:
            return []


    def do_rename(self, args):
        """
rename (task|tag) <old> <new> - changes the name of an existing task or tag.
"""

        items = shlex.split(args)
        if len(items) != 3:
            self.logger.error("rename cmd takes three arguments")
            return
        if items[0] not in ("task", "tag"):
            self.logger.error("rename cmd takes task/tag as first argument")
            return
        try:
            if items[0] == "tag":
                self.db.tags.rename(items[1], items[2])
                print "Tag '%s' renamed to '%s'" % (items[1], items[2])
            else:
                self.db.tasks.rename(items[1], items[2])
                print "Task '%s' renamed to '%s'" % (items[1], items[2])
        except KeyError, e:
            self.logger.error("no such tag/task (%s)", e)
        except tracklib.TimeTrackError, e:
            self.logger.error("rename error: %s", e)


    def do_resume(self, args):
        """
resume - switch to previously-running task.

If there is no current task, this command switches to the most recently
active task. If there is a currently active task, this command switches
to the most recently active task which is different to the current.
This can be used to start work on a task again after a period of
inactivity, or to resume work on something after an interruption.
"""

        if args.strip():
            self.logger.error("resume cmd takes no arguments")
            return
        try:
            prev = self.db.get_previous_task()
            if prev is None:
                self.logger.error("no previous task to resume")
                return
            self.db.start_task(prev)
            print "Resumed task '%s'" % (prev,)

        except tracklib.TimeTrackError, e:
            self.logger.error("status error: %s", e)


    def do_show(self, args):
        """
show (tasks|tags) - display a list of available tasks or tags.
"""

        items = shlex.split(args)
        if len(items) != 1:
            self.logger.error("show cmd takes a single argument")
            return
        if items[0] not in ("tasks", "tags"):
            self.logger.error("show cmd takes 'tasks' or 'tags' as first arg")
            return

        try:
            if items[0] == "tasks":
                print "Tasks:"
                for task in self.db.tasks:
                    tags = self.db.get_task_tags(task)
                    if tags:
                        print "  %s (%s)" % (task, ", ".join(tags))
                    else:
                        print "  %s" % (task,)
            else:
                print "Tags:"
                for tag in self.db.tags:
                    print "  %s" % (tag,)
        except tracklib.TimeTrackError, e:
            self.logger.error("show error: %s", e)


    def complete_start(self, text, line, begidx, endidx):
        return self._complete_task(text)


    def do_start(self, args):
        """
start <task> - starts timer on an already defined task.
"""

        items = shlex.split(args)
        if len(items) != 1:
            self.logger.error("start cmd takes single argument")
            return
        try:
            self.db.start_task(items[0])
            print "Started task '%s'" % (items[0],)
        except KeyError, e:
            self.logger.error("no such task (%s)" % (e,))
        except tracklib.TimeTrackError, e:
            self.logger.error("start error: %s", e)


    def do_status(self, args):
        """
status - display current task and time spent on it.
"""

        if args.strip():
            self.logger.error("status cmd takes no arguments")
            return
        try:
            prev = self.db.get_previous_task()
            if prev is None:
                print "No previous task."
            else:
                print "Previous task: %s" % (prev,)
            task = self.db.get_current_task()
            if task is None:
                print "No current task."
                return
            start = self.db.get_current_task_start()
            start_str = format_datetime(start)
            dur_str = format_duration_since_datetime(start)
            print "Current task: %s" % (task,)
            print "Started: %s (%s ago)" % (start_str, dur_str)

        except tracklib.TimeTrackError, e:
            self.logger.error("status error: %s", e)


    def do_stop(self, args):
        """
stop - stops timer on current task.
"""

        if args.strip():
            self.logger.error("stop cmd takes no arguments")
            return
        try:
            print "Stopping task '%s'" % (self.db.get_current_task(),)
            self.db.stop_task()
        except tracklib.TimeTrackError, e:
            self.logger.error("stop error: %s", e)


    def complete_summary(self, text, line, begidx, endidx):
        items = shlex.split(line[:begidx])
        if len(items) == 1:
            return self._complete_list(text, ("tag", "task"))
        elif len(items) == 2:
            return self._complete_list(text, ("time", "switches", "diary"))
        elif len(items) == 3:
            return self._complete_list(text, ("day", "week", "month"))
        elif len(items) == 4:
            return self._complete_list(text, ("this", "now", "current", "tag"))
        elif len(items) == 5:
            if items[-1] == "tag":
                return self._complete_tag(text)
            else:
                return self._complete_list(text, ("tag",))
        elif len(items) == 6 and items[-1] == "tag":
            return self._complete_tag(text)
        else:
            return []


    def do_summary(self, args):
        """
summary (tag|task) (time|switches|diary) (day|week|month)
        [<period>] [tag <tag>]

Shows various summary information in tabular form. The first argument sets
whether totals are split by task or tag. The second argument sets whether
the values shown are total time or context switches into the tag/task.
The third argument specifies the period over which the results should be
accumulated and the fourth specifies how many such periods to go back.
For example, specifying "week" with a <period> of 0 shows the summary for
the current (partial) week, whereas a <period> of 1 shows the previous week.
If the <period> is ommitted a value of 0 is assumed. Synonyms like "current"
are also accepted.

If the optional additional "tag" argument is specified (either in place of
or after a <period> argument) then it must be followed by the name of a
tag. This will filter results so that only tasks with the specified tag
are counted towards the total. This is only valid when summarising by task.
"""
        items = shlex.split(args)
        if len(items) not in (3, 4, 5, 6):
            self.logger.error("summary cmd requires 3-6 arguments")
            return
        if items[0] not in ("tag", "task"):
            self.logger.error("summary cmd takes tag/task as first arg")
            return
        if items[1] not in ("time", "switches", "diary"):
            self.logger.error("summary cmd takes time/switches/diary"
                              " as second arg")
            return
        if items[2] not in ("day", "week", "month"):
            self.logger.error("unsupported period %r for summary cmd", items[3])
            return
        filter_tag = None
        if len(items) < 4:
            period = 0
        else:
            if items[3] == "tag":
                if len(items) < 5:
                    self.logger.error("no tag specified to filter")
                    return
                else:
                    filter_tag = items[4]
                    period = 0
            else:
                if items[3] in ("this", "now", "current"):
                    period = 0
                else:
                    try:
                        period = int(items[3])
                    except ValueError:
                        self.logger.error("summary cmd takes int as fourth arg")
                        return
                if len(items) > 4:
                    if items[4] != "tag":
                        self.logger.error("unrecognised arg '%s'", items[4])
                        return
                    if len(items) < 6:
                        self.logger.error("no tag specified to filter")
                        return
                    filter_tag = items[5]
        if filter_tag is not None and items[0] != "task":
            self.logger.error("filtering by tag only valid when summarising"
                              " by task")
            return

        if period == 0:
            if items[2] == "day":
                period_name = "today"
            else:
                period_name = "this %s" % (items[2],)
        elif period == 1:
            if items[2] == "day":
                period_name = "yesterday"
            else:
                period_name = "last %s" % (items[2],)
        else:
            period_name = "%d %ss ago" % (period, items[2])

        try:
            tags_arg = set((filter_tag,)) if filter_tag is not None else None
            if items[0] == "tag":
                summary_obj = tracklib.TagSummaryGenerator()
            else:
                summary_obj = tracklib.TaskSummaryGenerator(tags=tags_arg)
            tracklib.get_summary_for_period(self.db, summary_obj, items[2],
                                            period)
            if items[1] == "time":
                print "\nTime spent per %s %s:\n" % (items[0], period_name)
                display_summary(summary_obj.total_time, format_duration)
            elif items[1] == "switches":
                print "\nContext switches per %s %s:\n" % (items[0],
                                                           period_name)
                display_summary(summary_obj.switches, str)
            else:
                print "\nDiary entries by %s %s:\n" % (items[0], period_name)
                display_diary(summary_obj.diary_entries)
        except tracklib.TimeTrackError, e:
            self.logger.error("summary error: %s", e)


    def complete_task(self, text, line, begidx, endidx):
        if len(shlex.split(line[:begidx])) == 1:
            return self._complete_task(text)
        elif len(shlex.split(line[:begidx])) == 2:
            return self._complete_list(text, ("tag", "untag"))
        elif len(shlex.split(line[:begidx])) == 3:
            return self._complete_tag(text)
        else:
            return []


    def do_task(self, args):
        """
task <task> (tag|untag) <tag> - adds or removes a tag from a task.
"""

        items = shlex.split(args)
        if len(items) != 3:
            self.logger.error("task cmd takes three arguments")
            return
        if items[1] not in ("tag", "untag"):
            self.logger.error("task cmd takes tag/untag as second argument")
            return
        try:
            if items[1] == "tag":
                self.db.add_task_tag(items[0], items[2])
                print "Tagged task '%s' with '%s'" % (items[0], items[2])
            else:
                self.db.remove_task_tag(items[0], items[2])
                print "Removed tag '%s' from task '%s'" % (items[2], items[0])
        except KeyError, e:
            self.logger.error("no such tag/task (%s)", e)
        except tracklib.TimeTrackError, e:
            self.logger.error("tag error: %s", e)


    def do_exit(self, args):
        """
Exit the application.
"""
        return 1


    def do_EOF(self, args):
        """
Exit the application.
"""
        print "exit"
        return self.do_exit(args)


    def emptyline(self):
        """Do nothing on an empty line."""
        return



def get_stderr_logger(app_name, level=logging.WARNING):

    logger = logging.getLogger(app_name)
    stderr_handler = logging.StreamHandler()
    stderr_formatter = logging.Formatter("%(name)s: %(levelname)s -"
                                         " %(message)s")
    stderr_handler.setFormatter(stderr_formatter)
    stderr_handler.setLevel(level)
    logger.addHandler(stderr_handler)

    # Logger accepts all messages, and relies on handlers to set their
    # own thresholds.
    logger.setLevel(1)

    return logger



def main(argv):
    """Main entrypoint."""

    # Parse command-line arguments
    parser = get_option_parser()
    (options, args) = parser.parse_args(argv[1:])

    if options.debug:
        logger = get_stderr_logger("ttrack", logging.DEBUG)
    else:
        logger = get_stderr_logger("ttrack")

    # If not skipping history, read command history file (if any) and
    # register an atexit handler to write it on termination.
    if not options.skip_history:
        atexit.register(readline.write_history_file, HISTORY_FILE)
        try:
            readline.read_history_file(HISTORY_FILE)
        except IOError:
            pass

    try:
        interpreter = CommandHandler(logger)
        if args:
            cmdline = []
            for arg in args:
                if " " in arg:
                    cmdline.append('"%s"' % (arg,))
                else:
                    cmdline.append(arg)
            interpreter.onecmd(" ".join(cmdline))
        else:
            first_time = True
            while True:
                try:
                    if first_time:
                        first_time = False
                        interpreter.cmdloop(BANNER)
                    else:
                        interpreter.cmdloop("")
                    break
                except KeyboardInterrupt:
                    print
                    print "(To quit use the 'exit' command or CTRL+D)"

    except ApplicationError, e:
        if logger is not None:
            logger.error(e)
        return 1

    except Exception, e:
        if logger is not None:
            logger.critical("caught exception: %s" % e, exc_info=True)
        return 1

    return 0



if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    finally:
        logging.shutdown()

