"""Date and time parsing based on cmdparser.

This module contains various classes suitable for use in :mod:`cmdparser`
parse trees which parse combinations of dates and times, including some
natural language phrases which express relative times. The parsing is intended
to be as broad as possible, but quite specific to the English language.
"""


import datetime
import time

import cmdparser


class StrptimeToken(cmdparser.AnyToken):
    """Matches one of a set of strftime() format strings.

    Matches command arguments against the specified list of strftime()
    format strings in turn, converting the value to that returned by
    :func:`time.strptime()`.

    Any combination of date and time specifiers can be put into the format,
    subject to the same restrictions as :func:`time.strptime()`, and the
    only additional feature this class implements is to allow variations
    where ``-`` is replaced by ``/`` (or vice versa) and/or ``:`` is replaced
    by ``.`` (or vice versa). So, if the time format ``"%Y-%m-%d"`` is provided
    then implicitly ``"%Y/%m/%d"`` will also match.
    """

    def __init__(self, name, time_formats):

        def alts(fmts, src, dst):
            for fmt in fmts:
                yield fmt
                if src in fmt:
                    yield fmt.replace(src, dst)
                elif dst in fmt:
                    yield fmt.replace(dst, src)

        cmdparser.AnyToken.__init__(self, name)
        self.time_formats = list(alts(alts(time_formats, "-", "/"), ":", "."))


    def convert(self, arg, context):
        for time_format in self.time_formats:
            try:
                return [time.strptime(arg, time_format)]
            except ValueError:
                pass
        raise ValueError("no matching strptime() formats")



class AgoToken(cmdparser.Token):
    """Simple token which matches synonyms of "ago"."""

    def get_values(self, context):
        return ("ago", "earlier", "before", "previous", "previously", "prior")



class AfterToken(cmdparser.Subtree):
    """Subtree matching phrases which are synonyms of "in the future"."""

    # These are intended as the union of words that might occur before
    # or after a period (e.g. "IN 3 weeks", "3 weeks LATER") so we may
    # end up accepting some grammatically incorrect phrases. The
    # interpretation should always be unambiguous, however.
    spec = """( after | later | on | in [the future] | from (now|today) )"""

    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec)


    def convert(self, args, fields, context):

        return [" ".join(args)]



class DateSubtree(cmdparser.Subtree):
    """A subtree representing an unambiguous calendar day.

    This subtree accepts standard date specifications, but also phrases such
    as ``23rd of March`` and ``Thursday next week``. Two slight subtleties
    should be noted - if omitted, the current week/year are assumed as
    appropriate, and phrases of the form ``(last|this|next) <weekday>`` use
    what I consider to be the most common interpretation in English-speaking
    nations - specifically, a synonym for ``<weekday> (last|this|next) week``.

    These interpretations will likely trip some people up, as this
    library doesn't have the context to decide if the future or past
    dates are more likely. However, they're sufficiently useful and
    common that I think it would be *more* annoying to fail to support
    them at all.
    """

    spec = """( <date>
              | (yesterday|today|tomorrow)
              | <monthday> [of] <month> [<year>]
              | (last|this|next) <weekday>
              | <weekday> [(last|this|next) week
                          | <after> <n> (week|weeks)
                          | <n> (week|weeks) (<ago>|<after>)]
              )"""

    @staticmethod
    def ident_factory(token):

        if token == "date":
            # Don't allow 2-digit years as %d-%m-%y and %y-%m-%d are ambiguous.
            # Also, the US form %m-%d-%Y is not included for similar reasons.
            return StrptimeToken(token, ("%Y-%m-%d", "%d-%m-%Y"))
        elif token == "monthday":
            return StrptimeToken(token, ("%d", "%dth", "%dst", "%dnd", "%drd"))
        elif token == "month":
            return StrptimeToken(token, ("%B", "%b", "%m"))
        elif token == "year":
            return StrptimeToken(token, ("%Y", "%y"))
        elif token == "weekday":
            return StrptimeToken(token, ("%A", "%a"))
        elif token == "n":
            return cmdparser.IntegerToken(token, min_value=1)
        elif token == "ago":
            return AgoToken(token)
        elif token == "after":
            return AfterToken(token)
        return None


    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec,
                                   ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        # <date>
        if "<date>" in fields:
            tm = fields["<date>"][0]
            return [datetime.date(tm.tm_year, tm.tm_mon, tm.tm_mday)]

        # All remaining formats are relative to the current date.
        today = datetime.date.today()

        # ( yesterday | today | tomorrow )
        for offset, name in enumerate(("yesterday", "today", "tomorrow"), -1):
            if name in fields:
                return [today + datetime.timedelta(offset)]

        # <monthday> [of] <month> [<year>]
        if "<monthday>" in fields:
            day = fields["<monthday>"][0].tm_mday
            month = fields["<month>"][0].tm_mon
            year = fields.get("<year>", (today.timetuple(),))[0].tm_year
            return [datetime.date(year, month, day)]

        # (last|this|next) <weekday>
        # <weekday> [ (last|this|next) week
        #           | <after> <n> (week|weeks)
        #           | <n> (week|weeks) (<ago>|<after>) ]
        if "<weekday>" in fields:
            # Determine week offset from today.
            delta = None
            if len(args) == 1:
                delta = 0
            else:
                for offset, name in enumerate(("last", "this", "next"), -1):
                    if args[0] == name or args[1] == name:
                        delta = offset
                        break
            if delta is None and ("<ago>" in fields or "<after>" in fields):
                delta = fields["<n>"][0] * (-1 if "<ago>" in fields else 1)
            assert(delta is not None)
            # Target date is Monday of target week plus weekday number.
            monday = (today + datetime.timedelta(delta * 7)
                      - datetime.timedelta(today.weekday()))
            return [monday + datetime.timedelta(fields["<weekday>"][0].tm_wday)]

        assert(False)



