Overview
========

The ``cmdparser`` package contains two modules which are useful for writing
text command parsers, particularly using the builtin Python ``cmd`` module.

The package consists of two modules:

* ``cmdparser.cmdparser``
* ``cmdparser.datetimeparse``

These two modules are discussed below briefly. For more information see the
docstrings of the two modules, and also the ``ttrack`` command-line application
(from which these libraries originated) makes a good example of their use.

.. highlight:: none


Installation
============

Install the ``cmdparser`` package from PyPI. For example, to install using
``pip``::

    pip install cmdparser


.. _cmdparser_overview:

cmdparser Overview
==================

This module allows the creation of parse trees from textual command
specifications of the following form::

    ham ( eggs | chips [spam] | beans [spam [...]] )

These parse trees can then be used to check for matches against particular
command strings, and also allow valid completions of partial command strings to
be listed. To build a parse tree and use it in a few examples, see the
following example code:

.. code-block:: python

    from cmdparser import cmdparser

    parse_tree = cmdparser.parse_spec("one (two|three) <four> [five]")

    # Returns None to indicate successful parse
    parse_tree.check_match(("one", "two", "anything"))
    # Returns an appropriate parsing error message
    parse_tree.check_match(("one", "three", "anything", "six"))
    # Returns the list ["two", "three"]
    parse_tree.get_completions(("one",))

As well as dealing with fixed token strings, dynamic tokens can also be set up
where the list of strings accepted can change over time, or where arbitrary
strings or lists of strings can be accepted. See the module's docstrings for
specifics of the classes available, but as an example:

.. code-block:: python

    from cmdparser import cmdparser

    class ColourToken(cmdparser.Token):
        def get_values(self, context):
            # Static list here, but could easily be dynamic
            return ["red", "orange", "yellow", "green", "blue", "purple"]

    def my_ident_factory(token):
        if token == "number":
            return cmdparser.IntegerToken(token)
        elif token == "colour":
            return ColourToken(token)
        return None

    parse_tree = cmdparser.parse_tree("take <number> <colour> balls",
                                      ident_factory=my_ident_factory)

    # Returns None to indicate successful parse, and the "cmd_fields" dict will
    # be initialised as:
    # { "take": ["take"], "<number>": ["23"],
    #   "<colour>": ["blue"], "balls": ["balls"] }
    cmd_fields = {}
    parse_tree.check_match(("take", "23", "blue", "balls"), fields=cmd_fields)
    # Returns an appropriate parsing error message
    parse_tree.check_match(("take", "all", "red", "balls"))
    # Returns the list ["red", "orange", "yellow", ..., "purple"]
    parse_tree.get_completions(("take", "5"))


There are four classes which are suitable base classes for user-derived
tokens:

``Token``
  This is useful for cases where one of a set of fixed values is suitable,
  where the list may be fixed or dynamic. The ``get_values()`` method should be
  overridden to return a list of valid tokens as strings. Optionally, there is
  also a ``convert()`` method which can be used to convert

``AnyToken``
  Similar to ``Token``, but any string is to be expected. Validation can be
  performed via the ``validate()`` method, but that doesn't allow
  tab-completion as it's only called once the entire command is parsed.
  There is also a ``convert()`` method should it be required.

``AnyTokenString``
  As ``AnyToken`` but all remaining items on the command line are consumed.
  There are ``validate()`` and ``convert()`` methods.

``Subtree``
  Matches an entire command subtree and stores the result against the specified
  token in the ``fields`` dictionary. The command specification string must
  be passed to the constructor, and typically classes will override the
  ``convert()`` method to interpret the command in some way (although this
  is strictly optional).

There are also decorators for use with command handlers derived from ``cmd.Cmd``
which allow command strings to be automatically extracted from docstring help
text, allowing command parsing and completion to be transparently added to the
command-handling methods of the class.

To implement the ``cmd.Cmd`` class, various methods of the form ``do_XXX()`` are
implemented. To add the ``cmdparser`` integration, these methods must contain a
docstring the first line(s) of which form a command specification as outlined
above, followed by a blank line and then any descriptive text for the operation
of the command. The prototype is also altered, taking three arguments - the
usual ``self`` argument, a list of parsed command line items and a
``fields`` dictionary as demonstrated in the example immediately above.

Once the methods have been suitably modified, the ``CmdMethodDecorator``
decorator should be applied to each of them, and the ``CmdClassDecorator``
decorator should be applied to the class definition as a whole:

