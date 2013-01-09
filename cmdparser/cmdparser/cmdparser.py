"""A simple command parsing library.

This module allows textual command specifications to be "compiled" into parse
tree structures which can then be used to parse command strings entered by a
user. It also provides some decorators to use with the Python builtin
:mod:`cmd` module to use these command parsers to ease some of the effort
checking command syntax and extracting the relevant values.

The classes which make up the parse tree are all classes derived from a base
:class:`ParseItem`. This base class provides two methods which are typically
called on the root of a parse tree:

:meth:`ParseItem.check_match()`
  This method is used to check a complete command string as entered by a user
  against the parse tree to check for a match. Calling code is responsible for
  splitting the command string into a list of strings first, so application can
  select their own quoting conventions. This list is then passed to
  ``check_match()`` which returns ``None``, to indicate the command matches,
  or a string containing an error message if the match fails. This method also
  takes a set of other parameters for extracting items from the command string -
  see the documentation for the method for more details.

:meth:`ParseItem.get_completions()`
  This method is passed a list of command-line items as ``check_match()``, but
  in this case the list is typically incomplete - the function returns a list
  of strings indicating the valid tokens which could follow the command
  specified, if any. This is used to implement tab-completion.

.. highlight:: none

Parse trees can be built by manually constructing class instances, but the
intended method is to use the :func:`parse_spec()` function to convert a string
command specification into the corresponding parse tree. Command specifications
consist of a sequence of specifiers, each of which can be a fixed string, an
identifier in angle brackets, an alternation in round brackes or an optional
alternation in square brackets. An example specification is shown below::

    one ( two | three [ four | five ] ) <six> [...] <seven...>

This specification demonstrates most of the accepted syntax elements for
command specifications. It specifies that commands must consist of the fixed
item ``one`` followed by either ``two`` or ``three``, where ``three`` may also
optionally be followed by either ``four`` or ``five`` (but not both). After
this, the identifer ``<six>`` occurs - identifiers are explained below. Next,
the ``[...]`` indicates that the previous item may occur one or more times, so
matching continues against ``<six>`` until a command-line item fails to match.
After this point the ellipsis at the end of the ``<seven...>`` identifier
indicates that this token will consume all remaining command-line items.

This is all relatively straightforward except for the identifiers - these may
represent arbitrarily complex sequences of items, from the basic :class:`Token`
class, which matches a single command-line item from a fixed list, to
:class:`Subtree` instances, which match against an entire nested parse tree.
Applications can create derived classes from various bases to customise the
matching behaviour.

To specify the class of each identifier, a function is passed via the
``ident_factory`` keyword parameter of the :func:`parse_spec()` function. This
function should take a single parameter which is the name of the identifier
(omitting the angle backets), and should return either an instance of a class
derived from :class:`ParseItem`, or ``None`` - if the function returns ``None``
then :func:`parse_spec()` will assume the identifier is of the
:class:`AnyToken` class, which matches any single command-line item.

Taking the example above, if the ``ident_factory`` function returned an
instance of the :class:`IntegerToken` class when passed the string ``"six"``
as its argument then the ``<six>`` identifier in the command specification
would only match strings which were valid integers. Note that in this
particular example, if the ``ident_factory`` returned ``None`` (or if no
factory were specified) then the ``<seven...>`` identifier would never match
anything because the remaining command-line would always be consumed by
repetitions of ``<six>`` (using the default :class:`AnyToken`). This
illustrates that the matching is purely greedy on a left-to-right basis, so
it's quite possible (though not useful) to invent a command specification which
will not match anything.

The instances returned by ``ident_factory`` can be any class derived from
:class:`ParseItem`. The ``cmdparser`` module provides several useful classes
which can be used directly, and also used as base classes to avoid applications
and other modules having to duplicate functionality. It's generally intended
that the following classes act as base classes for application-specific
versions:

:class:`Token`
  Override the :meth:`~Token.get_values()` method to return a list of strings
  to match - this list isn't cached so may be entirely dynamic, but note that
  unlike the :class:`AnyToken` class the list of acceptable items must be a
  finite list. Use of this class allows tab-completion of the values.

:class:`AnyToken`
  Similar to :class:`Token`, but in this case any string will be accepted so
  tab-completion isn't possible. Derived instances typically override one or
  both of the :meth:`~AnyToken.convert()` and :meth:`~AnyToken.validate()`
  methods to provide their specific behaviour.

:class:`AnyTokenString`
  Matches all remaining command-line items, and is otherwise similar to
  :class:`AnyToken`.

For both :class:`AnyToken` and :class:`AnyTokenString`, there is a
:meth:`~AnyToken.validate()` method which is called just after matching, and
which should return ``True`` if the matched value is acceptable, ``False``
otherwise. Where the list of acceptable items is known in advance it's
typically better to use :class:`Token` as the base class to enable
tab-completion, but this is not always feasible (e.g. any string consisting of
only alphanumerics should be accepted). If this method returns ``False``,
matching will continue with any other possibilities as usual. Also see the
implementation of :class:`IntegerToken` for a simple illustration of how this
method may be used.

Many of the classes also support a ``~Token.convert()`` method, which is used
to convert the command-line items into a more useful form for the application.
For example, as well as only matching strings which are a sequence of digits,
:class:`IntegerToken` also converts the string into an ``int`` value.

These converted values go into the ``fields`` dictionary, which is an optional
parameter to the :meth:`~ParseItem.check_match()` method. If not ``None``, this
parameter must be a ``dict``-like instance which is used to store matched
values indexed by identifier name. The key is the string form of the item as
used in the command specification (e.g. ``"<six>"``) and the value is a list
of the matched items from the command instance being matched. A list is used
because in cases of repetition an identifier may match multiple times. This is
perhaps best illustrated with an example using the following specification::

    set <name> ( age <number> | nicknames <nick> [...] )

For this example, assume that the ``ident_factory`` function returns an
:class:`IntegerToken` instance for the ``<number>`` identifier and returns
``None`` in all other cases, leaving ``<name>`` and ``<nick>`` as the default
:class:`AnyToken` class.

.. highlight:: python

If the following call were made on the compiled parse tree::

    cmd_fields = {}
    parse_tree.check_match(("set", "Andrew", "age", "98"), fields=cmd_fields)

Then the ``cmd_fields`` dictionary would appear as follows after the call::

    { "set": ["set"], "<name>": ["Andrew"], "age": ["age"], "<number>": [98] }

By comparison, the same call but using the following command items::

    ("set", "Andrew", "nicknames", "Andy", "Ace", "Trouble")

Would result in a dictionary populated as follows::

    { "set": ["set"], "<name>": ["Andrew"], "nicknames": ["nicknames"],
      "<nick>": ["Andy", "Ace", "Trouble"] }

Finally, the :class:`CmdMethodDecorator` and :class:`CmdClassDecorator` classes
deserve a brief mention. As their name suggests they're intended for use as a
method and class decorator respectively, specifically for use with the builtin
Python :mod:`cmd` module.

Decorating the ``do_XXX()`` methods and the entire :class:`cmd.Cmd` class
instance itself with the respective decorators will use the ``cmdparser``
facilities to parse entered commands, only passing valid commands on to the
method itself and supporting the dict-based forms of command-line item
extraction outlined above. The command specification itself is automatically
extracted from the command's docstring, so the docstrings must start with a
compatible command specification (possibly spanning multiple lines) and then
contain a blank line and then arbitrary help text. The entire docstring is
used by :class:`cmd.Cmd` as the online help - this automatic extraction keeps
the documentation and functional code in close harmony.

A simple example of these decorators is shown below::

   import cmd
   from cmdparser import cmdparser

   def _ident_factory(token_name):
       if token_name == "num":
           return cmdparser.IntegerToken(token_name)
       return None

   @cmdparser.CmdClassDecorator()
   class Handler(cmd.Cmd):

       @cmdparser.CmdMethodDecorator(token_factory=_ident_factory)
       def do_display(self, args, fields):
           \"\"\"display <num> <msg...>

           Displays the specified message a total of <num> times.
           \"\"\"

           for i in xrange(fields["<num>"][0]):
               print " ".join(fields["<msg...>"])


   if __name__ == "__main__":
       interpreter = Handler()
       interpreter.cmdloop("Welcome to the test handler")


See the docstrings of these decorators for more information on their use.
"""


