#!/usr/bin/python

from cmdparser import cmdparser
import unittest


class TestParser(unittest.TestCase):

    def test_parse_sequence(self):
        spec = "one two three"
        tree = cmdparser.parse_spec(spec)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 3)
        for item, spec_item in zip(tree.items, ("one", "two", "three")):
            self.assertIsInstance(item, cmdparser.Token)
            self.assertEqual(item.name, spec_item)


    def test_parse_alternation(self):
        spec = "(one | two | three)"
        tree = cmdparser.parse_spec(spec)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 1)
        alt = tree.items[0]
        self.assertIsInstance(alt, cmdparser.Alternation)
        self.assertEqual(alt.optional, False)
        self.assertEqual(len(alt.options), 3)
        for item, spec_item in zip(alt.options, ("one", "two", "three")):
            self.assertIsInstance(item, cmdparser.Sequence)
            self.assertEqual(len(item.items), 1)
            self.assertIsInstance(item.items[0], cmdparser.Token)
            self.assertEqual(item.items[0].name, spec_item)
            self.assertEqual(item.items[0].token, spec_item)


    def test_parse_named_token_alternation(self):
        spec = "( one:foo | two:foo | three:foo )"
        tree = cmdparser.parse_spec(spec)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 1)
        alt = tree.items[0]
        self.assertIsInstance(alt, cmdparser.Alternation)
        self.assertEqual(alt.optional, False)
        self.assertEqual(len(alt.options), 3)
        for item, spec_item in zip(alt.options, ("one", "two", "three")):
            self.assertIsInstance(item, cmdparser.Sequence)
            self.assertEqual(len(item.items), 1)
            self.assertIsInstance(item.items[0], cmdparser.Token)
            self.assertEqual(item.items[0].name, "foo")
            self.assertEqual(item.items[0].token, spec_item)


    def test_parse_repeat_token(self):
        spec = "one two [...]"
        tree = cmdparser.parse_spec(spec)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 2)
        self.assertIsInstance(tree.items[0], cmdparser.Token)
        self.assertEqual(tree.items[0].name, "one")
        self.assertIsInstance(tree.items[1], cmdparser.Repeater)
        self.assertIsInstance(tree.items[1].item, cmdparser.Token)
        self.assertEqual(tree.items[1].item.name, "two")


    def test_parse_optional(self):
        spec = "one [two] three"
        tree = cmdparser.parse_spec(spec)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 3)
        self.assertIsInstance(tree.items[0], cmdparser.Token)
        self.assertEqual(tree.items[0].name, "one")
        self.assertIsInstance(tree.items[1], cmdparser.Alternation)
        self.assertEqual(tree.items[1].optional, True)
        self.assertEqual(len(tree.items[1].options), 1)
        self.assertIsInstance(tree.items[1].options[0], cmdparser.Sequence)
        self.assertEqual(len(tree.items[1].options[0].items), 1)
        self.assertIsInstance(tree.items[1].options[0].items[0], cmdparser.Token)
        self.assertEqual(tree.items[1].options[0].items[0].name, "two")
        self.assertIsInstance(tree.items[2], cmdparser.Token)
        self.assertEqual(tree.items[2].name, "three")


    def test_parse_identifier(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "three":
                return XYZIdent(ident)
            return None
        spec = "one <two> <three> <four...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 4)
        self.assertIsInstance(tree.items[0], cmdparser.Token)
        self.assertEqual(tree.items[0].name, "one")
        self.assertIsInstance(tree.items[1], cmdparser.AnyToken)
        self.assertEqual(tree.items[1].name, "two")
        self.assertIsInstance(tree.items[2], XYZIdent)
        self.assertEqual(tree.items[2].name, "three")
        self.assertIsInstance(tree.items[3], cmdparser.AnyTokenString)
        self.assertEqual(tree.items[3].name, "four")


    def test_parse_full(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "five":
                return XYZIdent(ident)
            return None
        spec = "one ( two three | four [<five>] ) [ six | seven ] <eight...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        self.assertIsInstance(tree, cmdparser.Sequence)
        self.assertEqual(len(tree.items), 4)
        self.assertIsInstance(tree.items[0], cmdparser.Token)
        self.assertIsInstance(tree.items[1], cmdparser.Alternation)
        self.assertEqual(tree.items[1].optional, False)
        self.assertEqual(len(tree.items[1].options), 2)
        self.assertIsInstance(tree.items[1].options[0], cmdparser.Sequence)
        opt = tree.items[1].options[0]
        self.assertEqual(len(opt.items), 2)
        self.assertIsInstance(opt.items[0], cmdparser.Token)
        self.assertIsInstance(opt.items[1], cmdparser.Token)
        opt = tree.items[1].options[1]
        self.assertEqual(len(opt.items), 2)
        self.assertIsInstance(opt.items[0], cmdparser.Token)
        self.assertIsInstance(opt.items[1], cmdparser.Alternation)
        self.assertEqual(opt.items[1].optional, True)
        self.assertEqual(len(opt.items[1].options), 1)
        self.assertIsInstance(opt.items[1].options[0], cmdparser.Sequence)
        self.assertEqual(len(opt.items[1].options[0].items), 1)
        self.assertIsInstance(opt.items[1].options[0].items[0], XYZIdent)
        self.assertIsInstance(tree.items[2], cmdparser.Alternation)
        self.assertEqual(tree.items[2].optional, True)
        self.assertEqual(len(tree.items[2].options), 2)
        for i in (0, 1):
            self.assertIsInstance(tree.items[2].options[i], cmdparser.Sequence)
            self.assertEqual(len(tree.items[2].options[i].items), 1)
            self.assertIsInstance(tree.items[2].options[i].items[0],
                                  cmdparser.Token)
        self.assertIsInstance(tree.items[3], cmdparser.AnyTokenString)



class TestMatching(unittest.TestCase):

    def test_match_sequence(self):
        spec = "one two three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one", "two", "three")), None)
        self.assertRegexpMatches(tree.check_match(("one", "two")),
                                 "insufficient args")
        self.assertRegexpMatches(tree.check_match(("two", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("two", "one", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "two", "threeX")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "two", "thre")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match([]), "insufficient args")


    def test_match_alternation(self):
        spec = "(one | two | three)"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one",)), None)
        self.assertEqual(tree.check_match(("two",)), None)
        self.assertEqual(tree.check_match(("three",)), None)
        self.assertRegexpMatches(tree.check_match(("one", "two")),
                         "command invalid somewhere in")
        self.assertRegexpMatches(tree.check_match(("one", "one")),
                         "command invalid somewhere in")
        self.assertRegexpMatches(tree.check_match(("one", "two", "three")),
                         "command invalid somewhere in")
        self.assertRegexpMatches(tree.check_match([]), "insufficient args")


    def test_match_repeat_token(self):
        spec = "one two [...] three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one", "two", "three")), None)
        fields = {}
        self.assertEqual(tree.check_match(("one", "two", "two", "three"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "two": ["two", "two"],
                         "three": ["three"]})
        self.assertEqual(tree.check_match(("one", "two", "two", "two",
                                           "three")), None)
        self.assertRegexpMatches(tree.check_match(("one",)),
                                 "insufficient args")
        self.assertRegexpMatches(tree.check_match(("one", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "two", "three", "two")),
                                 "command invalid somewhere in")


    def test_match_repeat_sequence(self):
        spec = "(one two) [...] three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one", "two", "three")), None)
        self.assertEqual(tree.check_match(("one", "two", "one", "two",
                                           "three")), None)
        self.assertRegexpMatches(tree.check_match(("one", "two", "one", "three")),
                         "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "two", "two")),
                         "doesn't match")


    def test_match_optional(self):
        spec = "one [two] three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one", "three")), None)
        self.assertEqual(tree.check_match(("one", "two", "three")), None)
        self.assertRegexpMatches(tree.check_match(("one", "twoX", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "two")),
                                 "insufficient args")
        self.assertRegexpMatches(tree.check_match(("one", "three", "two")),
                                 "command invalid somewhere in")
        self.assertRegexpMatches(tree.check_match(("two", "one", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("two", "three")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one",)),
                                 "insufficient args")
        self.assertRegexpMatches(tree.check_match(("two",)),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("three",)),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match([]), "insufficient args")


    def test_match_identifier(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "three":
                return XYZIdent(ident)
            return None
        spec = "one <two> <three> <four...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        fields = {}
        self.assertEqual(tree.check_match(("one", "foo", "x", "a", "b"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "<two>": ["foo"],
                                  "<three>": ["x"], "<four...>": ["a", "b"]})
        fields = {}
        self.assertEqual(tree.check_match(("one", "bar", "z", "baz"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "<two>": ["bar"],
                                  "<three>": ["z"], "<four...>": ["baz"]})
        self.assertRegexpMatches(tree.check_match(("one", "foo", "x")),
                                 "insufficient args")
        self.assertRegexpMatches(tree.check_match(("one", "foo", "w", "a")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "x", "a")),
                                 "doesn't match")


    def test_match_subtree(self):
        class SubtreeIdent(cmdparser.Subtree):
            def convert(self, args, fields, context):
                return [args, fields]
        def ident_factory(ident):
            if ident == "sub":
                return SubtreeIdent(ident, "x (y|z) <foo>")
            return None
        spec = "one <sub> <ident>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        fields = {}
        self.assertEqual(tree.check_match(("one", "x", "y", "z", "bar"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"],
                                  "<sub>": [("x", "y", "z"),
                                            {"x": ["x"], "y": ["y"],
                                             "<foo>": ["z"]}],
                                  "<ident>": ["bar"]})
        fields = {}
        self.assertEqual(tree.check_match(("one", "x", "z", "z", "bar"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"],
                                  "<sub>": [("x", "z", "z"),
                                            {"x": ["x"], "z": ["z"],
                                             "<foo>": ["z"]}],
                                  "<ident>": ["bar"]})
        self.assertRegexpMatches(tree.check_match(("one", "x", "x", "z", "a")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "y", "y", "z", "a")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "x", "y", "aaa")),
                                 "insufficient args")


    def test_match_full(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "five":
                return XYZIdent(ident)
            return None
        spec = "one ( two three | four [<five>] ) [ six | seven ] <eight...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        fields = {}
        self.assertEqual(tree.check_match(("one", "two", "three", "six",
                                           "foo", "bar"), fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "two": ["two"],
                                  "three": ["three"], "six": ["six"],
                                  "<eight...>": ["foo", "bar"]})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "seven", "foo"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "four": ["four"],
                                  "seven": ["seven"], "<eight...>": ["foo"]})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "foo"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "four": ["four"],
                                  "<eight...>": ["foo"]})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "x", "foo", "bar"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": ["one"], "four": ["four"],
                                  "<five>": ["x"], "<eight...>": ["foo", "bar"]})

        self.assertRegexpMatches(tree.check_match(("one", "two", "foo")),
                                 "doesn't match")
        self.assertRegexpMatches(tree.check_match(("one", "four", "x")),
                         "insufficient args")
        self.assertRegexpMatches(tree.check_match(("one", "four", "six")),
                         "insufficient args")



