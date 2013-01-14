#!/usr/bin/python

import contextlib
import datetime
import time
import unittest

from cmdparser import datetimeparse


# Note: This file currently contains fairly minimal testing compared to what's
#       concievably sensible for a library like this. However, coverage of
#       areas which should be handled by underlying Python date/time functions
#       (e.g. handling of leap years) is deliberately avoided to focus tests
#       on the code most likely to be incorrect (i.e. parsing).


# It seems datetime.datetime.now() doesn't use time.time() under the hood like
# most functions, so we add a wrapper class to force it to.
class FakeDatetime(datetime.datetime):

    @staticmethod
    def now():
        return datetime.datetime.fromtimestamp(time.time())


@contextlib.contextmanager
def fake_now(*args):
    def my_time():
        return time.mktime(datetime.datetime(*args).timetuple())
    old_time = time.time
    time.time = my_time
    old_datetime = datetime.datetime
    datetime.datetime = FakeDatetime
    yield
    time.time = old_time
    datetime.datetime = old_datetime


class TestStrptimeToken(unittest.TestCase):

    def test_strptime_one_format(self):
        tree = datetimeparse.StrptimeToken("x", ("%Y-%m-%d",))
        fields = {}
        self.assertEqual(tree.check_match(("2012-02-03",), fields=fields), None)
        self.assertEqual(fields,
                         {"<x>": [time.strptime("2012-02-03", "%Y-%m-%d")]})
        fields = {}
        self.assertEqual(tree.check_match(("2012/4/5",), fields=fields), None)
        self.assertEqual(fields,
                         {"<x>": [time.strptime("2012-4-5", "%Y-%m-%d")]})
        self.assertRegexpMatches(tree.check_match(("12-2-3",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("2012-13-1",)),
                                                  "not a valid")


    def test_strptime_two_formats(self):
        tree = datetimeparse.StrptimeToken("x", ("%B", "%b"))
        fields = {}
        self.assertEqual(tree.check_match(("March",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [time.strptime("March", "%B")]})
        fields = {}
        self.assertEqual(tree.check_match(("Apr",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [time.strptime("Apr", "%b")]})
        self.assertRegexpMatches(tree.check_match(("May1",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("Augu",)), "not a valid")



class TestDateSubtree(unittest.TestCase):

    def test_date(self):
        tree = datetimeparse.DateSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("2012-02-03",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.date(2012, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("15/4/2030",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.date(2030, 4, 15)]})
        self.assertRegexpMatches(tree.check_match(("4-15-2030",)),
                                 "not a valid")


    def test_yesterday_today_tomorrow(self):
        tree = datetimeparse.DateSubtree("x")
        with fake_now(2012, 6, 10, 14, 20, 40):
            fields = {}
            self.assertEqual(tree.check_match(("yesterday",), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 9)]})
            fields = {}
            self.assertEqual(tree.check_match(("today",), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 10)]})
            fields = {}
            self.assertEqual(tree.check_match(("tomorrow",), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 11)]})


    def test_day_of_month(self):
        tree = datetimeparse.DateSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("3", "Nov", "2012"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.date(2012, 11, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("1st", "of", "September", "2013"),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.date(2013, 9, 1)]})
        with fake_now(2010, 1, 1):
            fields = {}
            self.assertEqual(tree.check_match(("22nd", "May"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [datetime.date(2010, 5, 22)]})
        self.assertRegexpMatches(tree.check_match(("33 Nov 2012",)),
                                 "not a valid")
        self.assertRegexpMatches(tree.check_match(("1 of Wibble 2012",)),
                                 "not a valid")


    def test_day_of_week(self):
        tree = datetimeparse.DateSubtree("x")
        # 8th June 2012 was a Friday.
        with fake_now(2012, 6, 8):
            fields = {}
            self.assertEqual(tree.check_match(("Wednesday", "this", "week"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 6)]})
            fields = {}
            self.assertEqual(tree.check_match(("Sun", "last", "week"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 3)]})
            fields = {}
            self.assertEqual(tree.check_match(("Mon", "next", "week"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 11)]})

        # 10th June 2012 was a Sunday.
        with fake_now(2012, 6, 10):
            fields = {}
            self.assertEqual(tree.check_match(("Sunday", "in", "2", "weeks"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 24)]})
            fields = {}
            self.assertEqual(tree.check_match(("Monday", "in", "3", "weeks"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 25)]})
            fields = {}
            self.assertEqual(tree.check_match(("Wednesday", "4", "weeks",
                                               "from", "now"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 7, 4)]})

        # 4th June 2012 was a Monday.
        with fake_now(2012, 6, 4):
            fields = {}
            self.assertEqual(tree.check_match(("Monday", "2", "weeks", "ago"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 5, 21)]})
            fields = {}
            self.assertEqual(tree.check_match(("Sunday", "3", "weeks",
                                               "earlier"), fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 5, 20)]})


    def test_bare_day_of_week(self):
        """Issue: https://github.com/Cartroo/ttrack/issues/5"""
        tree = datetimeparse.DateSubtree("x")
        # 8th June 2012 was a Friday.
        with fake_now(2012, 6, 8):
            fields = {}
            self.assertEqual(tree.check_match(("Wednesday",),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 6)]})
            fields = {}
            self.assertEqual(tree.check_match(("Sun",),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [datetime.date(2012, 6, 10)]})