import itertools
import shlex


class ParseError(Exception):
    """Error parsing command specification."""
    pass



class MatchError(Exception):
    """Raised internally if a command fails to match the specification."""
    pass



class CallTracer(object):
    """Utility class for debugging parse tree call chain."""

    def __init__(self, trace, parse_item, items):
        self.trace = trace
        self.name = parse_item.__class__.__name__ + "(" + str(parse_item) + ")"
        if trace is not None:
            trace.append(">>> " + self.name + ": " + repr(items))


    def __del__(self):
        if self.trace is not None:
            self.trace.append("<<< " + self.name)


    def fail(self, items):
        if self.trace is not None:
            self.trace.append("!! " + self.name + " [" + " ".join(items) + "]")



class ParseItem(object):
    """Base class for all items in a command specification."""

    def __str__(self):
        raise NotImplementedError()


    def finalise(self):
        """Called when an object is final.

        The default does nothing, derived classes can raise :class:`ParseError`
        if the object isn't valid as it stands for any reason.
        """
        pass


    def add(self, child):
        """Called when a child item is added.

        The default is to disallow children, derived classes can override.
        """
        raise ParseError("children not allowed")


    def pop(self):
        """Called to recover and remove the most recently-added child item.

        The default is to disallow children, derived classes can override.
        """
        raise ParseError("children not allowed")


    def add_alternate(self):
        """Called to add a new alternate option.

        The default is to disallow alternates, derived classes can override.
        """
        raise ParseError("alternates not allowed")


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """Called during the match process.

        Should attempt to match item's specification against list of
        command-line items in ``compare_items`` and either return the remains
        of ``compare_items`` with consumed items removed, or raise
        :class:`MatchError` if the command-line doesn't match.

        If the item has consumed a command-line argument, it should store
        it against the item's name in the ``fields`` dict if that parameter is
        not ``None``.

        If the ``completions`` field is not ``None`` and ``compare_items`` is
        empty (i.e. just after the matched string) then the item should store a
        list of valid following token strings in ``completions`` (which should
        be treated as a ``set``) and then raise :class:`MatchError` - this only
        applies to items which support tab-completion, items which match any
        string should leave the set alone.

        The ``trace`` parameter, if supplied, should be a ``list``. As each
        class's ``match()`` function is entered or left, a string representing
        it is appended to the list. This is for debugging purposes.

        The ``context`` parameter is reflected down through all calls to
        ``match()`` methods so application-provided tokens can use it. For
        example, the :mod:`cmd` integration passes the :class:`cmd.Cmd`
        instance as the context.

        The default is to raise a :class:`MatchError`, derived classes should
        override this behaviour.
        """
        raise MatchError("invalid use of ParseItem (programming error)")


    def check_match(self, items, fields=None, trace=None, context=None):
        """Return None if the specified command-line is valid and complete.

        If the command-line doesn't match, an appropriate error explaining the
        lack of match is returned.

        Calling code should typically use this instead of calling
        :meth:`match()` directly. Derived classes shouldn't typically override
        this method.

        The ``fields`` parameter should be ``None`` or a dictionary - if
        specified, parsed items will be stored in the dictionary under their
        command specifiers.

        The ``trace`` field should be ``None`` or a list - if specified,
        function entries and exits and parse failures are traced by appending
        appropriate strings to the list. This is only of use for debugging
        issues in the parsing code itself.

        The ``context`` parameter is passed into various methods of the
        parse tree instances, which may be useful for derived classes.
        """
        try:
            unparsed = self.match(items, fields=fields, trace=trace,
                                  context=context)
            if unparsed:
                suffix = " ".join(unparsed)
                suffix = suffix[:29] + "..." if len(suffix) > 32 else suffix
                return "command invalid somewhere in: %r" % (suffix,)
            else:
                return None
        except MatchError, e:
            return str(e)


    def get_completions(self, items, context=None):
        """Return ``set`` of valid tokens to follow partial command-line.

        Calling code should typically use this instead of calling
        :meth:`match()` directly. Derived classes shouldn't typically
        override this method.

        The ``items`` parameter should be a list of strings representing
        the command-line entered at the point the completion key is pressed,
        not including any partial argument. Note that these classes do not
        filter returned values according to a half-entered final argument,
        which is why it is omitted. Such filtering is done within the
        completion function added by :class:`CmdMethodDecorator` if the
        :mod:`cmd` integration is being used, or by application code
        otherwise.

        The ``context`` parameter is passed into various methods of the
        parse tree instances, which may be useful for derived classes.
        """
        try:
            completions = set()
            self.match(items, completions=completions, context=context)
        except MatchError:
            pass
        return completions



