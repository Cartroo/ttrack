"""cmdparser - A simple command parsing library."""


import itertools
import shlex


class ParseError(Exception):
    """Error parsing command specification."""
    pass



class MatchError(Exception):
    """Raised internally if a command fails to match the specification."""
    pass



class CallTracer(object):

    def __init__(self, trace, name):
        self.trace = trace
        self.name = name
        if trace is not None:
            trace.append(">>> " + name)


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
        raise MatchError(compare_items)


    def check_match(self, items, fields=None, trace=None, context=None):
        """Return None if the specified command-line is valid and complete.

        If the command-line doesn't match, the first non-matching item is
        returned, or the empty string if the command was incomplete.

        Calling code should typically use this instead of calling match()
        directly. Derived classes shouldn't typically override this method.
        """
        try:
            unparsed = self.match(items, fields=fields, trace=trace,
                                  context=context)
            if not unparsed:
                return None
        except MatchError, e:
            unparsed = e.args[0]
        if unparsed:
            return unparsed[0]
        else:
            return ""


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

        tracer = CallTracer(trace, "Sequence")
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

        tracer = CallTracer(trace, "Repeater")
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

        tracer = CallTracer(trace, "Alternation")
        remaining = compare_items
        for option in self.options:
            try:
                return option.match(compare_items, fields=fields,
                                    completions=completions,
                                    trace=trace, context=context)
            except MatchError, e:
                if len(e.args[0]) < len(remaining):
                    remaining = e.args[0]
        if self.optional:
            return compare_items
        else:
            tracer.fail(remaining)
            raise MatchError(remaining)



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
        return self.token


    def get_values(self, context):
        """Return the current list of valid tokens.

        Derived classes should override this method to return the full list of
        every valid token. This method is invoked on demand with no caching
        (though there is nothing to stop derived instances doing their own
        caching should it be required).
        """
        return [self.token]


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        """See ParseItem.match()."""

        tracer = CallTracer(trace, "Token(%s)" % (self.name,))
        if not compare_items:
            if completions is not None:
                completions.update(self.get_values(context))
            tracer.fail([])
            raise MatchError([])
        for value in self.get_values(context):
            if compare_items and compare_items[0] == value:
                if fields is not None:
                    fields.setdefault(self.name, []).append(value)
                return compare_items[1:]
        tracer.fail(compare_items)
        raise MatchError(compare_items)



class AnyToken(ParseItem):
    """Matches any single item."""

    def __init__(self, name):
        self.name = name


    def __str__(self):
        return "<" + self.name + ">"


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        tracer = CallTracer(trace, "AnyToken(%s)" % (self.name,))
        if not compare_items:
            tracer.fail([])
            raise MatchError([])
        if fields is not None:
            fields.setdefault(self.name, []).append(compare_items[0])
        return compare_items[1:]



class AnyTokenString(ParseItem):
    """Matches the remainder of the command string."""

    def __init__(self, name):
        self.name = name


    def __str__(self):
        return "<" + self.name + "...>"


    def match(self, compare_items, fields=None, completions=None, trace=None,
              context=None):
        tracer = CallTracer(trace, "AnyTokenString(%s)" % (self.name,))
        if not compare_items:
            tracer.fail([])
            raise MatchError([])
        if fields is not None:
            fields.setdefault(self.name, []).extend(compare_items)
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
    appropriate completion methods added.
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

    Also marks the method as requiring completion, suitable for the later
    class decorator to insert a completion method.
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
                if check:
                    print "Invalid command (unrecognised from %r)" % (check,)
                else:
                    print "Incomplete command"
                print "Expected syntax: %s" % (self.parse_tree,)

        # Ensure wrapper has correct docstring, and also store away the parse
        # tree for the class wrapper to use for building completer methods.
        wrapper.__doc__ = self.new_docstring
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


