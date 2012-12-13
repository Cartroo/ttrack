#!/usr/bin/python

import cPickle
import datetime
import logging
import sqlite3
import time
import unittest

# Module under test
import tracklib


class NullHandler(logging.Handler):
    """Dummy logging handler which does nothing."""

    def emit(self, record):
        pass


# Must be defined at the top level to be pickled.
class MyClass(object):
    """A test class type."""

    def __init__(self, value):
        self.local_value = value

    def method(self):
        return self.local_value


class TestInfoTiedDict(unittest.TestCase):

    def setUp(self):
        self.logger = NullHandler()
        self.conn = sqlite3.connect(":memory:")
        tracklib.create_tracklib_schema(self.logger, self.conn)


    def tearDown(self):
        self.conn.close()
        del self.conn


    def _check_info(self, expected):
        cur = self.conn.cursor()
        cur.execute("SELECT name, value FROM info")
        found = dict((k, cPickle.loads(v.encode("utf8"))) for k, v in cur)
        for item, value in expected.iteritems():
            self.assertEqual(value, found[item])


    def test_add_info(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = "bar"
        self.assertTrue("foo" in info)
        self._check_info({"foo": "bar"})


    def test_del_info(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = "bar"
        self.assertTrue("foo" in info)
        del info["foo"]
        self.assertFalse("foo" in info)
        self._check_info({})


    def test_update_info(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = "bar"
        self.assertTrue("foo" in info)
        self._check_info({"foo": "bar"})
        info["foo"] = "baz"
        self.assertTrue("foo" in info)
        self._check_info({"foo": "baz"})


    def test_add_str_persist(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = "bozzle"
        self.assertTrue("foo" in info)
        del info
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertTrue("foo" in info)
        self.assertEqual(info["foo"], "bozzle")


    def test_add_datetime_persist(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = datetime.datetime(2010, 1, 2, 3, 4, 5)
        self.assertTrue("foo" in info)
        del info
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertTrue("foo" in info)
        self.assertEqual(info["foo"], datetime.datetime(2010, 1, 2, 3, 4, 5))


    def test_add_class_persist(self):
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertFalse("foo" in info)
        info["foo"] = MyClass(12345)
        self.assertTrue("foo" in info)
        del info
        info = tracklib.TiedDict(self.logger, self.conn, "info")
        self.assertTrue("foo" in info)
        self.assertIsInstance(info["foo"], MyClass)
        self.assertEqual(info["foo"].method(), 12345)



class TestTaskTiedSet(unittest.TestCase):

    def setUp(self):
        logger = NullHandler()
        self.conn = sqlite3.connect(":memory:")
        tracklib.create_tracklib_schema(logger, self.conn)
        self.tasks = tracklib.TiedSet(logger, self.conn, "task")


    def tearDown(self):
        self.conn.close()
        del self.conn
        del self.tasks


    def _check_tasks(self, expected):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM tasks")
        found = set(i[0] for i in cur)
        self.assertEqual(found, expected)


    def test_add_single_task(self):
        self.tasks.add("task1")
        self.assertTrue("task1" in self.tasks)
        self._check_tasks(set(("task1",)))


    def test_add_multiple_tasks(self):
        test_tasks = ["task%d" % (i,) for i in xrange(1, 10)]
        for task in test_tasks:
            self.tasks.add(task)
        for task in test_tasks:
            self.assertTrue(task in self.tasks)
        self._check_tasks(set(test_tasks))


    def test_discard_single_task(self):
        self.tasks.add("task1")
        self.tasks.discard("task1")
        self.assertFalse("task1" in self.tasks)
        self._check_tasks(set())


    def test_discard_multiple_tasks(self):
        test_tasks_1 = ["task%d" % (i,) for i in xrange(1, 5)]
        test_tasks_2 = ["task%d" % (i,) for i in xrange(5, 10)]
        for task in test_tasks_1 + test_tasks_2:
            self.tasks.add(task)
        for task in test_tasks_1:
            self.tasks.discard(task)
        for task in test_tasks_1:
            self.assertFalse(task in self.tasks)
        for task in test_tasks_2:
            self.assertTrue(task in self.tasks)
        self._check_tasks(set(test_tasks_2))


    def test_discard_task_with_tags(self):
        self.tasks.add("task1")
        self.tasks.add("task2")
        task1_id = self.tasks.get_id("task1")
        task2_id = self.tasks.get_id("task2")
        cur = self.conn.cursor()
        cur.execute("INSERT INTO tags (id, name) VALUES (1, 'tag1')")
        cur.execute("INSERT INTO tags (id, name) VALUES (2, 'tag2')")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (?, 1)",
                    (task1_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (?, 2)",
                    (task1_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (?, 1)",
                    (task2_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (?, 2)",
                    (task2_id,))
        self.conn.commit()
        self.tasks.discard("task1")
        cur.execute("SELECT task, tag FROM tagmappings")
        mappings = set(cur)
        self.assertFalse((task1_id, 1) in mappings)
        self.assertFalse((task1_id, 2) in mappings)
        self.assertTrue((task2_id, 1) in mappings)
        self.assertTrue((task2_id, 2) in mappings)


    def test_discard_task_with_log_entries(self):
        self.tasks.add("task1")
        self.tasks.add("task2")
        task1_id = self.tasks.get_id("task1")
        task2_id = self.tasks.get_id("task2")
        cur = self.conn.cursor()
        cur.execute("INSERT INTO tags (id, name) VALUES (1, 'tag1')")
        cur.execute("INSERT INTO tags (id, name) VALUES (2, 'tag2')")
        cur.execute("INSERT INTO tasklog (task, start, end)"
                    " VALUES (?, 100, NULL)", (task1_id,))
        cur.execute("INSERT INTO tasklog (task, start, end)"
                    " VALUES (?, 200, NULL)", (task2_id,))
        cur.execute("INSERT INTO tasklog (task, start, end)"
                    " VALUES (?, 300, NULL)", (task1_id,))
        cur.execute("INSERT INTO tasklog (task, start, end)"
                    " VALUES (?, 400, NULL)", (task2_id,))
        self.tasks.discard("task1")
        cur.execute("SELECT task, start, end FROM tasklog ORDER BY id")
        entries = list(cur)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], (task2_id, 200, None))
        self.assertEqual(entries[1], (task2_id, 400, None))


    def test_discard_task_with_diary_entries(self):
        self.tasks.add("task1")
        self.tasks.add("task2")
        task1_id = self.tasks.get_id("task1")
        task2_id = self.tasks.get_id("task2")
        cur = self.conn.cursor()
        cur.execute("INSERT INTO tags (id, name) VALUES (1, 'tag1')")
        cur.execute("INSERT INTO tags (id, name) VALUES (2, 'tag2')")
        cur.execute("INSERT INTO diary (task, description, time)"
                    " VALUES (?, 'one', 100)", (task1_id,))
        cur.execute("INSERT INTO diary (task, description, time)"
                    " VALUES (?, 'two', 200)", (task2_id,))
        cur.execute("INSERT INTO diary (task, description, time)"
                    " VALUES (?, 'three', 300)", (task1_id,))
        cur.execute("INSERT INTO diary (task, description, time)"
                    " VALUES (?, 'four', 400)", (task2_id,))
        self.conn.commit()
        self.tasks.discard("task1")
        cur.execute("SELECT task, description, time FROM diary ORDER BY id")
        entries = list(cur)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], (task2_id, "two", 200))
        self.assertEqual(entries[1], (task2_id, "four", 400))



class TestTagTiedSet(unittest.TestCase):

    def setUp(self):
        logger = NullHandler()
        self.conn = sqlite3.connect(":memory:")
        tracklib.create_tracklib_schema(logger, self.conn)
        self.tags = tracklib.TiedSet(logger, self.conn, "tag")


    def tearDown(self):
        self.conn.close()
        del self.conn
        del self.tags


    def _check_tags(self, expected):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM tags")
        found = set(i[0] for i in cur)
        self.assertEqual(found, expected)


    def test_add_single_tag(self):
        self.tags.add("tag1")
        self.assertTrue("tag1" in self.tags)
        self._check_tags(set(("tag1",)))


    def test_add_multiple_tags(self):
        test_tags = ["tag%d" % (i,) for i in xrange(1, 10)]
        for tag in test_tags:
            self.tags.add(tag)
        for tag in test_tags:
            self.assertTrue(tag in self.tags)
        self._check_tags(set(test_tags))


    def test_discard_single_tag(self):
        self.tags.add("tag1")
        self.tags.discard("tag1")
        self.assertFalse("tag1" in self.tags)
        self._check_tags(set())


    def test_discard_multiple_tags(self):
        test_tags_1 = ["tag%d" % (i,) for i in xrange(1, 5)]
        test_tags_2 = ["tag%d" % (i,) for i in xrange(5, 10)]
        for tag in test_tags_1 + test_tags_2:
            self.tags.add(tag)
        for tag in test_tags_1:
            self.tags.discard(tag)
        for tag in test_tags_1:
            self.assertFalse(tag in self.tags)
        for tag in test_tags_2:
            self.assertTrue(tag in self.tags)
        self._check_tags(set(test_tags_2))


    def test_discard_tag_with_tasks(self):
        self.tags.add("tag1")
        self.tags.add("tag2")
        tag1_id = self.tags.get_id("tag1")
        tag2_id = self.tags.get_id("tag2")
        cur = self.conn.cursor()
        cur.execute("INSERT INTO tasks (id, name) VALUES (1, 'task1')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (2, 'task2')")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (1, ?)",
                    (tag1_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (2, ?)",
                    (tag1_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (1, ?)",
                    (tag2_id,))
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (2, ?)",
                    (tag2_id,))
        self.conn.commit()
        self.tags.discard("tag1")
        cur.execute("SELECT task, tag FROM tagmappings")
        mappings = set(cur)
        self.assertFalse((1, tag1_id) in mappings)
        self.assertFalse((2, tag1_id) in mappings)
        self.assertTrue((1, tag2_id) in mappings)
        self.assertTrue((2, tag2_id) in mappings)



class TestTimeTrackDB(unittest.TestCase):

    def setUp(self):
        logger = NullHandler()
        self.db = tracklib.TimeTrackDB(logger, filename=":memory:")


    def tearDown(self):
        del self.db


    def test_tasks(self):
        self.db.tasks.add("task1")
        self.db.tasks.add("task2")
        self.db.tasks.discard("task1")
        self.assertFalse("task1" in self.db.tasks)
        self.assertTrue("task2" in self.db.tasks)


    def test_tags(self):
        self.db.tags.add("tag1")
        self.db.tags.add("tag2")
        self.db.tags.discard("tag1")
        self.assertFalse("tag1" in self.db.tags)
        self.assertTrue("tag2" in self.db.tags)


    def test_start_stop_task(self):
        # Add new task and start it.
        self.db.tasks.add("task1")
        task1_id = self.db.tasks.get_id("task1")
        start_time = int(time.time())
        self.db.start_task("task1")

        # Check new task is listed with correct start time and no end time.
        cur = self.db.conn.cursor()
        cur.execute("SELECT task, start, end FROM tasklog")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], task1_id)
        self.assertAlmostEqual(entries[0][1], start_time, delta=1)
        self.assertEqual(entries[0][2], None)

        # Sleep for 2 seconds then stop task.
        time.sleep(2)
        stop_time = int(time.time())
        self.db.stop_task()

        # Check task now has correct end time listed.
        cur.execute("SELECT task, start, end FROM tasklog")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], task1_id)
        self.assertAlmostEqual(entries[0][1], start_time, delta=1)
        self.assertAlmostEqual(entries[0][2], stop_time, delta=1)


    def test_start_same_task(self):
        # Add new task and start it.
        self.db.tasks.add("task1")
        task1_id = self.db.tasks.get_id("task1")
        start_time = int(time.time())
        self.db.start_task("task1")

        # Sleep for 2 seconds then restart same task.
        time.sleep(2)
        self.db.start_task("task1")

        # Check new task is listed with correct start time and no end time.
        cur = self.db.conn.cursor()
        cur.execute("SELECT task, start, end FROM tasklog")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], task1_id)
        self.assertAlmostEqual(entries[0][1], start_time, delta=1)
        self.assertEqual(entries[0][2], None)


    def test_start_second_task(self):
        # Add two tasks and start one.
        self.db.tasks.add("task1")
        self.db.tasks.add("task2")
        task1_id = self.db.tasks.get_id("task1")
        task2_id = self.db.tasks.get_id("task2")
        start_time = int(time.time())
        self.db.start_task("task1")

        # Sleep for 2 seconds then start second task.
        time.sleep(2)
        stop_time = int(time.time())
        self.db.start_task("task2")

        # Check task now has correct end time listed.
        cur = self.db.conn.cursor()
        cur.execute("SELECT task, start, end FROM tasklog")
        entries = list(cur)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], task1_id)
        self.assertAlmostEqual(entries[0][1], start_time, delta=1)
        self.assertAlmostEqual(entries[0][2], stop_time, delta=1)
        self.assertEqual(entries[1][0], task2_id)
        self.assertAlmostEqual(entries[1][1], stop_time, delta=1)
        self.assertEqual(entries[1][2], None)


    def test_current_task(self):
        self.db.tasks.add("task1")
        self.db.start_task("task1")
        self.assertEqual(self.db.get_current_task(), "task1")
        self.db.stop_task()
        self.assertEqual(self.db.get_current_task(), None)


    def test_add_task_tags(self):
        self.db.tasks.add("task1")
        self.db.tasks.add("task2")
        self.db.tasks.add("task1+2")
        self.db.tags.add("tag1")
        self.db.tags.add("tag2")
        self.db.add_task_tag("task1", "tag1")
        self.db.add_task_tag("task2", "tag2")
        self.db.add_task_tag("task1+2", "tag1")
        self.db.add_task_tag("task1+2", "tag2")
        self.assertEqual(set(self.db.get_task_tags("task1")), set(("tag1",)))
        self.assertEqual(set(self.db.get_task_tags("task2")), set(("tag2",)))
        self.assertEqual(set(self.db.get_task_tags("task1+2")),
                         set(("tag1", "tag2")))
        self.assertEqual(set(self.db.get_tag_tasks("tag1")),
                         set(("task1", "task1+2")))
        self.assertEqual(set(self.db.get_tag_tasks("tag2")),
                         set(("task2", "task1+2")))


    def test_remove_task_tags(self):
        self.db.tasks.add("task1")
        self.db.tasks.add("task2")
        self.db.tasks.add("task1+2")
        self.db.tags.add("tag1")
        self.db.tags.add("tag2")
        self.db.add_task_tag("task1", "tag1")
        self.db.add_task_tag("task2", "tag2")
        self.db.add_task_tag("task1+2", "tag1")
        self.db.add_task_tag("task1+2", "tag2")
        self.db.remove_task_tag("task1", "tag1")
        self.db.remove_task_tag("task1+2", "tag1")
        self.assertEqual(set(self.db.get_task_tags("task1")), set())
        self.assertEqual(set(self.db.get_task_tags("task2")), set(("tag2",)))
        self.assertEqual(set(self.db.get_task_tags("task1+2")), set(("tag2",)))
        self.assertEqual(set(self.db.get_tag_tasks("tag1")), set())
        self.assertEqual(set(self.db.get_tag_tasks("tag2")),
                         set(("task2", "task1+2")))


    def test_add_diary_entry(self):
        self.db.tasks.add("task1")
        self.db.start_task("task1")
        entry_time = int(time.time())
        self.db.add_diary_entry("entry1")

        cur = self.db.conn.cursor()
        cur.execute("SELECT task, description, time FROM diary")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[0][1], "entry1")
        self.assertAlmostEqual(entries[0][2], entry_time, delta=1)


    def test_add_diary_entry_no_task(self):
        self.db.tasks.add("task1")
        self.db.start_task("task1")
        self.db.stop_task()
        with self.assertRaises(tracklib.TimeTrackError):
            self.db.add_diary_entry("entry1")


    def test_add_todo(self):
        self.db.tasks.add("task1")
        entry_time = time.time()
        self.db.add_task_todo("task1", "Test todo A for task1")

        cur = self.db.conn.cursor()
        cur.execute("SELECT task, description, added, done FROM todos")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[0][1], "Test todo A for task1")
        self.assertAlmostEqual(entries[0][2], entry_time, delta=1)
        self.assertEqual(entries[0][3], 0)


    def test_mark_todo_done(self):
        self.db.tasks.add("task1")
        entry_time = time.time()
        self.db.add_task_todo("task1", "Test todo A for task1")
        self.db.start_task("task1")
        done_time = time.time()
        self.db.mark_todo_done("Test todo A for task1")
        self.db.stop_task()

        cur = self.db.conn.cursor()
        cur.execute("SELECT task, description, added, done FROM todos")
        entries = list(cur)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[0][1], "Test todo A for task1")
        self.assertAlmostEqual(entries[0][2], entry_time, delta=1)
        self.assertAlmostEqual(entries[0][3], done_time, delta=1)


    def test_mark_todo_done_unique_prefix(self):
        self.db.tasks.add("task1")
        self.db.add_task_todo("task1", "Test todo A for task1")
        self.db.add_task_todo("task1", "Test todo B for task1")
        self.db.start_task("task1")
        done_time = time.time()
        self.db.mark_todo_done("Test todo A")
        self.db.stop_task()

        cur = self.db.conn.cursor()
        cur.execute("SELECT task, description, done FROM todos")
        entries = sorted(list(cur))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[0][1], "Test todo A for task1")
        self.assertAlmostEqual(entries[0][2], done_time, delta=1)
        self.assertEqual(entries[1][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[1][1], "Test todo B for task1")
        self.assertAlmostEqual(entries[1][2], 0)


    def test_mark_todo_done_no_task(self):
        self.db.tasks.add("task1")
        self.db.add_task_todo("task1", "Test todo A for task1")
        with self.assertRaises(tracklib.TimeTrackError):
            self.db.mark_todo_done("Test todo")


    def test_mark_todo_done_ambiguous_prefix(self):
        self.db.tasks.add("task1")
        self.db.add_task_todo("task1", "Test todo A for task1")
        self.db.add_task_todo("task1", "Test todo B for task1")
        self.db.start_task("task1")
        with self.assertRaises(tracklib.TimeTrackError):
            self.db.mark_todo_done("Test todo")


    def test_mark_todo_done_unique_within_task_prefix(self):
        self.db.tasks.add("task1")
        self.db.tasks.add("task2")
        self.db.add_task_todo("task1", "Test todo A for task1")
        self.db.add_task_todo("task2", "Test todo A for task2")
        self.db.start_task("task1")
        done_time = time.time()
        self.db.mark_todo_done("Test")
        self.db.stop_task()

        cur = self.db.conn.cursor()
        cur.execute("SELECT task, description, done FROM todos")
        entries = sorted(list(cur))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], self.db.tasks.get_id("task1"))
        self.assertEqual(entries[0][1], "Test todo A for task1")
        self.assertAlmostEqual(entries[0][2], done_time, delta=1)
        self.assertEqual(entries[1][0], self.db.tasks.get_id("task2"))
        self.assertEqual(entries[1][1], "Test todo A for task2")
        self.assertAlmostEqual(entries[1][2], 0)


    def _get_ts(self, day, hour, minute, second):
        return time.mktime(datetime.datetime(2011, 1, day, hour, minute,
                                             second).timetuple())


    def _create_sample_task_logs(self):
        cur = self.db.conn.cursor()

        # Layout of test tasks:
        #
        # task1: tag1
        # task2: tag2
        # task3: tag1 tag2
        # task4: tag4
        # task5: tag1 tag4
        # task6: tag2 tag4
        # task7: tag1 tag2 tag4

        cur.execute("INSERT INTO tasks (id, name) VALUES (1, 'task1')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (2, 'task2')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (3, 'task3')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (4, 'task4')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (5, 'task5')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (6, 'task6')")
        cur.execute("INSERT INTO tasks (id, name) VALUES (7, 'task7')")
        cur.execute("INSERT INTO tags (id, name) VALUES (1, 'tag1')")
        cur.execute("INSERT INTO tags (id, name) VALUES (2, 'tag2')")
        cur.execute("INSERT INTO tags (id, name) VALUES (4, 'tag4')")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (1, 1)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (2, 2)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (3, 1)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (3, 2)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (4, 4)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (5, 1)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (5, 4)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (6, 2)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (6, 4)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (7, 1)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (7, 2)")
        cur.execute("INSERT INTO tagmappings (task, tag) VALUES (7, 4)")

        # Sequence of events on test tasks:
        #
        # evA: 2011-01-01 10:00:00 - START task1    [00h 30m]
        # evB: 2011-01-01 10:30:00 - START task2    [01h 30m]
        # evBa:2011-01-01 10:31:00 - TODO 'Todo for task2'
        # evBb:2011-01-01 10:31:10 - TODO 'Todo for task3'
        # evBc:2011-01-01 10:31:20 - TODO 'Todo for task4'
        # evC: 2011-01-01 10:35:00 - DIARY one
        # evCa:2011-01-01 10:35:05 - DONE 'Todo for task2'
        # evD: 2011-01-01 12:00:00 - START task1    [04h 00m]
        # evE: 2011-01-01 13:00:00 - DIARY two
        # evF: 2011-01-01 13:30:00 - DIARY three
        # evG: 2011-01-01 16:00:00 - STOP task1
        # evH: 2011-01-02 10:00:00 - START task3    [24h 00m]
        # evHa:2011-01-02 10:15:00 - DONE 'Todo for task3'
        # evI: 2011-01-02 12:00:00 - DIARY four
        # evJ: 2011-01-03 10:00:00 - START task4    [01h 00m]
        # evK: 2011-01-03 11:00:00 - START task5    [01h 00m]
        # evL: 2011-01-03 12:00:00 - START task6    [01h 00m]
        # evM: 2011-01-03 13:00:00 - START task7    [inf.   ]
        # (task7 is left running as the current task)

        evA, evB = (self._get_ts(1, 10, 0, 0), self._get_ts(1, 10, 30, 0))
        evBa, evBb = (self._get_ts(1, 10, 31, 0), self._get_ts(1, 10, 31, 10))
        evBc = self._get_ts(1, 10, 31, 20)
        evC, evD = (self._get_ts(1, 10, 35, 0), self._get_ts(1, 12, 0, 0))
        evCa = self._get_ts(1, 10, 35, 5)
        evE, evF = (self._get_ts(1, 13, 0, 0), self._get_ts(1, 13, 30, 0))
        evG, evH = (self._get_ts(1, 16, 0, 0), self._get_ts(2, 10, 0, 0))
        evHa = self._get_ts(2, 10, 15, 0)
        evI, evJ = (self._get_ts(2, 12, 0, 0), self._get_ts(3, 10, 0, 0))
        evK, evL = (self._get_ts(3, 11, 0, 0), self._get_ts(3, 12, 0, 0))
        evM = self._get_ts(3, 13, 0, 0)

        # Insert tasklog entries.
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (1, ?, ?)", (evA, evB))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (2, ?, ?)", (evB, evD))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (1, ?, ?)", (evD, evG))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (3, ?, ?)", (evH, evJ))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (4, ?, ?)", (evJ, evK))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (5, ?, ?)", (evK, evL))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (6, ?, ?)", (evL, evM))
        cur.execute("INSERT INTO tasklog (task, start, end) VALUES"
                    " (7, ?, NULL)", (evM,))

        # Insert diary entries.
        cur.execute("INSERT INTO diary (task, description, time) VALUES"
                    " (2, 'one', ?)", (evC,))
        cur.execute("INSERT INTO diary (task, description, time) VALUES"
                    " (1, 'two', ?)", (evE,))
        cur.execute("INSERT INTO diary (task, description, time) VALUES"
                    " (1, 'three', ?)", (evF,))
        cur.execute("INSERT INTO diary (task, description, time) VALUES"
                    " (3, 'four', ?)", (evI,))

        # Insert todo entries.
        cur.execute("INSERT INTO todos (task, description, added, done) VALUES"
                    " (2, 'Todo for task2', ?, ?)", (evBa, evCa))
        cur.execute("INSERT INTO todos (task, description, added, done) VALUES"
                    " (3, 'Todo for task3', ?, ?)", (evBb, evHa))
        cur.execute("INSERT INTO todos (task, description, added, done) VALUES"
                    " (4, 'Todo for task4', ?, 0)", (evBc,))

        self.db.conn.commit()


    def test_query_no_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries())

        self.assertEqual(len(entries), 8)

        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[0].start,
                         datetime.datetime(2011, 1, 1, 10, 0, 0))
        self.assertEqual(entries[0].end,
                         datetime.datetime(2011, 1, 1, 10, 30, 0))
        self.assertEqual(len(entries[0].diary), 0)

        self.assertEqual(entries[1].task, 'task2')
        self.assertEqual(entries[1].start,
                         datetime.datetime(2011, 1, 1, 10, 30, 0))
        self.assertEqual(entries[1].end,
                         datetime.datetime(2011, 1, 1, 12, 0, 0))
        self.assertEqual(len(entries[1].diary), 2)
        self.assertEqual(entries[1].diary[0],
                         (datetime.datetime(2011, 1, 1, 10, 35, 0),
                          'task2', 'one'))
        self.assertEqual(entries[1].diary[1],
                         (datetime.datetime(2011, 1, 1, 10, 35, 5),
                          'task2', '[DONE] Todo for task2'))

        self.assertEqual(entries[2].task, 'task1')
        self.assertEqual(entries[2].start,
                         datetime.datetime(2011, 1, 1, 12, 0, 0))
        self.assertEqual(entries[2].end,
                         datetime.datetime(2011, 1, 1, 16, 0, 0))
        self.assertEqual(len(entries[2].diary), 2)
        self.assertEqual(entries[2].diary[0],
                         (datetime.datetime(2011, 1, 1, 13, 0, 0),
                          'task1', 'two'))
        self.assertEqual(entries[2].diary[1],
                         (datetime.datetime(2011, 1, 1, 13, 30, 0),
                          'task1', 'three'))

        self.assertEqual(entries[3].task, 'task3')
        self.assertEqual(entries[3].start,
                         datetime.datetime(2011, 1, 2, 10, 0, 0))
        self.assertEqual(entries[3].end,
                         datetime.datetime(2011, 1, 3, 10, 0, 0))
        self.assertEqual(len(entries[3].diary), 2)
        self.assertEqual(entries[3].diary[0],
                         (datetime.datetime(2011, 1, 2, 10, 15, 0),
                          'task3', '[DONE] Todo for task3'))
        self.assertEqual(entries[3].diary[1],
                         (datetime.datetime(2011, 1, 2, 12, 0, 0),
                          'task3', 'four'))

        self.assertEqual(entries[4].task, 'task4')
        self.assertEqual(entries[4].start,
                         datetime.datetime(2011, 1, 3, 10, 0, 0))
        self.assertEqual(entries[4].end,
                         datetime.datetime(2011, 1, 3, 11, 0, 0))
        self.assertEqual(len(entries[4].diary), 0)

        self.assertEqual(entries[5].task, 'task5')
        self.assertEqual(entries[5].start,
                         datetime.datetime(2011, 1, 3, 11, 0, 0))
        self.assertEqual(entries[5].end,
                         datetime.datetime(2011, 1, 3, 12, 0, 0))
        self.assertEqual(len(entries[5].diary), 0)

        self.assertEqual(entries[6].task, 'task6')
        self.assertEqual(entries[6].start,
                         datetime.datetime(2011, 1, 3, 12, 0, 0))
        self.assertEqual(entries[6].end,
                         datetime.datetime(2011, 1, 3, 13, 0, 0))
        self.assertEqual(len(entries[6].diary), 0)

        self.assertEqual(entries[7].task, 'task7')
        self.assertEqual(entries[7].start,
                         datetime.datetime(2011, 1, 3, 13, 0, 0))
        self.assertEqual(entries[7].end, None)
        self.assertEqual(len(entries[7].diary), 0)


    def test_query_tag_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(tags=('tag1',)))
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[1].task, 'task1')
        self.assertEqual(entries[2].task, 'task3')
        self.assertEqual(entries[3].task, 'task5')
        self.assertEqual(entries[4].task, 'task7')


    def test_query_multiple_tag_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(tags=('tag1', 'tag4')))
        self.assertEqual(len(entries), 7)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[1].task, 'task1')
        self.assertEqual(entries[2].task, 'task3')
        self.assertEqual(entries[3].task, 'task4')
        self.assertEqual(entries[4].task, 'task5')
        self.assertEqual(entries[5].task, 'task6')
        self.assertEqual(entries[6].task, 'task7')


    def test_query_task_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(tasks=('task1',)))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[1].task, 'task1')


    def test_query_multiple_task_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(tasks=('task1', 'task2')))
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[1].task, 'task2')
        self.assertEqual(entries[2].task, 'task1')


    def test_query_start_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(
                start=datetime.datetime(2011, 1, 1, 12, 5, 0)))
        self.assertEqual(len(entries), 6)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[0].start,
                         datetime.datetime(2011, 1, 1, 12, 5, 0))
        self.assertEqual(entries[0].end,
                         datetime.datetime(2011, 1, 1, 16, 0, 0))
        self.assertEqual(entries[1].task, 'task3')
        self.assertEqual(entries[2].task, 'task4')
        self.assertEqual(entries[3].task, 'task5')
        self.assertEqual(entries[4].task, 'task6')
        self.assertEqual(entries[5].task, 'task7')


    def test_query_end_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(
                end=datetime.datetime(2011, 1, 1, 12, 0, 0)))
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[1].task, 'task2')
        self.assertEqual(entries[2].task, 'task1')
        self.assertEqual(entries[2].start,
                         datetime.datetime(2011, 1, 1, 12, 0, 0))
        self.assertEqual(entries[2].end,
                         datetime.datetime(2011, 1, 1, 12, 0, 0))
        self.assertEqual(len(entries[2].diary), 0)


    def test_query_start_end_filter(self):
        self._create_sample_task_logs()
        entries = list(self.db.get_task_log_entries(
                start=datetime.datetime(2011, 1, 1, 13, 15, 0),
                end=datetime.datetime(2011, 1, 2, 10, 10, 0)))

        self.assertEqual(len(entries), 2)

        self.assertEqual(entries[0].task, 'task1')
        self.assertEqual(entries[0].start,
                         datetime.datetime(2011, 1, 1, 13, 15, 0))
        self.assertEqual(entries[0].end,
                         datetime.datetime(2011, 1, 1, 16, 0, 0))
        self.assertEqual(len(entries[0].diary), 1)
        self.assertEqual(entries[0].diary[0],
                         (datetime.datetime(2011, 1, 1, 13, 30, 0),
                          'task1', 'three'))

        self.assertEqual(entries[1].task, 'task3')
        self.assertEqual(entries[1].start,
                         datetime.datetime(2011, 1, 2, 10, 0, 0))
        self.assertEqual(entries[1].end,
                         datetime.datetime(2011, 1, 2, 10, 10, 0))
        self.assertEqual(len(entries[1].diary), 0)


    def test_task_summary_generator(self):
        self._create_sample_task_logs()
        gen = tracklib.TaskSummaryGenerator()
        gen.read_entries(self.db.get_task_log_entries())

        # Check total times
        self.assertEqual(len(gen.total_time), 7)
        self.assertEqual(gen.total_time["task1"], 16200)
        self.assertEqual(gen.total_time["task2"], 5400)
        self.assertEqual(gen.total_time["task3"], 86400)
        self.assertEqual(gen.total_time["task4"], 3600)
        self.assertEqual(gen.total_time["task5"], 3600)
        self.assertEqual(gen.total_time["task6"], 3600)
        self.assertGreater(gen.total_time["task7"], 10**6)

        # Check context switches
        self.assertEqual(len(gen.switches), 6)
        self.assertEqual(gen.switches["task1"], 1)
        self.assertEqual(gen.switches["task2"], 1)
        self.assertEqual(gen.switches["task4"], 1)
        self.assertEqual(gen.switches["task5"], 1)
        self.assertEqual(gen.switches["task6"], 1)
        self.assertEqual(gen.switches["task7"], 1)

        # Check diary entries
        self.assertEqual(len(gen.diary_entries), 3)
        self.assertEqual(len(gen.diary_entries["task1"]), 2)
        self.assertEqual(gen.diary_entries["task1"][0],
                         (datetime.datetime(2011, 1, 1, 13, 0, 0),
                          'task1', 'two'))
        self.assertEqual(gen.diary_entries["task1"][1],
                         (datetime.datetime(2011, 1, 1, 13, 30, 0),
                          'task1', 'three'))
        self.assertEqual(len(gen.diary_entries["task2"]), 2)
        self.assertEqual(gen.diary_entries["task2"][0],
                         (datetime.datetime(2011, 1, 1, 10, 35, 0),
                          'task2', 'one'))
        self.assertEqual(gen.diary_entries["task2"][1],
                         (datetime.datetime(2011, 1, 1, 10, 35, 5),
                          'task2', '[DONE] Todo for task2'))
        self.assertEqual(len(gen.diary_entries["task3"]), 2)
        self.assertEqual(gen.diary_entries["task3"][0],
                         (datetime.datetime(2011, 1, 2, 10, 15, 0),
                          'task3', '[DONE] Todo for task3'))
        self.assertEqual(gen.diary_entries["task3"][1],
                         (datetime.datetime(2011, 1, 2, 12, 0, 0),
                          'task3', 'four'))


    def test_tag_summary_generator(self):
        self._create_sample_task_logs()
        gen = tracklib.TagSummaryGenerator()
        gen.read_entries(self.db.get_task_log_entries(
                end=datetime.datetime(2011, 1, 3, 15, 0, 0)))

        # Check total times
        self.assertEqual(len(gen.total_time), 3)
        self.assertEqual(gen.total_time["tag1"], 16200+86400+3600+7200)
        self.assertEqual(gen.total_time["tag2"], 5400+86400+3600+7200)
        self.assertEqual(gen.total_time["tag4"], 3600+3600+3600+7200)

        # Check context switches
        self.assertEqual(len(gen.switches), 3)
        self.assertEqual(gen.switches["tag1"], 3)
        self.assertEqual(gen.switches["tag2"], 2)
        self.assertEqual(gen.switches["tag4"], 1)

        # Check diary entries
        self.assertEqual(len(gen.diary_entries), 2)
        self.assertEqual(len(gen.diary_entries["tag1"]), 4)
        self.assertEqual(gen.diary_entries["tag1"][0],
                         (datetime.datetime(2011, 1, 1, 13, 0, 0),
                          'task1', 'two'))
        self.assertEqual(gen.diary_entries["tag1"][1],
                         (datetime.datetime(2011, 1, 1, 13, 30, 0),
                          'task1', 'three'))
        self.assertEqual(gen.diary_entries["tag1"][2],
                         (datetime.datetime(2011, 1, 2, 10, 15, 0),
                          'task3', '[DONE] Todo for task3'))
        self.assertEqual(gen.diary_entries["tag1"][3],
                         (datetime.datetime(2011, 1, 2, 12, 0, 0),
                          'task3', 'four'))
        self.assertEqual(len(gen.diary_entries["tag2"]), 4)
        self.assertEqual(gen.diary_entries["tag2"][0],
                         (datetime.datetime(2011, 1, 1, 10, 35, 0),
                          'task2', 'one'))
        self.assertEqual(gen.diary_entries["tag2"][1],
                         (datetime.datetime(2011, 1, 1, 10, 35, 5),
                          'task2', '[DONE] Todo for task2'))
        self.assertEqual(gen.diary_entries["tag2"][2],
                         (datetime.datetime(2011, 1, 2, 10, 15, 0),
                          'task3', '[DONE] Todo for task3'))
        self.assertEqual(gen.diary_entries["tag2"][3],
                         (datetime.datetime(2011, 1, 2, 12, 0, 0),
                          'task3', 'four'))


    def test_pending_todos_no_filter(self):
        self._create_sample_task_logs()
        todos = self.db.get_pending_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0],
                         (datetime.datetime(2011, 1, 1, 10, 31, 20),
                          "task4", "Todo for task4"))


    def test_pending_todos_filter_before(self):
        self._create_sample_task_logs()
        todos = self.db.get_pending_todos(
                at_datetime=datetime.datetime(2011, 1, 1))
        self.assertEqual(len(todos), 0)


    def test_pending_todos_filter_after(self):
        self._create_sample_task_logs()
        todos = self.db.get_pending_todos(
                at_datetime=datetime.datetime(2011, 1, 3))
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0],
                         (datetime.datetime(2011, 1, 1, 10, 31, 20),
                          "task4", "Todo for task4"))


    def test_pending_todos_filter_between_adding(self):
        self._create_sample_task_logs()
        todos = self.db.get_pending_todos(
                at_datetime=datetime.datetime(2011, 1, 1, 10, 31, 5))
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0],
                         (datetime.datetime(2011, 1, 1, 10, 31, 0),
                          "task2", "Todo for task2"))


    def test_pending_todos_filter_between_completing(self):
        self._create_sample_task_logs()
        todos = self.db.get_pending_todos(
                at_datetime=datetime.datetime(2011, 1, 2))
        self.assertEqual(len(todos), 2)
        self.assertEqual(todos[0],
                         (datetime.datetime(2011, 1, 1, 10, 31, 10),
                          "task3", "Todo for task3"))
        self.assertEqual(todos[1],
                         (datetime.datetime(2011, 1, 1, 10, 31, 20),
                          "task4", "Todo for task4"))



if __name__ == "__main__":
    unittest.main()