class Sequence(ParseItem):
    """Matches a sequential series of items, each of which must match."""

    def __init__(self):
        self.items = []


    def __str__(self):
        return " ".join(str(i) for i in self.items)


    def finalise(self):
        """See :meth:`ParseItem.finalise()`."""

        if not self.items:
            raise ParseError("empty sequence")
        for item in self.items:
            item.finalise()


    def add(self, child):
        """See :meth:`ParseItem.add()`."""

        assert isinstance(child, ParseItem)
        self.items.append(child)


    def pop(self):
        """See :meth:`ParseItem.pop()`."""

        try:
            return self.items.pop()
        except IndexError:
            raise ParseError("no child item to pop")


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        for item in self.items:
            compare_items = item.match(compare_items, fields=fields,
                                       completions=completions, trace=trace,
                                       context=context)
        return compare_items



class Repeater(ParseItem):
    """Matches a single specified item one or more times."""

    def __init__(self):
        self.item = None


    def __str__(self):
        return str(self.item) + " [...]"


    def finalise(self):
        """See :meth:`ParseItem.finalise()`."""
        if self.item is None:
            raise ParseError("empty repeater")


    def add(self, child):
        """See :meth:`ParseItem.add()`."""

        assert isinstance(child, ParseItem)
        if isinstance(child, Repeater) or isinstance(child, AnyTokenString):
            raise ParseError("repeater cannot accept a repeating child")
        if self.item is not None:
            raise ParseError("repeater may only have a single child")
        self.item = child


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        repeats = 0
        while True:
            try:
                new_items = self.item.match(compare_items, fields=fields,
                                            completions=completions,
                                            trace=trace, context=context)
                compare_items = new_items
                repeats += 1
            except MatchError, e:
                if repeats == 0:
                    tracer.fail(e.args[0])
                    raise
                return compare_items