class TimeSubtree(cmdparser.Subtree):
    """A subtree representing a time of day.

    Examples of phrases accepted include ``now`` and ``3:15pm``.
    """

    spec = """( now | <time> ) [am|AM|pm|PM]"""


    @staticmethod
    def ident_factory(token):

        if token == "time":
            return StrptimeToken(token, ("%I:%M:%S%p", "%H:%M:%S",
                                         "%I:%M%p", "%H:%M"))
        return None


    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec,
                                   ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        if "now" in fields:
            tm = time.localtime()
        else:
            tm = fields["<time>"][0]
        ret = datetime.time(tm.tm_hour, tm.tm_min, tm.tm_sec)

        # The additional am/pm exists only for cases where the user inserted a
        # space and so the time otherwise matched as a 24-hour format. Thus, we
        # only catch cases where the am/pm actually changes the time.
        if ("am" in fields or "AM" in fields) and ret.hour == 12:
            ret = ret.replace(hour=0)
        elif ("pm" in fields or "PM" in fields) and 1 <= ret.hour <= 11:
            ret = ret.replace(hour=ret.hour + 12)

        return [ret]


class DateDelta(object):
    """Represents a relative offset in calendar dates.

    This class is a wrapper around :class:`datetime.timedelta` which adds
    calendar month offsets in addition to the days and seconds represented by
    :class:`~datetime.timedelta`. This allows any arbitrary calendar offset
    to be represented.

    Instances of this class may be combined with other :class:`DateDelta`
    instances, :class:`~datetime.timedelta` instances and
    :class:`~datetime.datetime` instances in the same way that
    :class:`~datetime.timedelta` instances can.

    The behaviour of month offsets towards the end of the month is as follows:
    the month is adjusted without changing the day of the month, and if this
    yields an invalid date then ``ValueError`` will be raised. If the date is
    valid then the time delta is then applied to this new date. This behaviour
    may not be ideal in all cases, but is at least unambiguous.
    """

    def __init__(self, delta=None, months=0):
        if delta is not None and not isinstance(delta, datetime.timedelta):
            raise TypeError("%r is not a datetime.timedelta" % (delta,))
        self.delta = datetime.timedelta(0) if delta is None else delta
        self.months = int(months)


    def __str__(self):
        if self.months != 0:
            plural = "" if abs(self.months) == 0 else "s"
            return "%d month%s and %s" % (self.months, plural, self.delta)
        else:
            return str(self.delta)


    def __repr__(self):
        return "datetimeparse.DateDelta(%r, %r)" % (self.delta, self.months)


    def __neg__(self):
        return DateDelta(-self.delta, -self.months)


    def __add__(self, other):
        if isinstance(other, DateDelta):
            return DateDelta(self.delta + other.delta,
                             self.months + other.months)
        if (isinstance(other, datetime.datetime)
            or isinstance(other, datetime.date)):
            new = other.month - 1 + self.months
            base = other.replace(month = (new % 12) + 1,
                                 year = other.year + (new // 12))
            return base + self.delta
        try:
            return self.delta + other
        except (TypeError, ValueError):
            pass
        try:
            return self.months + int(other)
        except (TypeError, ValueError):
            return NotImplemented


    def __sub__(self, other):
        if isinstance(other, DateDelta):
            return DateDelta(self.delta - other.delta,
                             self.months - other.months)
        try:
            return self.delta - other
        except (TypeError, ValueError):
            pass
        try:
            return self.months - int(other)
        except (TypeError, ValueError):
            return NotImplemented


    def __radd__(self, other):
        return self.__add__(other)


    def __rsub__(self, other):
        if (isinstance(other, datetime.datetime)
            or isinstance(other, datetime.date)):
            new = other.month - 1 - self.months
            # If year should change then "new" will be negative - modulo and
            # division do exactly what we want in this case.
            base = other.replace(month = (new % 12) + 1,
                                 year = other.year + (new // 12))
            return base - self.delta
        return NotImplemented



class OffsetSubtree(cmdparser.Subtree):
    """A subtree matching a period of a single unit.

    This subtree matches simple clauses of the form ``N units`` where a unit
    may be a second, minute, hour, day, week, month or year. The converted
    value is a :class:`DateDelta` representing the specified length of time.

    This subtree is typically only used indirectly via
    :class:`RelativeTimeSubtree`.
    """

    @staticmethod
    def ident_factory(token):

        if token == "n":
            return cmdparser.IntegerToken(token, min_value=1)
        return None


    def __init__(self, name):

        # We match any base period name with an option "s" for plurals and an
        # optional comma for phrases such as "4 hours, 2 minutes and 1 second".
        spec_items = []
        for base in ("second", "minute", "hour", "day", "week", "month",
                     "year"):
            spec_items.extend((base, base + "s", base + ",", base + "s,"))
        cmdparser.Subtree.__init__(self, name, "<n> (" + "|".join(spec_items)
                                   + ")", ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        try:
            value = int(fields["<n>"][0])
        except (ValueError, IndexError, KeyError):
            raise ValueError("invalid period count specified")

        for period in fields.keys():
            if period.startswith("second"):
                return [DateDelta(datetime.timedelta(0, value))]
            if period.startswith("minute"):
                return [DateDelta(datetime.timedelta(0, 60 * value))]
            if period.startswith("hour"):
                return [DateDelta(datetime.timedelta(0, 3600 * value))]
            if period.startswith("day"):
                return [DateDelta(datetime.timedelta(value))]
            if period.startswith("week"):
                return [DateDelta(datetime.timedelta(7 * value))]
            if period.startswith("month"):
                return [DateDelta(None, value)]
            if period.startswith("year"):
                return [DateDelta(None, value * 12)]

        raise ValueError("no matching periods")



class RelativeTimeSubtree(cmdparser.Subtree):
    """A subtree matching a relative time.

    This subtree matches times relative to a fixed point in time - for example,
    phrases such as ``2 hours ago`` and ``in 3 days and 5 minutes``. Its
    converted value is a :class:`DateDelta` instance.
    """

    spec = """( <after> (<offset> [,|and]) [...]
              | (<offset> [,|and]) [...] (<after>|<ago>) )"""

    @staticmethod
    def ident_factory(token):

        if token == "offset":
            return OffsetSubtree(token)
        elif token == "ago":
            return AgoToken(token)
        elif token == "after":
            return AfterToken(token)
        return None


    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec,
                                   ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        delta = DateDelta()
        for item in fields["<offset>"]:
            delta += item
        if "<ago>" in fields:
            return [-delta]
        else:
            return [delta]



class DateTimeSubtree(cmdparser.Subtree):
    """A subtree matching a specific point in time.

    This subtree attempts to parse specifications of a date and time, either
    absolute or relative to the current time (as returned by
    :meth:`datetime.datetime.now()`). The converted value is a
    :class:`~datetime.datetime` instance.
    """

    spec = """( [on] <date> [at] <time>
              | [at] <time> [ [on] <date> ]
              | <relative> )"""

    @staticmethod
    def ident_factory(token):

        if token == "date":
            return DateSubtree(token)
        elif token == "time":
            return TimeSubtree(token)
        elif token == "relative":
            return RelativeTimeSubtree(token)
        return None


    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec,
                                   ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        if "<time>" in fields:
            t = fields["<time>"][0]
            if "<date>" in fields:
                d = fields["<date>"][0]
            else:
                d = datetime.date.today()
            return [datetime.datetime(d.year, d.month, d.day,
                                      t.hour, t.minute, t.second)]
        elif "<relative>" in fields:
            return [datetime.datetime.now() + fields["<relative>"][0]]
        raise ValueError("invalid subtree syntax")



class PastCalendarPeriodSubtree(cmdparser.Subtree):
    """A subtree matching a date range in the past.

    Examples of matched phrases include ``last month``, ``january 2011`` and
    ``week of 2012-03-22``. Aside from calendar periods, arbitrary periods
    can be specified in the form ``between <date> and <date>`` or various
    synonymous phrases - in this form, the start date is inclusive and the
    end date is exclusive.

    This subtree doesn't attempt to match dates in the future, although neither
    does it have any special checks to avoid matching future dates (for
    example, if a calendar date is specified any valid date will match).
    Only dates are permitted - times of day will fail to match.

    The converted value is a 2-tuple ``(start, end)`` of :class:`datetime.date`
    instances, where ``start`` is inclusive and ``end`` is exclusive.
    """

    spec = """( <date> | <year> | (last|this) (week|month|year)
              | <n> (day|days|week|weeks|month|months|year|years) <ago>
              | (week|month) (of|with|containing|starting|commencing) <date>
              | <month> [<year>|(last|this) year]
              | [between|from] <start> (and|to|until|through|thru) <end> ) """


    @staticmethod
    def ident_factory(token):

        if token == "date":
            return DateSubtree(token)
        elif token == "weekday":
            return StrptimeToken(token, ("%A", "%a"))
        elif token == "n":
            return cmdparser.IntegerToken(token, min_value=1)
        elif token == "ago":
            return AgoToken(token)
        elif token in ("date", "start", "end"):
            # Don't allow 2-digit years as %d-%m-%y and %y-%m-%d are ambiguous.
            # Also, the US form %m-%d-%Y is not included for similar reasons.
            return DateSubtree(token)
        elif token == "month":
            return StrptimeToken(token, ("%B", "%b", "%m"))
        elif token == "year":
            return StrptimeToken(token, ("%Y", "%y"))
        return None


    def __init__(self, name):

        cmdparser.Subtree.__init__(self, name, self.spec,
                                   ident_factory=self.ident_factory)


    def convert(self, args, fields, context):

        # (last|this) (week|month|year)
        if args[0] in ("last", "this"):
            today = datetime.date.today()
            offset = -1 if args[0] == "last" else 0
            if args[1] == "week":
                monday = (today + datetime.timedelta(offset * 7)
                          - datetime.timedelta(today.weekday()))
                return [(monday, monday + datetime.timedelta(7))]
            elif args[1] == "month":
                first = today.replace(day=1) + DateDelta(months=offset)
                return [(first, first + DateDelta(months=1))]
            else:
                first = datetime.date(today.year + offset, 1, 1)
                return [(first, first.replace(year=first.year + 1))]

        # <n> (day|days|week|weeks|month|months|year|years) <ago>
        if "<n>" in fields:
            today = datetime.date.today()
            if args[1].startswith("day"):
                start = today - datetime.timedelta(fields["<n>"][0])
                return [(start, start + datetime.timedelta(1))]
            elif args[1].startswith("week"):
                monday = (today - datetime.timedelta(7 * fields["<n>"][0])
                          - datetime.timedelta(today.weekday()))
                return [(monday, monday + datetime.timedelta(7))]
            elif args[1].startswith("month"):
                day = today.replace(day=1) - DateDelta(months=fields["<n>"][0])
                return [(day, day + DateDelta(months=1))]
            else:
                day = datetime.date(today.year - fields["<n>"][0], 1, 1)
                return [(day, day.replace(year=day.year + 1))]

        # (week|month) (of|with|containing|starting|commencing) <date>
        if args[0] in ("week", "month"):
            day = fields["<date>"][0]
            if args[0] == "week":
                monday = day - datetime.timedelta(day.weekday())
                return [(monday, monday + datetime.timedelta(7))]
            else:
                first = day.replace(day=1)
                return [(first, first + DateDelta(months=1))]

        # <date>
        if "<date>" in fields:
            day = fields["<date>"][0]
            return [(day, day + datetime.timedelta(1))]

        # <month> [<year>|(last|this) year]
        if "<month>" in fields:
            month = fields["<month>"][0].tm_mon
            if "<year>" in fields:
                year = fields["<year>"][0].tm_year
            else:
                year = datetime.date.today().year
                if "last" in fields:
                    year -= 1
            start = datetime.date(year, month, 1)
            return [(start, start + DateDelta(months=1))]

        # <year>
        if "<year>" in fields:
            start = datetime.date(fields["<year>"][0].tm_year, 1, 1)
            return [(start, start.replace(year=start.year + 1))]

        # [between|from] <start> (and|to|until|through|thru) <end>
        return [(fields["<start>"][0], fields["<end>"][0])]