.. code-block:: python

    from cmdparser import cmdparser

    @cmdparser.CmdClassDecorator()
    class CommandHandler(cmd.Cmd):

        @cmdparser.CmdMethodDecorator():
        def do_command(self, args, fields):
            """command ( add | delete ) <name>

            This is an example command to demonstrate use of the cmd
            decorators.
            """

            # Method body goes here - it will only be called if a command
            # parses successfully according to the specification above.

Note that due to the design of the ``cmd.Cmd`` class, the first token in the
specification must be the same as the method name after the ``do_`` prefix. An
exception will be raised if this is not the case.

The method decorator adds some wrapper code which parses the entered command
according to the specification, and displays an error message if parsing fails.
Should parsing succeed, the implementation method itself is called with the
parsed arguments and fields passed as from the ``check_match()`` method of the
parse tree. Note that when using these decorators, the ``cmd.Cmd`` class
instance is passed as the ``context`` parameter to many of the token methods,
which can be useful for recovering dynamic state.

The class decorator then adds tab-completion methods for every decorated
command method, so applications need not concern themselves with this at all.

It is not necessary to decorate every command method - for very simple commands
which take no arguments it may be simpler to leave them bare. In this case, of
course, the method prototype must match what is expected by ``cmd.Cmd``
(i.e. a single ``string`` parameter beyond the ``self`` parameter). However,
if any method is decorated then the class decorator is required to add the
completion methods.

Finally, note that as a convenience the docstring help for commands has the
leading whitespace of the second line stripped from all lines (on the
assumption that the first line immediately follows a triple quote and hence has
no indentation). Lines are also wrapped to 80 columns in the help text.


datetimeparse Overview
======================

Building on the parse trees within the ``cmdparser`` module, this module adds
specific token types to parse human-readable specifications of date and time.
It allows both absolute and relative dates to be specified, and these are
converted to datetime and other instances as appropriate.

Some examples of the type of specifications supported:

* ``2:35pm on Wednesday last week``
* ``3 days, 2 hours and 5 minutes ago``
* ``3rd March 2012``

The following classes are currently defined:

``DateSubtree``
  Parses a calendar date, including literal dates (``2012-06-15``), descriptive
  versions (``15th June 2012``), days of the week relative to the current day
  (``Thursday last week``) as well as ``yesterday``, ``today`` and
  ``tomorrow``. The returned value is a ``datetime.date`` instance.

``TimeSubtree``
  Parses a time of day in 12 or 24 hour format. The returned value is as
  returned by ``time.localtime()``.

``RelativeTimeSubtree``
  Parses phrases which indicate a time offset from the present time, such as
  ``3 days and 2 hours ago``. The returned value is an instance of
  ``cmdparser.DateDelta``, which is a wrapper class containing a
  ``datetime.timedelta`` and an additional offset in calendar months. It has
  sufficient methods defined to allow it to be added or subtracted from
  a ``datetime.datetime`` in the same way as ``datetime.timedelta``.

``DateTimeSubtree``
  Parses specifications of a date and time, accepting either a combination of
  ``DateSubtree`` and ``TimeSubtree`` phrases, or a ``RelativeTimeSubtree``
  phrase; in the latter case the time is taken as relative to the current
  time. The returned value is a ``datetime.datetime`` instance.

``PastCalendarPeriodSubtree``
  Parses specifications of calendar periods in the past. Examples of the
  phrases this will accept include ``last week``, ``3 months ago``,
  ``week containing 24th March 2012`` and ``between 2012-02-03 and today``.
  The returned value is a 2-tuple of ``datetime.date`` instances representing
  the range of dates specified, where the first date is inclusive and the
  second exclusive.

See the docstrings of the classes for more details and the ``spec`` class
attribute for the complete specification of phrases that each class accepts.


Feedback
========

If you have any questions, problems or requests, please get in touch with me
at andy@andy-pearce.com. If you want to submit a bug, please do so via
`GitHub's issue tracker`_ for the TTrack application, with which ``cmdparser``
shares a repository.

If you want to make changes, the source code is available at GitHub_ - feel
free to send me pull requests if you make an improvement you feel others would
find useful.

.. _GitHub: https://github.com/Cartroo/ttrack
.. _`GitHub's issue tracker`: https://github.com/Cartroo/ttrack/issues