class Subtree(ParseItem):
    """Matches an entire parse tree, converting the result to a single value.

    This item is intended for use in applications which wish to present
    a potentially complicated potion of the parse tree as a single argument.
    A good example of this is a time specification, which might accept
    strings such as ``"yesterday at 3:34"`` or ``"25 minutes ago"``, but wish
    to store the result in the fields dictionary as a single ``datetime``
    instance.

    By default, command completion within the subtree will be enabled - if the
    tree should be treated more like a token then it may be useful to disable
    completion (i.e. always return no completions), and this can be done by
    setting the ``suppress_completion`` parameter to the constructor to
    ``True``.
    """

    def __init__(self, name, spec, ident_factory=None,
                 suppress_completion=False):
        """Construct a new :class:`Subtree` instance.

        The ``name`` parameter should be that passed to the ``ident_factory``
        method which is constructing this class and the ``spec`` parameter
        should be the string command specification, as suitable for parsing
        by :func:`parse_spec()`.

        The ``ident_factory`` parameter may be used to specify a factory for
        this subtree - note that this defaults to ``None`` and not the
        ``ident_factory`` for the parent parse tree (though there is no reason
        why the same function can't be explicitly passed).

        Typically tab-completion is allowed for parts of the subtree - to
        disable this, for example if the fact that a subtree is being used
        should be hidden from the user, set ``suppress_completion`` to ``True``.
        """

        self.name = name
        self.suppress_completion = suppress_completion
        # Allow any parsing exceptions to be passed out of constructor.
        self.parse_tree = parse_spec(spec, ident_factory=ident_factory)


    def __str__(self):
        return '<' + str(self.name) + '>'


    def convert(self, args, fields, context):
        """Convert matched items into values for the ``fields`` dictionary.

        This method is called when the subtree matches and is passed the
        subset of the argument list which matched as well as the ``fields``
        dictionary that was filled in during the matching of the subtree.
        The method should return a list of values which will be appended to
        those for the identifier for this subtree in the parent ``fields``
        dictionary. The number of items returned need bear no relation to
        the number of parameters actually matched and may even be an empty
        list (although this is typically not very useful).

        The base class instance simply returns the list of command-line items
        which matched the subtree.
        """
        return args


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        subtree_fields = {}
        completions = None if self.suppress_completion else completions
        new_items = self.parse_tree.match(compare_items, fields=subtree_fields,
                                          completions=completions, trace=trace,
                                          context=context)
        consumed = compare_items[:len(compare_items)-len(new_items)]
        if fields is not None:
            field_value = fields.setdefault(str(self), [])
            field_value.extend(self.convert(consumed, subtree_fields, context))
        return new_items



