"""A simple command parsing library.

This module allows textual command specifications to be "compiled" into parse
tree structures which can then be used to parse command strings entered by a
user. It also provides some decorators to use with the Python builtin cmd module
to use these command parsers to ease some of the effort checking command syntax
and extracting the relevant values.

The structures which make up the parse tree are all classes derived from a base
ParseItem class. This base class provides two methods which are typically
called on the root of a parse tree:

check_match()
  This method is used to check a complete command string as entered by a user
  against the parse tree to check for a match. Calling code is responsible for
  splitting the command string into a list of strings first, so application can
  select their own quoting conventions. This list is then passed to
  check_match() which returns None, to indicate the command matches, or a string
  containing an error message if the match fails. This method also takes a set
  of other arguments for extracting items from the command string, see the
  documentation for the method for more details.

get_completions()
  This method is passed a list of command-line items as check_match(), but in
  this case the list is typically incomplete - the function returns a list of
  strings indicating the valid tokens which could follow the command specified,
  if any. This is used to implement tab-completion.

Parse trees can be built by manually constructing class instances, but the
intended method is to use the parse_spec() method to convert a string command
specification into the corresponding parse tree. Command specifications consist
of a sequence of specifiers, each of which can be a fixed string, an identifier
in angle brackets, an alternation in round brackes or an optional alternation in
square brackets. An example specification is shown below:

    one ( two | three [ four | five ] ) <six> [...] <seven...>

This specification demonstrates most of the accepted syntax for command
specifications. It specifies that commands must consist of the fixed item
"one" followed by either "two" or "three", where "three" may also optionally
be followed by either "four" or "five". After this, the identifer <six> occurs -
identifiers are explained below. After this the "[...]" indicates that the
previous item may occur one or more times, so matching continues against <six>
until a command-line item fails to match. After this point the ellipsis at the
end of the <seven...> identifier indicates that this token will consume all
remaining command-line items.

This is all relatively straightforward except for the identifiers - these may
represent arbitrarily complex sequences of items, from the basic Token class
which matches a single fixed command-line item, to Subtree instances, which
match against an entire nested parse tree.

To specify the class of each identifier, a function is passed via the
ident_factory keyword argument of the parse_spec() method. This function should
take a single argument which is the name of the identifier (with the angle
backets removed), and should return either an instance of a class derived from
ParseItem, or None - if the function returns None then parse_spec() will assume
the identifier is of the AnyToken class, which matches any single command-line
item.

Taking the example above, if the ident_factory function returned an instance of
the IntegerToken class when passed the string "six" as its argument then the
<six> identifier in the command would only match strings which were valid
integers. Note that in this particular example, if the ident_factory returned
None (or if no factory were specified) then the <seven...> identifier would
never match anything because the remaining command-line would always be consumed
by repetitions of <six>. This illustrates that the matching is purely greedy on
a left-to-right basis, so it's quite possible (though not useful) to invent a
command specification which is impossible to match (in this case because the
AnyTokenString class always requires at least one argument).

The instances returned by ident_factory can be of classes defined within this
module or application-specified versions, typically derived from classes defined
herein. It's generally intended that the following classes act as base classes
for application-specified classes:

Token
  Override the get_values() method to specify a fixed list of strings which
  could match - this list isn't cached so may be entirely dynamic, but note that
  unlike the AnyToken class the list of acceptable items is known in advance.
  Deriving from this class allows tab-completion of the values as well.

AnyToken
  Similar to Token, but in this case any string will be accepted so
  tab-completion isn't possible. Derived instances typically override one or
  both of the convert() and validate() methods to provide their specific
  behaviour.

AnyTokenString
  Matches all remaining command-line items, and is otherwise similar to the
  AnyToken class.

For both AnyToken and AnyTokenString, there is a validate() method which is
called just after matching to indicate whether the matched value is acceptable.
Where the list of acceptable items is known in advance it's typically better to
use Token as the base class to enable tab-completion, but in some cases it's
only feasible to check whether a specific value matches (e.g. any string within
a specified range of lengths is to be accepted). If this method returns False,
matching will continue with any other possibilities as usual. Also see the
implementation of the IntegerToken class for a simple illustration of how this
method may be used.

Many of the classes also support a convert() method, which is used to convert
the command-line items into a more useful form for the application - for
example, as well as only matching strings which are a sequence of digits, the
IntegerToken class also converts the string into an int value.

These converted values go into the "fields" dictionary, which is an optional
parameter to the check_match() method. If non-None, this argument must be a
dict-like instance which is used to store matched values indexed by identifier
name. The key is the form of the specification item as used in parse_spec()
and the value is a list of the matched items from the command instance being
matched. This is perhaps best illustrated with an example using the following
command specification:

    set <name> ( age <number> | nicknames <nick> [...] )

For this example, assume that the ident_factory function returns an IntegerToken
instance for the <number> identifier and returns None in all other cases,
leaving <name> and <nick> as the default AnyToken class.

If the following call were made on the compiled parse tree:

    cmd_fields = {}
    parse_tree.check_match(("set", "Andrew", "age", "98"), fields=cmd_fields)

... then the cmd_fields dict would appear as follows after the call:

    { "set": ["set"], "<name>": ["Andrew"], "age": ["age"], "<number>": [98] }

By comparison, the same call but using the following command items:

    ("set", "Andrew", "nicknames", "Andy", "Ace", "Trouble")

... would result in a dictionary populated as follows:

    { "set": ["set"], "<name>": ["Andrew"], "nicknames": ["nicknames"],
      "<nick>": ["Andy", "Ace", "Trouble"] }

Finally, the CmdMethodDecorator and CmdClassDecorator classes deserve a brief
mention. As their name suggests they're intended for use as a method and class
decorator respectively, specifically for use with the builtin Python cmd module.
Decorating the do_XXX() methods and the entire cmd.Cmd class instance itself
with them will use the cmdparser facilities to parse entered commands, only
passing valid commands on to the method itself and supporting the dict-based
forms of command-line item extraction outlined above. The command specification
itself is automatically extracted from the command's docstring, which is also
used by cmd.Cmd as the online help - this is intended to keep the documentation
and functional code in close harmony.

See the docstrings of these decorators for more information.
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

        The default does nothing, derived classes can raise ParseError if
        the object isn't valid as it stands for any reason.
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

        Should attempt to match item's specification against command-line
        supplied in compare_items and either return compare_items with
        consumed items removed, or raise MatchError if the command-line
        doesn't match.

        If the item has consumed a command-line argument, it should store
        it against the item's name in the fields dict if that parameter is
        not None. If the completions field is not None and compare_items
        is empty (i.e. just after the matched string) then the item should
        store a list of valid tokens in the completions set just prior
        to raising MatchError - this only applies to items which accept
        a list of valid values, items which match any string should leave
        the set alone (it's used for tab-completion).

        The trace argument, if supplied, should be a list. As each class's
        match() function is entered or left, a string representing it
        is appended to the list.

        The context argument is reflected down through all calls to match()
        methods so application-provided tokens can use it.

        The default is to raise a MatchError, derived classes should override.
        """
        raise MatchError("invalid use of ParseItem (programming error)")


    def check_match(self, items, fields=None, trace=None, context=None):
        """Return None if the specified command-line is valid and complete.

        If the command-line doesn't match, an appropriate error explaining the
        lack of match is returned.

        Calling code should typically use this instead of calling match()
        directly. Derived classes shouldn't typically override this method.
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
        """Return set of valid tokens to follow partial command-line in items.

        Calling code should typically use this instead of calling match()
        directly. Derived classes shouldn't typically override this method.
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
        """See ParseItem.finalise()."""

        if not self.items:
            raise ParseError("empty sequence")
        for item in self.items:
            item.finalise()


    def add(self, child):
        """See ParseItem.add()."""

        assert isinstance(child, ParseItem)
        self.items.append(child)


    def pop(self):
        """See ParseItem.pop()."""

        try:
            return self.items.pop()
        except IndexError:
            raise ParseError("no child item to pop")


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See ParseItem.match()."""

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
        """See ParseItem.finalise()."""
        if self.item is None:
            raise ParseError("empty repeater")


    def add(self, child):
        """See ParseItem.add()."""

        assert isinstance(child, ParseItem)
        if isinstance(child, Repeater) or isinstance(child, AnyTokenString):
            raise ParseError("repeater cannot accept a repeating child")
        if self.item is not None:
            raise ParseError("repeater may only have a single child")
        self.item = child


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):

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
    strings such as "yesterday at 3:34" or "25 minutes ago", but wish to
    store the result in the fields dictionary as a single datetime instance.

    By default, command completion within the subtree will be enabled - if the
    tree should be treated more like a token then it may be useful to disable
    completion (i.e. always return no completions), and this can be done by
    setting the suppress_completion parameter to the constructor to True.
    """

    def __init__(self, name, spec, ident_factory=None,
                 suppress_completion=False):
        self.name = name
        self.suppress_completion = suppress_completion
        # Allow any parsing exceptions to be passed out of constructor.
        self.parse_tree = parse_spec(spec, ident_factory=ident_factory)


    def __str__(self):
        return '<' + str(self.name) + '>'


    def convert(self, args, fields, context):
        """Convert matched items into field value(s).

        This method is called when the subtree matches and is passed the
        subset of the argument list which matched as well as the fields
        array that was filled in. It should return a list of values which
        will be appended to those for the field name.

        The base class instance simply appends the list of matched arguments
        to the field values list.
        """
        return args


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):

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

    Alternation instances can also be marked optional by setting the "optional"
    parameter to True in the constructor - this menas that if none of the
    options match, they'll return success without consuming any items instead of
    raising MatchError.

    Note that matching is greedy with no back-tracking, so if an optional item
    matches the command line argument(s) will always be consumed even if this
    leads to a MatchError later in the string which wouldn't have occurred had
    the optional item chosen to match nothing instead.
    """

    def __init__(self, optional=False):
        self.optional = optional
        self.options = []
        self.add_alternate()


    def __str__(self):
        seps = "[]" if self.optional else "()"
        return seps[0] + "|".join(str(i) for i in self.options) + seps[1]


    def finalise(self):
        """See ParseItem.finalise()."""

        if not self.options:
            raise ParseError("empty alternation")
        for option in self.options:
            option.finalise()


    def add(self, child):
        """See ParseItem.add()."""

        assert isinstance(child, ParseItem)
        self.options[-1].add(child)


    def pop(self):
        """See ParseItem.pop()."""

        return self.options[-1].pop()


    def add_alternate(self):
        """See ParseItem.add_alternate()."""

        self.options.append(Sequence())


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See ParseItem.match()."""

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

    This class also doubles as the base class for any application-specific items
    which should match one or more fixed strings (the list can change over time,
    but at any point in time there's a deterministic list of valid options).
    Such derived classes should simply override get_values().
    """

    def __init__(self, name, token=None):
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
            return "<" + self.name + ">"


    def get_values(self, context):
        """Return the current list of valid tokens.

        Derived classes should override this method to return the full list of
        every valid token. This method is invoked on demand with no caching
        (though there is nothing to stop derived instances doing their own
        caching should it be required).
        """
        return [self.token]


    def convert(self, arg, context):
        """Argument conversion hook.

        A matched argument is filtered through this method before being placed
        in the "fields" dictionary passed on the match() method. This allows
        derived classes to, for example, convert the type of the argument to
        something that's more useful to the code using the value.

        The first argument (after self) is the matched token string, the second
        is the context passed to match(). The return value should be a list to
        be added to the list of values for the field.
        """
        return [arg]


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See ParseItem.match()."""

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
        self.name = name


    def __str__(self):
        return "<" + self.name + ">"


    def validate(self, arg, context):
        """Validation hook.

        Derived classes can use this to indicate whether a given parameter
        value is accpetable. Return True if yes, False otherwise. The base
        class version returns True unless convert() raises ValueError, in
        which case False (note that no other exceptions are caught).

        For cases where a small set of values is acceptable it may be more
        appropriate to derive from Token and override get_values(), which has
        the advantage of also allowing tab-completion.
        """
        try:
            self.convert(arg, context)
            return True
        except ValueError:
            return False


    def convert(self, arg, context):
        """Argument conversion hook.

        A matched argument is filtered through this method before being placed
        in the "fields" dictionary passed on the match() method. This allows
        derived classes to, for example, convert the type of the argument to
        something that's more useful to the code using the value.

        The first argument (after self) is the matched token string. The second
        is the context passed to match(). The return value should be a list to
        be added to the list of values for the field.
        """
        return [arg]


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
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
    """As AnyToken, but only accepts integers and converts to int values."""

    def __init__(self, name, min_value=None, max_value=None):
        AnyToken.__init__(self, name)
        self.min_value = min_value
        self.max_value = max_value


    def convert(self, arg, context):
        value = int(arg)
        if (self.min_value is not None and value < self.min_value or
            self.max_value is not None and value > self.max_value):
            raise ValueError("integer value %d outside range %d-%d" %
                             (value, self.min_value, self.max_value))
        return [value]




class AnyTokenString(ParseItem):
    """Matches the remainder of the command string."""

    def __init__(self, name):
        self.name = name


    def __str__(self):
        return "<" + self.name + "...>"


    def validate(self, items, context):
        """Validation hook.

        Derived classes can use this to indicate whether a given parameter
        list is accpetable. Return True if yes, False otherwise. The base
        class version returns True unless convert() raises ValueError, in
        which case False (note that no other exceptions are caught).
        """
        try:
            self.convert(items, context)
            return True
        except ValueError:
            return False


    def convert(self, items, context):
        """Argument conversion hook.

        A matched argument list is filtered through this method before being
        placed in the "fields" dictionary passed on the match() method. This
        allows derived classes to, for example, convert the types of arguments
        or concatenate them.

        The first argument (after self) is the list of matched arguments. The
        second is the context argument passed to match(). The return value
        should be a list which is added to the list of values for the field -
        the list need not be the same length as the input.
        """
        return items


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
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