class TestTimeSubtree(unittest.TestCase):

    def test_time_HMS(self):
        tree = datetimeparse.TimeSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("01:02:03",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(1, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("1.2.3",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(1, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("13:58:59",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(13, 58, 59)]})
        fields = {}
        self.assertEqual(tree.check_match(("00:02:03",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02:03",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02:03am",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02:03pm",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02:03am",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(2, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02:03pm",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(14, 2, 3)]})
        self.assertRegexpMatches(tree.check_match(("24:00:00",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("00:60:00",)), "not a valid")
        # Note: 60 and 61 are accepted to support leap seconds.
        self.assertRegexpMatches(tree.check_match(("00:00:62",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02:03xm",)),
                                 "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02:03a",)),
                                 "not a valid")


    def test_time_HM(self):
        tree = datetimeparse.TimeSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("01:02",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(1, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("1.2",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(1, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("13:59",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(13, 59, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("00:02",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02am",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02pm",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02am",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(2, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02pm",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(14, 2, 0)]})
        self.assertRegexpMatches(tree.check_match(("24:00",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("00:60",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02xm",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02a",)), "not a valid")


    def test_time_ampm(self):
        tree = datetimeparse.TimeSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("12:02:03", "am"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02:03", "pm"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02:03", "am"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.time(2, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02:03", "pm"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.time(14, 2, 3)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02", "am"), fields=fields),
                         None)
        self.assertEqual(fields, {"<x>": [datetime.time(0, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("12:02", "pm"), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(12, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02", "am"), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(2, 2, 0)]})
        fields = {}
        self.assertEqual(tree.check_match(("2:02", "pm"), fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.time(14, 2, 0)]})
        self.assertRegexpMatches(tree.check_match(("01:02:03 xm",)),
                                 "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02 xm",)), "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02:03 a",)),
                                 "not a valid")
        self.assertRegexpMatches(tree.check_match(("01:02 p",)), "not a valid")



class TestDateTimeSubtree(unittest.TestCase):

    def test_date_time(self):
        tree = datetimeparse.DateTimeSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("on", "2012-02-03", "at", "3:25pm",),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.datetime(2012, 2, 3,
                                                            15, 25, 0)]})


    def test_relative(self):
        tree = datetimeparse.DateTimeSubtree("x")
        with fake_now(2012, 6, 8, 13, 14, 15):
            fields = {}
            self.assertEqual(tree.check_match(
                ("3", "days", "and", "15", "minutes", "ago",),
                fields=fields), None)
        self.assertEqual(fields, {"<x>": [datetime.datetime(2012, 6, 5,
                                                            12, 59, 15)]})



class TestPastCalendarPeriodSubtree(unittest.TestCase):

    def test_date(self):

        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("15-10-2012",), fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2012, 10, 15),
                                           datetime.date(2012, 10, 16))]})
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("yesterday",), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 5),
                                               datetime.date(2012, 6, 6))]})



    def test_this_period(self):

        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        # 6th June 2012 is a Wednesday
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("this" ,"week"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 4),
                                               datetime.date(2012, 6, 11))]})
            fields = {}
            self.assertEqual(tree.check_match(("this" ,"month"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 1),
                                               datetime.date(2012, 7, 1))]})
            fields = {}
            self.assertEqual(tree.check_match(("this" ,"year"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 1, 1),
                                               datetime.date(2013, 1, 1))]})


    def test_last_period(self):

        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        # 6th June 2012 is a Wednesday
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("last", "week"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 5, 28),
                                               datetime.date(2012, 6, 4))]})
            fields = {}
            self.assertEqual(tree.check_match(("last", "month"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 5, 1),
                                               datetime.date(2012, 6, 1))]})
            fields = {}
            self.assertEqual(tree.check_match(("last", "year"), fields=fields),
                             None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2011, 1, 1),
                                               datetime.date(2012, 1, 1))]})


    def test_n_periods_ago(self):

        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        # 6th June 2012 is a Wednesday
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("2", "days", "ago"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 4),
                                               datetime.date(2012, 6, 5))]})
            fields = {}
            self.assertEqual(tree.check_match(("3", "weeks", "ago"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 5, 14),
                                               datetime.date(2012, 5, 21))]})
            fields = {}
            self.assertEqual(tree.check_match(("4", "months", "ago"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 2, 1),
                                               datetime.date(2012, 3, 1))]})
            fields = {}
            self.assertEqual(tree.check_match(("5", "years", "ago"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2007, 1, 1),
                                               datetime.date(2008, 1, 1))]})


    def test_week_containing(self):
        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("week", "of", "6-6-2012"),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 4),
                                           datetime.date(2012, 6, 11))]})


    def test_month_containing(self):
        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("month", "with", "6-6-2012"),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 1),
                                           datetime.date(2012, 7, 1))]})


    def test_month(self):
        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("June", "2012"),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 1),
                                           datetime.date(2012, 7, 1))]})
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("August", "last", "year"),
                                              fields=fields), None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2011, 8, 1),
                                               datetime.date(2011, 9, 1))]})


    def test_year(self):
        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("2012",),
                                          fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2012, 1, 1),
                                           datetime.date(2013, 1, 1))]})


    def test_between(self):
        tree = datetimeparse.PastCalendarPeriodSubtree("x")
        fields = {}
        self.assertEqual(tree.check_match(("from", "1-2-2010", "to",
                                           "3-4-2011"), fields=fields), None)
        self.assertEqual(fields, {"<x>": [(datetime.date(2010, 2, 1),
                                           datetime.date(2011, 4, 3))]})
        # 6th June 2012 is a Wednesday
        with fake_now(2012, 6, 6):
            fields = {}
            self.assertEqual(tree.check_match(("between", "last", "Friday",
                                               "and", "today"), fields=fields),
                                               None)
            self.assertEqual(fields, {"<x>": [(datetime.date(2012, 6, 1),
                                               datetime.date(2012, 6, 6))]})



if __name__ == "__main__":
    unittest.main()