class Alternation(ParseItem):
    """Matches any of a list of alternative Sequence items.

    Alternation instances can also be marked optional by setting the
    ``optional`` parameter to ``True`` in the constructor - this menas that if
    none of the options match, they'll return success without consuming any
    items instead of raising :class:`MatchError`.

    Note that matching is greedy with no back-tracking, so if an optional item
    matches the command line argument(s) will always be consumed even if this
    leads to a MatchError later in the string which wouldn't have occurred had
    the optional item chosen to match nothing instead.
    """

    def __init__(self, optional=False):
        """Construct a new :class:`Alternation` instance.

        The alternation is considered mandatory unless the ``optional``
        parameter is set to ``True`` on construction.
        """

        self.optional = optional
        self.options = []
        self.add_alternate()


    def __str__(self):
        seps = "[]" if self.optional else "()"
        return seps[0] + "|".join(str(i) for i in self.options) + seps[1]


    def finalise(self):
        """See :meth:`ParseItem.finalise()`."""

        if not self.options:
            raise ParseError("empty alternation")
        for option in self.options:
            option.finalise()


    def add(self, child):
        """See :meth:`ParseItem.add()`."""

        assert isinstance(child, ParseItem)
        self.options[-1].add(child)


    def pop(self):
        """See :meth:`ParseItem.pop()`."""

        return self.options[-1].pop()


    def add_alternate(self):
        """See :meth:`ParseItem.add_alternate()`."""

        self.options.append(Sequence())


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        errors = set()
        for option in self.options:
            try:
                return option.match(compare_items, fields=fields,
                                    completions=completions,
                                    trace=trace, context=context)
            except MatchError, e:
                errors.add(str(e))
        if self.optional:
            return compare_items
        else:
            tracer.fail(compare_items)
            raise MatchError(" and ".join(errors))



class Token(ParseItem):
    """Matches a single, fixed item.

    This class is used for literal strings in command specifications, where only
    a single item will match in a given position.

    This class also doubles as the base class for any application-specific items
    which should match one or more fixed strings. The list can change over time,
    but at any point in time there's a deterministic list of valid options.
    Such derived classes should simply override :meth:`get_values()` to return
    a list of possible options.
    """

    def __init__(self, name, token=None):
        """Construct a new :class:`Token` instance.

        The ``name`` parameter specifies the name of the identifier for this
        token, which is also used as the fixed string to match for the
        base class unless the optional ``token`` parameter is also set. This
        can be used, for example, to use different tokens in branches of an
        alternation, but always use the same name in the ``fields`` dict.
        For example, the ``x:y`` syntax in :func:`parse_spec()` is one way
        to apply an alternate name to a fixed token.
        """
        self.name = name
        self.token = name if token is None else token


    def __str__(self):
        # Slightly clumsy, but alter the return value depending on whether a
        # derived class has overridden get_values(). This is partly to make
        # life easier for clients of the library, and partly because some
        # people may simply forget to override __str__().
        if self.get_values.im_func == Token.get_values.im_func:
            return self.token
        else:
            # Add angle-brackets for derived classes, on the assumption that
            # the list of items is dynamic and hence this is an identifier.
            return "<" + self.name + ">"


    def get_values(self, context):
        """Return the current list of valid tokens.

        Derived classes should override this method to return the full list of
        every valid token. This method is invoked on demand with no caching
        (though there is nothing to stop derived instances doing their own
        caching should it be appropriate).

        The base class version returns a single-item list containing the fixed
        token passed to the constructor.
        """
        return [self.token]


    def convert(self, arg, context):
        """Argument conversion hook.

        A matched argument is filtered through this method before being placed
        in the ``fields`` dictionary passed on the :meth:`~ParseItem.match()`
        method. This allows derived classes to, for example, convert the type of
        the argument to something that's more useful to the code using the value
        or perform any other arbitrary transformations.

        The first argument (after ``self``) is the matched token string, the
        second is the context passed to :meth:`~ParseItem.match()`. The return
        value should be a list to be added to the list of values for the field.
        """
        return [arg]


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        if not compare_items:
            if completions is not None:
                completions.update(self.get_values(context))
            tracer.fail([])
            raise MatchError("insufficient args for %r" % (str(self),))
        arg = compare_items[0]
        for value in self.get_values(context):
            if arg == value:
                if fields is not None:
                    arg_list = fields.setdefault(str(self), [])
                    arg_list.extend(self.convert(arg, context))
                return compare_items[1:]
        tracer.fail(compare_items)
        raise MatchError("%r doesn't match %r" % (arg, str(self)))