class TestCompletions(unittest.TestCase):

    def test_complete_sequence(self):
        spec = "one two three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)),
                         set(("two",)))
        self.assertEqual(tree.get_completions(("one", "two")),
                         set(("three",)))
        self.assertEqual(tree.get_completions(("one", "two", "three")),
                         set())


    def test_complete_alternation(self):
        spec = "(one | two | three)"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.get_completions(()),
                         set(("one", "two", "three")))
        self.assertEqual(tree.get_completions(("one",)),
                         set())
        self.assertEqual(tree.get_completions(("two",)),
                         set())
        self.assertEqual(tree.get_completions(("three",)),
                         set())


    def test_complete_repeat_token(self):
        spec = "one two [...]"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)), set(("two",)))
        self.assertEqual(tree.get_completions(("one", "two")), set(("two",)))
        self.assertEqual(tree.get_completions(("one", "two", "two")),
                         set(("two",)))


    def test_complete_optional(self):
        spec = "one [two] three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)),
                         set(("two", "three")))
        self.assertEqual(tree.get_completions(("one", "two")),
                         set(("three",)))
        self.assertEqual(tree.get_completions(("one", "three")),
                         set())
        self.assertEqual(tree.get_completions(("one", "two", "three")),
                         set())


    def test_complete_identifier(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "three":
                return XYZIdent(ident)
            return None
        spec = "one <two> <three> <four...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)),
                         set())
        self.assertEqual(tree.get_completions(("one", "foo")),
                         set(("x", "y", "z")))
        self.assertEqual(tree.get_completions(("one", "foo", "x")),
                         set())
        self.assertEqual(tree.get_completions(("one", "foo", "x", "foo")),
                         set())


    def test_complete_subtree(self):
        class SubtreeIdent(cmdparser.Subtree):
            def convert(self, args, fields, context):
                return [args, fields]
        def ident_factory(ident):
            if ident == "sub":
                return SubtreeIdent(ident, "x (y|z) <foo>")
            return None
        spec = "one <sub> <ident>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)), set(("x",)))
        self.assertEqual(tree.get_completions(("one", "x")), set(("y", "z")))
        self.assertEqual(tree.get_completions(("one", "x", "y")), set())
        self.assertEqual(tree.get_completions(("one", "x", "z")), set())
        self.assertEqual(tree.get_completions(("one", "x", "y", "z")), set())


    def test_complete_full(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self, context):
                return ["x", "y", "z"]
        def ident_factory(ident):
            if ident == "five":
                return XYZIdent(ident)
            return None
        spec = "one ( two three | four [<five>] ) [ six | seven ] <eight...>"
        tree = cmdparser.parse_spec(spec, ident_factory=ident_factory)
        self.assertEqual(tree.get_completions(()), set(("one",)))
        self.assertEqual(tree.get_completions(("one",)),
                         set(("two", "four")))
        self.assertEqual(tree.get_completions(("one", "two")),
                         set(("three",)))
        self.assertEqual(tree.get_completions(("one", "two", "three")),
                         set(("six", "seven")))
        self.assertEqual(tree.get_completions(("one", "four")),
                         set(("x", "y", "z", "six", "seven")))
        self.assertEqual(tree.get_completions(("one", "four", "y")),
                         set(("six", "seven")))
        self.assertEqual(tree.get_completions(("one", "four", "six")), set())



if __name__ == "__main__":
    unittest.main()

