
import bisect
import cPickle
import collections
from datetime import datetime, timedelta
import os
import sqlite3
import time


__version__ = "1.0.0"



class TimeTrackError(Exception):
    pass



class TiedContainer(object):
    """Mixin class to add shared methods for tied containers."""

    def __init__(self, logger, conn, table):
        self.logger = logger
        self.conn = conn
        self.table = table


    def __len__(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM %s" % (self.table,))
        return int(cur.fetchone()[0])


    def __iter__(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM %s" % (self.table,))
        return (i[0] for i in cur)


    def __contains__(self, item):
        try:
            self.get_id(item)
            return True
        except KeyError:
            return False


    def get_id(self, item):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM %s WHERE name LIKE ?" % (self.table,),
                    (item,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(item)
        elif cur.fetchone() is not None:
            raise KeyError("ambiguous: %r" % (item,))
        return row[0]


    def rename(self, old, new):
        try:
            self.get_id(new)
            raise TimeTrackError("new name '%s' already exists" % (new,))
        except KeyError:
            pass
        row_id = self.get_id(old)
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("UPDATE %s SET name=? WHERE id=?" % (self.table,),
                        (new, row_id))



class TiedDict(TiedContainer, collections.MutableMapping):
    """Dict interface to info tags."""

    def __init__(self, logger, conn, table):
        TiedContainer.__init__(self, logger, conn, table)


    def __getitem__(self, item):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM %s WHERE name LIKE ?" % (self.table,),
                    (item,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(item)
        elif cur.fetchone() is not None:
            raise KeyError("ambiguous: %r" % (item,))
        return cPickle.loads(row[0].encode("utf8"))


    def __setitem__(self, item, value):
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("INSERT OR REPLACE INTO %s (name, value) VALUES (?, ?)"
                        % (self.table,), (item, cPickle.dumps(value)))


    def __delitem__(self, item):
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("DELETE FROM %s WHERE name LIKE ?" % (self.table,), 
                        (item,))


class TiedSet(TiedContainer, collections.MutableSet):
    """Set interface to tags and tasks."""

    def __init__(self, logger, conn, base_type):
        TiedContainer.__init__(self, logger, conn, base_type + "s")
        self.base_type = base_type


    def add(self, item):
        if self.__contains__(item):
            return
        cur = self.conn.cursor()
        try:
            with self.conn:
                cur.execute("INSERT INTO %s (name) VALUES (?)" % (self.table,),
                            (item,))
        except sqlite3.IntegrityError:
            pass


    def discard(self, item):
        cur = self.conn.cursor()
        try:
            del_id = self.get_id(item)
        except KeyError:
            # If the item doesn't exist there's nothing else to do.
            return

        with self.conn:

            # Remove any entries from tagmappings which refer to this.
            cur.execute("DELETE FROM tagmappings WHERE %s=?" %
                        (self.base_type,), (del_id,))

            # For tasks, remove any other entries which refer to it.
            if self.base_type == "task":
                cur.execute("DELETE FROM tasklog WHERE task=?", (del_id,))
                cur.execute("DELETE FROM diary WHERE task=?", (del_id,))
                cur.execute("DELETE FROM todos WHERE task=?", (del_id,))

            # Remove the row itself.
            cur.execute("DELETE FROM %s WHERE id=?" % (self.table,), (del_id,))



def create_tracklib_schema(logger, conn):

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = set(row[0] for row in cur)

    with conn:

        # Schema v1 (move to v2 only for incompatible changes).
        if "tasks" not in tables:
            cur.execute("CREATE TABLE tasks ("
                        " id INTEGER PRIMARY KEY,"
                        " name TEXT UNIQUE NOT NULL)")
        if "tags" not in tables:
            cur.execute("CREATE TABLE tags ("
                        " id INTEGER PRIMARY KEY,"
                        " name TEXT UNIQUE NOT NULL)")
        if "tasklog" not in tables:
            cur.execute("CREATE TABLE tasklog ("
                        " id INTEGER PRIMARY KEY,"
                        " task INTEGER NOT NULL,"
                        " start INTEGER NOT NULL,"
                        " end INTEGER,"
                        " FOREIGN KEY (task) REFERENCES tasks(id))")
        if "diary" not in tables:
            cur.execute("CREATE TABLE diary ("
                        " id INTEGER PRIMARY KEY,"
                        " task INTEGER NOT NULL,"
                        " description TEXT NOT NULL,"
                        " time INTEGER NOT NULL,"
                        " FOREIGN KEY (task) REFERENCES tasks(id))")
        if "tagmappings" not in tables:
            cur.execute("CREATE TABLE tagmappings ("
                        " id INTEGER PRIMARY KEY,"
                        " task INTEGER NOT NULL,"
                        " tag INTEGER NOT NULL,"
                        " UNIQUE (task, tag),"
                        " FOREIGN KEY (task) REFERENCES tasks(id),"
                        " FOREIGN KEY (tag) REFERENCES tags(id))")
        if "todos" not in tables:
            cur.execute("CREATE TABLE todos ("
                        " id INTEGER PRIMARY KEY,"
                        " task INTEGER NOT NULL,"
                        " description TEXT NOT NULL,"
                        " added INTEGER NOT NULL,"
                        " done INTEGER NOT NULL,"
                        " FOREIGN KEY (task) REFERENCES tasks(id))")
        if "info" not in tables:
            cur.execute("CREATE TABLE info ("
                        " id INTEGER PRIMARY KEY,"
                        " name TEXT UNIQUE NOT NULL,"
                        " value TEXT)")
            cur.execute("INSERT INTO info (name, value) VALUES (?, ?)",
                        ("version", cPickle.dumps(1)))



class TaskLogEntry(object):
    """Reresents a single task entry.

    Most attributes are read-only (although this is not enforced), but the
    start and end attributes may be modified and this causes the database to
    be updated. The exception to this is if the mutable_times parameter
    is set to False, which makes start and end read-only. This is typically
    done for TaskLogEntry instances returned from get_task_log_entries()
    because the times may be truncated to fit the search range in that case.
    """

    def __init__(self, logger, db, task, entry_id, start, end,
                 mutable_times=True):
        self.diary = []
        self.tags = set()
        self.task = task
        self.entry_id = entry_id
        self.db = db
        self.mutable_times = mutable_times

        self._start = datetime.fromtimestamp(start)
        self._end = datetime.fromtimestamp(end) if end is not None else None

        cur = db.conn.cursor()
        self.get_diary_entries(logger, cur, task, start, end)
        self.get_tags(logger, cur, task)
        self.get_completed_todos_as_diary(logger, cur, task, start, end)


    @property
    def start(self):
        """Time at which event starts as a datetime instance."""
        return self._start


    @start.setter
    def start(self, value):
        if not self.mutable_times:
            raise AttributeError("times not mutable on this TaskLogEntry")
        new_epoch_time = time.mktime(value.timetuple())
        cur = self.db.conn.cursor()
        cur.execute("SELECT end FROM tasklog WHERE id=?", (self.entry_id,))
        row = cur.fetchone()
        if row is None:
            raise TimeTrackError("can't find entry %r" % (self.entry_id,))
        end = time.time() if row[0] is None else row[0]
        if end < new_epoch_time:
            raise TimeTrackError("can't move start time to after end of"
                                 " same task (%s)" %
                                 (datetime.fromtimestamp(end).isoformat(),))
        cur.execute("SELECT end FROM tasklog"
                    " WHERE end <= (SELECT start FROM tasklog WHERE id=?)"
                    " ORDER BY end DESC LIMIT 1", (self.entry_id,))
        row = cur.fetchone()
        if row is not None and row[0] > new_epoch_time:
            raise TimeTrackError("can't move start time to before end of"
                                 " previous task (%s)" %
                                 (datetime.fromtimestamp(row[0]).isoformat(),))
        with self.db.conn:
            cur.execute("UPDATE tasklog SET start=? WHERE id=?",
                        (new_epoch_time, self.entry_id))
        self._start = value


    @property
    def end(self):
        """Time at which event ends as a datetime instance."""
        return self._end


    @end.setter
    def end(self, value):
        if not self.mutable_times:
            raise AttributeError("times not mutable on this TaskLogEntry")
        new_epoch_time = time.mktime(value.timetuple())
        cur = self.db.conn.cursor()
        cur.execute("SELECT start FROM tasklog WHERE id=?", (self.entry_id,))
        row = cur.fetchone()
        if row is not None and row[0] > new_epoch_time:
            raise TimeTrackError("can't move end time to before start of"
                                 " same task (%s)" %
                                 (datetime.fromtimestamp(row[0]).isoformat(),))
        cur.execute("SELECT start FROM tasklog"
                    " WHERE start >= (SELECT end FROM tasklog WHERE id=?)"
                    " ORDER BY start LIMIT 1", (self.entry_id,))
        row = cur.fetchone()
        if row is not None and row[0] < new_epoch_time:
            raise TimeTrackError("can't move end time to after start of"
                                 " following task (%s)" %
                                 (datetime.fromtimestamp(row[0]).isoformat(),))
        with self.db.conn:
            cur.execute("UPDATE tasklog SET end=? WHERE id=?",
                        (new_epoch_time, self.entry_id))
        self._end = value


    def __repr__(self):
        return "TaskLogEntry(%r, %r, %r, %r)" % (self.task, self.entry_id,
                                                 self.start, self.end)


    def duration_secs(self):
        """Returns duration of entry in seconds."""

        end_time = datetime.now() if self.end is None else self.end
        delta = end_time - self.start
        return delta.days * 24 * 3600 + delta.seconds


    def get_diary_entries(self, logger, cur, task, start, end):
        if self.end is None:
            cur.execute("SELECT D.description, D.time FROM diary AS D"
                        " INNER JOIN tasks AS T ON D.task=T.id"
                        " WHERE T.name=? AND D.time>=?",
                        (task, start))
        else:
            cur.execute("SELECT D.description, D.time FROM diary AS D"
                        " INNER JOIN tasks AS T ON D.task=T.id"
                        " WHERE T.name=? AND D.time>=? AND D.time<=?",
                        (task, start, end))

        # Use bisect rather than letting SQLite do the sort because we don't
        # want to rely on the order of calling this and
        # get_completed_todos_as_diary().
        for row in cur:
            item = (datetime.fromtimestamp(row[1]), task, row[0])
            bisect.insort_right(self.diary, item)


    def get_tags(self, logger, cur, task):
        cur.execute("SELECT G.name FROM tagmappings AS M"
                    " INNER JOIN tasks AS T ON T.id=M.task"
                    " INNER JOIN tags AS G ON G.id=M.tag"
                    " WHERE T.name=?", (task,))
        self.tags = set(i[0] for i in cur)


    def get_completed_todos_as_diary(self, logger, cur, task, start, end):
        if self.end is None:
            cur.execute("SELECT O.description, O.done FROM todos AS O"
                        " INNER JOIN tasks AS T ON O.task=T.id"
                        " WHERE T.name=? AND O.done>=? AND O.done>0",
                        (task, start))
        else:
            cur.execute("SELECT O.description, O.done FROM todos AS O"
                        " INNER JOIN tasks AS T ON O.task=T.id"
                        " WHERE T.name=? AND O.done>=? AND O.done<=?"
                        " AND O.done>0",
                        (task, start, end))

        # Use bisect rather than letting SQLite do the sort because we don't
        # want to rely on the order of calling this and get_completed_todos().
        for row in cur:
            item = (datetime.fromtimestamp(row[1]), task, "[DONE] " + row[0])
            bisect.insort_right(self.diary, item)



class TimeTrackDB(object):

    def __init__(self, logger, filename=None):
        """Opens database, creating it if required."""

        self.logger = logger
        if filename is None:
            filename = os.path.expanduser("~/.timetrackdb")
        self.conn = sqlite3.connect(filename)
        self.ensure_schema()
        self.tags = TiedSet(logger, self.conn, "tag")
        self.tasks = TiedSet(logger, self.conn, "task")
        self.info = TiedDict(logger, self.conn, "info")

        # Log startup time.
        self.info["startup_time"] = datetime.now()


    def __del__(self):
        """Closes connection."""

        if self.conn is not None:
            self.info["shutdown_time"] = datetime.now()
            self.conn.close()
            self.conn = None


    def ensure_schema(self):
        """Creates tables if necessary."""

        create_tracklib_schema(self.logger, self.conn)


    def _get_current_task_with_id(self):
        """Return tuple of (log entry id, task name) or None."""

        cur = self.conn.cursor()
        cur.execute("SELECT L.id, T.name FROM tasklog AS L"
                    " INNER JOIN tasks AS T ON L.task=T.id"
                    " WHERE L.end IS NULL")
        row = cur.fetchone()
        if row is None:
            return None
        else:
            return row


    def _get_previous_task_with_id(self):
        """Return tuple of (log entry id, task name) or None."""

        task = self._get_current_task_with_id()
        cur = self.conn.cursor()
        if task is None:
            cur.execute("SELECT L.id, T.name FROM tasklog AS L"
                        " INNER JOIN tasks AS T ON L.task=T.id"
                        " ORDER BY L.end DESC LIMIT 1")
        else:
            cur_task_id = self.tasks.get_id(task[1])
            cur.execute("SELECT L.id, T.name FROM tasklog AS L"
                        " INNER JOIN tasks AS T ON L.task=T.id"
                        " WHERE end IS NOT NULL AND L.task!=?"
                        " ORDER BY L.end DESC LIMIT 1", (cur_task_id,))
        row = cur.fetchone()
        if row is None:
            return None
        else:
            return row


    def get_current_task(self):
        """Returns the name of the current task."""

        task = self._get_current_task_with_id()
        if task is None:
            return None
        else:
            return task[1]


    def get_previous_task(self):
        """Returns the name of the highest completed task."""

        task = self._get_previous_task_with_id()
        if task is None:
            return None
        else:
            return task[1]


    def get_last_created_task(self):
        """Returns the most-recently created task."""

        cur = self.conn.cursor()
        cur.execute("SELECT name FROM tasks ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        else:
            return row[0]


    def get_current_task_start(self):
        """Returns the start time of the current task as a local datetime."""

        cur = self.conn.cursor()
        cur.execute("SELECT start FROM tasklog WHERE end IS NULL")
        row = cur.fetchone()
        if row is None:
            return None
        else:
            return datetime.fromtimestamp(row[0])


    def end_current_task(self, epoch_time=None):
        """Ends the current task, if any."""

        if epoch_time is None:
            epoch_time = int(time.time())

        task = self._get_current_task_with_id()
        if task is not None:
            cur = self.conn.cursor()
            self.info["taskstop_time"] = datetime.fromtimestamp(epoch_time)
            with self.conn:
                cur.execute("UPDATE tasklog SET end=?"
                            " WHERE id=?", (epoch_time, task[0]))


    def get_latest_task_end(self):
        """Returns datetime of most recent task ending."""

        cur = self.conn.cursor()
        cur.execute("SELECT MAX(end) FROM tasklog WHERE end IS NOT NULL")
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        else:
            return datetime.fromtimestamp(float(row[0]))


    def start_task(self, task, at_datetime=None):
        """Starts a new task, ending any current task in the process."""

        # Work out the time to use as 'now'.
        if at_datetime is None:
            at_datetime = datetime.now()
        epoch_time = time.mktime(at_datetime.timetuple())

        # Check current task to see if we need to make any changes.
        cur_task = self._get_current_task_with_id()
        if cur_task is not None:
            cur_start = self.get_current_task_start()
            if at_datetime < cur_start:
                raise TimeTrackError("can't stop current task at a time"
                                     " earlier than its start (%s)" %
                                     (cur_start.isoformat(),))
        else:
            latest_end = self.get_latest_task_end()
            if latest_end is not None and at_datetime < latest_end:
                raise TimeTrackError("can't start new task at a time"
                                     " earlier than latest previous task"
                                     " ended (%s)" % (latest_end.isoformat(),))

        if task is None:
            if cur_task is None:
                # No change
                return
            new_task_id = None
        else:
            if cur_task is not None and task == cur_task[1]:
                # No change
                return
            new_task_id = self.tasks.get_id(task)

        # Stop current task.
        self.end_current_task(epoch_time)

        # If new task specified, start it.
        if new_task_id is not None:
            cur = self.conn.cursor()
            self.info["taskstart_time"] = datetime.fromtimestamp(epoch_time)
            with self.conn:
                cur.execute("INSERT INTO tasklog (task, start, end)"
                            " VALUES (?, ?, NULL)",
                            (new_task_id, epoch_time))


    def stop_task(self, at_datetime=None):
        """Stops the current task."""

        self.start_task(None, at_datetime=at_datetime)


    def get_entry_from_id(self, entry_id):
        """Returns a TaskLogEntry for the specified entry ID."""

        cur = self.conn.cursor()
        cur.execute("SELECT T.name, L.start, L.end FROM tasklog AS L"
                    " INNER JOIN tasks AS T ON L.task=T.id WHERE L.id=?",
                    (int(entry_id),))
        row = cur.fetchone()
        if row is None:
            raise KeyError(entry_id)
        end = row[2] if row[2] is not None else time.time()
        return TaskLogEntry(self.logger, self, row[0], entry_id, row[1], end)


    def get_task_tags(self, task):
        """Returns the set of tags for a particular task."""

        # Get task ID.
        task_id = self.tasks.get_id(task)

        # Get list of rows in tagmappings for specified task.
        cur = self.conn.cursor()
        cur.execute("SELECT G.name FROM tagmappings AS M"
                    " INNER JOIN tags AS G ON M.tag=G.id"
                    " WHERE M.task=?", (task_id,))

        # Convert returned list of tags to set and return it.
        task_tags = set()
        for row in cur:
            task_tags.add(row[0])
        return task_tags


    def get_tag_tasks(self, tag):
        """Returns the set of tasks for a particular tag."""

        # Get tag ID.
        tag_id = self.tags.get_id(tag)

        # Get list of rows in tagmappings for specified tag.
        cur = self.conn.cursor()
        cur.execute("SELECT T.name FROM tagmappings AS M"
                    " INNER JOIN tasks AS T ON M.task=T.id"
                    " WHERE M.tag=?", (tag_id,))

        # Convert returned list of tasks to set and return it.
        tag_tasks = set()
        for row in cur:
            tag_tasks.add(row[0])
        return tag_tasks


    def add_task_tag(self, task, tag):
        """Adds a tag to the specified task."""

        try:
            task_id = self.tasks.get_id(task)
            tag_id = self.tags.get_id(tag)
        except KeyError, e:
            raise TimeTrackError("item not found: %s" % (e,))

        if tag in self.get_task_tags(task):
            # No change.
            return

        # Add tag to task.
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("INSERT INTO tagmappings (task, tag) VALUES (?, ?)",
                        (task_id, tag_id))


    def remove_task_tag(self, task, tag):
        """Removes a tag from the specified task."""

        try:
            task_id = self.tasks.get_id(task)
            tag_id = self.tags.get_id(tag)
        except KeyError, e:
            raise TimeTrackError("item not found: %s" % (e,))

        # Remove any such mappings.
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("DELETE FROM tagmappings WHERE task=? AND tag=?",
                        (task_id, tag_id))


    def get_task_at_time(self, at_datetime):
        """Return the task name at the specified time."""

        epoch_time = time.mktime(at_datetime.timetuple())
        cur = self.conn.cursor()
        cur.execute("SELECT T.name FROM tasklog AS L"
                    " INNER JOIN tasks AS T ON L.task=T.id"
                    " WHERE L.start <= ? AND"
                    " (L.end IS NULL OR L.end >= ?)",
                    (epoch_time, epoch_time))
        row = cur.fetchone()
        if row is None:
            return None
        else:
            return row[0]


    def add_diary_entry(self, desc, at_datetime=None):
        """Adds a diary entry to the current task."""

        # Work out the task active at the specified time.
        if at_datetime is None:
            at_datetime = datetime.now()
            task = self.get_current_task()
            if task is None:
                raise TimeTrackError("no task currently active")
        else:
            task = self.get_task_at_time(at_datetime)
            if task is None:
                raise TimeTrackError("no task active at %r" % (at_datetime,))

        # Add entry to appropriate task.
        epoch_time = time.mktime(at_datetime.timetuple())
        task_id = self.tasks.get_id(task)
        cur = self.conn.cursor()
        with self.conn:
            self.info["diaryentry_time"] = datetime.now()
            cur.execute("INSERT INTO diary (task, description, time)"
                        " VALUES (?, ?, ?)",
                        (task_id, desc, epoch_time))


    def add_task_todo(self, task, desc):
        """Adds a todo item for the specified task."""

        try:
            task_id = self.tasks.get_id(task)
        except KeyError, e:
            raise TimeTrackError("task not found: %s" % (e,))

        # Add todo to database.
        epoch_time = time.mktime(datetime.now().timetuple())
        cur = self.conn.cursor()
        with self.conn:
            self.info["todoadded_time"] = datetime.now()
            cur.execute("INSERT INTO todos (task, added, done, description)"
                        " VALUES (?, ?, 0, ?)",
                        (task_id, epoch_time, desc))


    def mark_todo_done(self, desc, at_datetime=None):
        """Marks a todo on the current task as complete."""

        # Work out the task active at the specified time.
        if at_datetime is None:
            at_datetime = datetime.now()
            task = self.get_current_task()
            if task is None:
                raise TimeTrackError("no task currently active")
        else:
            task = self.get_task_at_time(at_datetime)
            if task is None:
                raise TimeTrackError("no task active at %r" % (at_datetime,))

        # Update value in database.
        epoch_time = time.mktime(at_datetime.timetuple())
        task_id = self.tasks.get_id(task)
        cur = self.conn.cursor()
        with self.conn:
            cur.execute("SELECT id FROM todos WHERE task=?"
                        " AND description LIKE ?",
                        (task_id, "%" + desc + "%"))
            matches = sum(1 for row in cur)
            if matches == 0:
                raise TimeTrackError("todo not found for task %s: %s"
                                     % (task, desc))
            elif matches > 1:
                raise TimeTrackError("%d todo matches found for task %s: %s"
                                     % (matches, task, desc))
            self.info["tododone_time"] = datetime.now()
            cur.execute("UPDATE todos SET done=? WHERE task=?"
                        " AND description LIKE ?",
                        (epoch_time, task_id, "%" + desc + "%"))


    def get_pending_todos(self, task=None, tag=None, at_datetime=None):

        if at_datetime is None:
            at_datetime = datetime.now()

        where_clauses = []
        args = []
        where_clauses.append("(O.done>? OR O.done=0)")
        args.append(time.mktime(at_datetime.timetuple()))
        where_clauses.append("O.added<=?")
        args.append(time.mktime(at_datetime.timetuple()))
        if task is not None:
            if tag is not None:
                raise TimeTrackError("can't specify both tag and task")
            where_clauses.append("O.task=?")
            args.append(self.tasks.get_id(task))
        elif tag is not None:
            tasks = self.get_tag_tasks(tag)
            where_clauses.append("T.name IN ('%s')" %
                                 ("','".join(str(i) for i in tasks),))

        cur = self.conn.cursor()
        cur.execute("SELECT O.added, T.name, O.description FROM todos AS O"
                    " INNER JOIN tasks AS T ON O.task=T.id"
                    " WHERE %s ORDER BY O.added"
                    % (" AND ".join(where_clauses),), args)

        return [(datetime.fromtimestamp(row[0]), row[1], row[2]) for row in cur]


    def get_task_log_entries(self, start=None, end=None, tags=None, tasks=None):
        """Return TaskLogEntry instances matching specified criteria.

        If specified, start and end give times at which to bound the search,
        which should be datetime instances in local time. If either is
        unspecified or None, it's taken as the appropriate infinity.
        If an entry partially overlaps with the period, its start and/or end
        times are truncated to lie within the specified period.
        The tags parameter should be an iterable if specified, which restricts
        the results to tasks with the specified tags attached, or the tasks
        parameter can specify task names directly.
        """
        # Convert times to UTC timestamps and tags and tasks to sets.
        start = time.mktime(start.timetuple()) if start is not None else None
        end = time.mktime(end.timetuple()) if end is not None else None
        tags = set(tags) if tags is not None else None
        tasks = set(tasks) if tasks is not None else None

        # Create database cursor for multiple queries below.
        cur = self.conn.cursor()

        filter_tasks = None

        # If 'tags' was specified, convert these into a list of tasks.
        if tags is not None:
            filter_tasks = set()
            for tag in tags:
                try:
                    filter_tasks.update(self.get_tag_tasks(tag))
                except KeyError:
                    raise TimeTrackError("tag not found: '%s'" % (tag,))

        # If 'tasks' was specified, merge these in with any from tags.
        if tasks is not None:
            if filter_tasks is not None:
                filter_tasks.intersection_update(set(tasks))
            else:
                filter_tasks = set(tasks)

        # Convert filter_tasks to task IDs
        if filter_tasks is not None:
            try:
                filter_tasks = set(self.tasks.get_id(i) for i in filter_tasks)
            except KeyError, e:
                raise TimeTrackError("task not found: '%s'" % (e,))

            if not filter_tasks:
                # No possible results if filter_tasks is empty.
                return

        # Build WHERE clause.
        where_items = []
        if start is not None:
            where_items.append("(L.end >= %d OR L.end IS NULL)" % (int(start),))
        if end is not None:
            where_items.append("L.start <= %d" % (int(end),))
        if filter_tasks is not None:
            where_items.append("L.task IN (%s)" %
                               (",".join(str(i) for i in filter_tasks),))

        where_clause = ""
        if where_items:
            where_clause = " WHERE %s" % (" AND ".join(where_items),)

        cur.execute("SELECT T.name, L.id, L.start, L.end FROM tasklog AS L"
                    " INNER JOIN tasks AS T ON L.task=T.id"
                    "%s ORDER BY L.start" % (where_clause,))
        for row in cur:
            start_time = row[2]
            if start is not None and start_time < start:
                start_time = start
            end_time = row[3]
            if end_time is None and end is not None:
                end_time = time.time()
            if end is not None and end_time > end:
                end_time = end
            # We don't allow start and end to be mutable because of the way
            # we truncate them to the requested range.
            yield TaskLogEntry(self.logger, self, row[0], row[1],
                               start_time, end_time, mutable_times=False)



class SummaryGenerator(object):

    def __init__(self):
        self.entries = []

    def read_entries(self, entries, merge_diaries=False):
        """Read multiple entries."""

        for entry in entries:
            self.read_entry(entry, merge_diaries)


    def read_entry(self, entry, merge_diaries):
        """Read a single TaskLogEntry instance."""

        self.entries.append(entry)



class TaskSummaryGenerator(SummaryGenerator):

    def __init__(self, tags=None):
        self.filter_tags = tags
        self.total_time = collections.defaultdict(int)
        self.switches = collections.defaultdict(int)
        self.diary_entries = collections.defaultdict(list)
        self.previous_entry = None


    def read_entry(self, entry, merge_diaries):
        """Add entry's duration to appropriate task in total_time.

        The switches attribute records context switches, which are defined
        as cases where the task changes with a gap of less than a minute
        between consecutive entries.
        """

        # Work out if this was a context switch.
        context_switch = False
        if self.previous_entry is not None:
            delta = entry.start - self.previous_entry.end
            if delta.days == 0 and abs(delta.seconds) < 60:
                if self.previous_entry.task != entry.task:
                    context_switch = True

        # If this task belongs to one of our tags (or we're not filtering)
        # then update entries in appropriate dictionaries.
        if self.filter_tags is None or self.filter_tags & entry.tags:
            self.total_time[entry.task] += entry.duration_secs()
            if context_switch:
                self.switches[entry.task] += 1
            for diary_entry in entry.diary:
                if merge_diaries:
                    bisect.insort(self.diary_entries[None], diary_entry)
                else:
                    bisect.insort(self.diary_entries[entry.task], diary_entry)

        self.previous_entry = entry



class TagSummaryGenerator(SummaryGenerator):

    def __init__(self):
        self.total_time = collections.defaultdict(int)
        self.switches = collections.defaultdict(int)
        self.diary_entries = collections.defaultdict(list)
        self.previous_entry = None


    def read_entry(self, entry, merge_diaries):
        """Add entry's duration to all applicable tags in total_time.

        The switches attribute records context switches, which are defined
        as cases where the new entry contains a tag not attached to the
        previous entry and where the gap between them is less than a minute.
        """

        for tag in entry.tags:
            self.total_time[tag] += entry.duration_secs()
            if self.previous_entry is not None:
                delta = entry.start - self.previous_entry.end
                if delta.days == 0 and abs(delta.seconds) < 60:
                    if tag not in self.previous_entry.tags:
                        self.switches[tag] += 1
            for diary_entry in entry.diary:
                if merge_diaries:
                    bisect.insort(self.diary_entries[None], diary_entry)
                else:
                    bisect.insort(self.diary_entries[tag], diary_entry)
        self.previous_entry = entry


def get_summary_for_period(db, summary_obj, period, number, tags=None):
    """Fills the specified summary object with entries from a calendar period.

    The db argument should be a TimeTrackDB instance. The summary_obj should
    be an instance of a class derived from SummaryGenerator. The period
    argument should be a string which is either "day", "week" or "month"
    to specify the calendar period over which summaries should be
    generated. The number argument specifies how many of those periods in the
    past the report should cover. Specifying a number of 0 indicates the
    current (partial) period should be used, 1 will indicate the previous
    (i.e. most recent complete) period, etc.
    """

    if number < 0:
        raise TimeTrackError("cannot predict the future")

    # Calculate start and end times.
    now = datetime.now()
    if period == "day":
        start = datetime(now.year, now.month, now.day, 0, 0 ,0)
        start -= timedelta(number)
        end = start + timedelta(1)
    elif period == "week":
        start = datetime(now.year, now.month, now.day, 0, 0, 0)
        start -= timedelta(now.weekday())
        start -= timedelta(number * 7)
        end = start + timedelta(7)
    elif period == "month":
        start = datetime(now.year + (((now.month - 1) - number) // 12),
                         (((now.month - 1) - number) % 12) + 1, 1, 0, 0, 0)
        end = datetime(start.year + (1 if start.month == 12 else 0),
                       start.month + 1 if start.month < 12 else 1, 1, 0, 0, 0)
    else:
        raise TimeTrackError("period %r invalid" % (period,))

    # Fill up summary object with correct entries.
    summary_obj.read_entries(db.get_task_log_entries(start=start, end=end,
                                                     tags=tags))