class AnyToken(ParseItem):
    """Matches any single item."""

    def __init__(self, name):
        """Construct a new :class:`AnyToken` instance.

        The ``name`` parameter specifies the name of the identifier for this
        token.
        """
        self.name = name


    def __str__(self):
        return "<" + self.name + ">"


    def validate(self, arg, context):
        """Validation hook.

        Derived classes can use this to indicate whether a given parameter
        value is accpetable. Return ``True`` if yes, ``False`` otherwise.
        The ``arg`` parameter will be the string argument matched and
        the ``context`` parameter is that passed to :meth:`~ParseItem.match()`.

        The base class version calls :meth:`convert()` and then returns ``True``
        iff that call doesn't raise ``ValueError`` or ``False`` otherwise.
        Note that no other exceptions are caught. This allows simple derived
        classes to override only the :meth:`convert()` method but allow the
        flexibility to do something more efficient in ``validate()`` if
        required.

        For cases where a small set of values is acceptable it may be more
        appropriate to derive from :class:`Token` and override
        :meth:`~Token.get_values()`, which has the advantage of also allowing
        tab-completion.
        """
        try:
            self.convert(arg, context)
            return True
        except ValueError:
            return False


    def convert(self, arg, context):
        """See :meth:`Token.convert()`."""

        return [arg]


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        if not compare_items:
            tracer.fail([])
            raise MatchError("insufficient args for %r" % (str(self),))
        arg = compare_items[0]
        if not self.validate(arg, context):
            raise MatchError("%r is not a valid %s" % (arg, str(self)))
        if fields is not None:
            fields.setdefault(str(self), []).extend(self.convert(arg, context))
        return compare_items[1:]



class IntegerToken(AnyToken):
    """Derivation of :class:`AnyToken` which parses integers.

    This class matches any sequence of decimal digits and converts them into
    an ``int`` in the ``fields`` dictionary. The range of the integer can
    also optionally be bounded at one or both ends.
    """

    def __init__(self, name, min_value=None, max_value=None, base=0):
        """Construct a new :class:`IntegerToken` instance.

        The ``name`` parameter is the name of the identifier, as taken by
        :class:`AnyToken`.

        The optional ``min_value`` and ``max_value`` parameters specify lower
        and upper bounds respectively for the value if the integer - a value
        outside this range will be rejected at the matchin stage. The limits
        are inclusive and default to the appropriate infinity, so negative
        values will be accepted unless ``min_value`` is set to zero or greater.

        The optional ``base`` parameter specifies the number base to use when
        interpreting the integer - this is passed directly as the second
        argument to the :func:`int()` constructor and defaults to zero, which
        causes the base to be guessed based on the number format.
        """

        # Validate base (will raise ValueError if not valid).
        int("0", base)

        AnyToken.__init__(self, name)
        self.min_value = min_value
        self.max_value = max_value
        self.base = int(base)


    def convert(self, arg, context):
        """Convert argument to ``int``.

        See :meth:`Token.convert()` for more details about argument conversion
        and the documentation for :meth:`__init__()` for the operation of this
        class in particular.
        """
        value = int(arg, self.base)
        if (self.min_value is not None and value < self.min_value or
            self.max_value is not None and value > self.max_value):
            raise ValueError("integer value %d outside range %d-%d" %
                             (value, self.min_value, self.max_value))
        return [value]




class AnyTokenString(ParseItem):
    """Matches the remainder of the command string.

    This class will match all remaining command-line arguments and then either
    accept or reject them based on the result of the :meth:`validate()` method.
    """

    def __init__(self, name):
        """Construct a new :class:`IntegerToken` instance.

        The ``name`` parameter is the name of the identifier, as taken by
        :class:`AnyToken`.
        """
        self.name = name


    def __str__(self):
        return "<" + self.name + "...>"


    def validate(self, items, context):
        """Validation hook.

        Derived classes can use this to indicate whether a given parameter
        list is acceptable. Return ``True`` if yes, ``False`` otherwise. The
        ``items`` parameter will be the list of command arguments matched
        and the ``context`` parameter is that passed to
        :meth:`~ParseItem.match()`.

        The base class version calls :meth:`convert()` and then returns ``True``
        iff that call doesn't raise ``ValueError`` or ``False``otherwise. Note
        that no other exceptions are caught. This allows simple derived
        classes to override only the :meth:`convert()` method but allow the
        flexibility to do something more efficient in ``validate()`` if
        required.
        """
        try:
            self.convert(items, context)
            return True
        except ValueError:
            return False


    def convert(self, items, context):
        """Argument conversion hook.

        The operation of this method is similar to :meth:`Token.convert()`
        except that the parameter immediately following ``self`` is a list
        of matched command arguments as opposed to a single string. The
        return value should still be a list of items, which need not be
        the same length as the input list.
        """
        return items


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See :meth:`ParseItem.match()`."""

        tracer = CallTracer(trace, self, compare_items)
        if not compare_items:
            raise MatchError("insufficient args for %r" % (str(self),))
        if not self.validate(compare_items, context):
            args = " ".join(compare_items)
            args = args[:20] + "[...]" if len(args) > 25 else args
            tracer.fail([])
            raise MatchError("%r is not a valid %s" % (args, str(self)))
        if fields is not None:
            arg_list = fields.setdefault(str(self), [])
            arg_list.extend(self.convert(compare_items, context))
        return []



def parse_spec(spec, ident_factory=None):
    """Convert a string command specification into a parse tree.

    This function takes a string command specification as demonstrated in
    :ref:`cmdparser_overview`. The complete set of constructions accepted
    within a specification are shown below:

    token
      Bare tokens must match the same fixed text in the argument list.

    token:name
      Tokens are typically stored in the ``fields`` dictionary under the
      text they match, but they can take an optional name suffix, in which
      case they still match the **token** text but are stored in ``fields``
      under the **name** text.

    <ident>
      An identifer, by default :class:`AnyToken` unless ``ident_factory``
      returns something different.

    x y z
      A sequence must match all items in turn.

    ( x | y | z )
      An alternation must match exactly one of the items.

    [ x | y | z ]
      An optional alternation must match either zero or one of the items.

    x [...]
      Optional repetition means that the previous item can be repeated (it
      must always match once, the optional part is the repetition).

    If specified, the ``ident_factory`` parameter must be a function taking
    a single argument which is the string text of an identifier. Whenever
    an identifier such as ``<foo>`` is encountered, the factory function
    will be called with the name of the identifier (``"foo"`` in this case)
    as its sole argument. This function should either return an instance
    derived from :class:`ParseItem` (or some other class already derived
    from it such as :class:`Token`), or it should return ``None`` to indicate
    that the identifier isn't special. If either the function returns ``None``
    or isn't specified, identifiers will be assumed to be :class:`AnyToken`.
    """

    stack = [Sequence()]
    token = ""
    name = None
    ident = False
    skip_chars = 0

    for num, chars in ((i+1, spec[i:]) for i in xrange(len(spec))):

        if skip_chars:
            skip_chars -= 1
            continue

        # Most matching happens on only the first character.
        char = chars[0]

        # Perform correctness checks.
        if ident and (char in ":()[]|<" or char.isspace()):
            raise ParseError("invalid in identifier at char %d" % (num,))
        if char == ">" and not (ident and token):
            raise ParseError("only valid after identifier at char %d" % (num,))
        if char in "|])" and not (stack and isinstance(stack[-1], Alternation)):
            raise ParseError("invalid outside alternation at char %d" % (num,))
        if char in ")]" and char != ")]"[stack[-1].optional]:
            raise ParseError("mismatched brackets at char %d" % (num,))
        if char == ":" and not token:
            raise ParseError("empty token name at char %d" % (num,))

        # Save out any current token.
        if (char in "()[]<>|" or char.isspace()) and token and not ident:
            stack[-1].add(Token(token, name))
            token = ""
            name = None

        # Process character.
        if char == "(":
            stack.append(Alternation())
        elif char == "[":
            # String [...] is a special case meaning "optionally repeat last
            # item". We recover the last item from the latest stack item
            # and wrap it in a Repeater.
            if chars[:5] == "[...]":
                try:
                    last_item = stack[-1].pop()
                    repeater = Repeater()
                    repeater.add(last_item)
                    stack[-1].add(repeater)
                    skip_chars = 4
                except ParseError:
                    raise ParseError("no token to repeat at char %d" % (num,))
            else:
                stack.append(Alternation(optional=True))
        elif char == "<":
            ident = True
        elif char == "|":
            stack[-1].add_alternate()
        elif char in ")]":
            alt = stack.pop()
            alt.finalise()
            stack[-1].add(alt)
        elif char == ">":
            item = None
            if token.endswith("..."):
                item = AnyTokenString(token[:-3])
            elif ident_factory is not None:
                item = ident_factory(token)
            if item is None:
                item = AnyToken(token)
            stack[-1].add(item)
            ident = False
            token = ""
        elif char == ":":
            name = token
            token = ""
        elif not char.isspace():
            token += char

    if len(stack) != 1 or ident:
        raise ParseError("incomplete specification")
    if token:
        stack[-1].add(Token(token, name))
    stack[-1].finalise()
    return stack.pop()



class CmdClassDecorator(object):
    """Decorates a cmd.Cmd class and adds completion methods.

    Any method which has been decorated with cmd_do_method_decorator() will
    have a tag added which is detected by this class decorator, and the
    appropriate completion methods added. In short, any cmd.Cmd instance
    which has used the CmdMethodDecorator at least once should also have its
    class definition decorated with this decorator (unless you don't want to
    use cmdparser's automatic tab-completion support).
    """

    def __call__(self, cls):

        for method in dir(cls):
            method_attr = getattr(cls, method)
            method_dec = getattr(method_attr, "_cmdparser_decorator", None)
            if method_dec is not None:
                # Note: it's important that the method creation is delegated
                #       to a so that each completer gets its own closure.
                method_dec.add_completer(cls)

        return cls



class CmdMethodDecorator(object):
    """Decorates a do_XXX method with command parsing code.

    This decorator changes the prototype of the method from that expected by
    cmd.Cmd (i.e. a single string parameter containing the argument string
    after the initial command item) to one that takes two parameters - the
    first is the raw list of items as passed to check_match(), the second
    is the "fields" dictionary populated by check_match().

    This decorator also marks the method as requiring completion, suitable for
    the later class decorator to insert a completion method - unless the class
    decorator is also used, however, tab-completion won't be enabled.
    """

    def __init__(self, token_factory=None):

        self.token_factory = token_factory
        self.parse_tree = None
        self.command_string = None
        self.new_docstring = None


    def __call__(self, method):

        # Work out command name.
        if not method.func_name.startswith("do_"):
            raise ParseError("method name %r doesn't start 'do_'"
                             % (method.func_name,))
        self.command_string = method.func_name[3:]

        # Parse method doc string to obtain parse tree and reformatted
        # docstring.
        self.parse_docstring(method.__doc__)

        # Build replacement method.
        def wrapper(cmd_self, args):

            split_args = [self.command_string] + shlex.split(args)
            fields = {}
            check = self.parse_tree.check_match(split_args, fields=fields,
                                                context=cmd_self)
            if check is None:
                return method(cmd_self, split_args, fields)
            else:
                print "Error: %s" % (check,)
                print "Expected syntax: %s" % (self.parse_tree,)

        # Ensure wrapper has correct docstring, and also store away the parse
        # tree for the class wrapper to use for building completer methods.
        wrapper.__doc__ = "\n" + self.new_docstring + "\n"
        wrapper._cmdparser_decorator = self

        return wrapper


    def parse_docstring(self, docstring):
        """Parse method docsstring and return (parse_tree, new_docstring)."""

        # Reflow docstring to remove unnecessary whitespace.
        common_indent = None
        new_doc = []

        for doc_line in docstring.splitlines():
            # Convert whitespace-only lines to empty lines and strip trailing
            # whitespace.
            doc_line = doc_line.rstrip()
            stripped = doc_line.lstrip()
            if not stripped:
                doc_line = ""
                # Collapse consecutive blank lines.
                if new_doc and not new_doc[-1]:
                    continue
            elif new_doc:
                # Track minimum indentation of any line save the first.
                indent = len(doc_line) - len(stripped)
                if common_indent is None or indent < common_indent:
                    common_indent = indent

            # Add line to new docstring list, collapsing consecutive blanks.
            new_doc.append(doc_line)

        # Strip leading and trailing blank lines, and trim off common
        # whitespace from all but initial line.
        if common_indent is not None:
            new_doc = [new_doc[0]] + [i[common_indent:] for i in new_doc[1:]]
        while new_doc and not new_doc[0]:
            new_doc.pop(0)
        while new_doc and not new_doc[-1]:
            new_doc.pop()

        # Store updated docstring.
        self.new_docstring = "\n".join(new_doc)

        # Build spec and flag commands with no command spec as an error.
        spec = " ".join(itertools.takewhile(lambda x: x, new_doc))
        if not spec:
            raise ParseError("%s: no command spec" % (self.command_string,))

        # Convert specification into parse tree.
        try:
            tree = parse_spec(spec, ident_factory=self.token_factory)
            starts = tree.get_completions([])
            if len(starts) != 1:
                raise ParseError("command spec must have unique initial token")
            token = starts.pop()
            if token != self.command_string:
                raise ParseError("%s: command spec initial token %r must match"
                                 " command" % (self.command_string, token))
        except ParseError, e:
            raise ParseError("%s: %s" % (self.command_string, e))

        # Store parse tree.
        self.parse_tree = tree


    def add_completer(self, cls):
        """Create completion function for this command and add it to class."""

        def completer_method(cmd_self, text, line, begidx, endidx):
            items = shlex.split(line[:begidx])
            completions = self.parse_tree.get_completions(items,
                                                          context=cmd_self)
            return [i for i in completions if i.startswith(text)]

        setattr(cls, "complete_" + self.command_string, completer_method)


