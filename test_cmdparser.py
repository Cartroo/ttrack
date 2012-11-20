#!/usr/bin/python

import cmdparser
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
            def get_values(self):
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
            def get_values(self):
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
        self.assertEqual(tree.check_match(("one", "two")), "")
        self.assertEqual(tree.check_match(("two", "three")), "two")
        self.assertEqual(tree.check_match(("one", "three")), "three")
        self.assertEqual(tree.check_match(("two", "one", "three")), "two")
        self.assertEqual(tree.check_match(("one", "two", "threeX")), "threeX")
        self.assertEqual(tree.check_match(("one", "two", "thre")), "thre")
        self.assertEqual(tree.check_match([]), "")


    def test_match_alternation(self):
        spec = "(one | two | three)"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one",)), None)
        self.assertEqual(tree.check_match(("two",)), None)
        self.assertEqual(tree.check_match(("three",)), None)
        self.assertEqual(tree.check_match(("one", "two")), "two")
        self.assertEqual(tree.check_match(("one", "one")), "one")
        self.assertEqual(tree.check_match(("one", "two", "three")), "two")
        self.assertEqual(tree.check_match([]), "")


    def test_match_optional(self):
        spec = "one [two] three"
        tree = cmdparser.parse_spec(spec)
        self.assertEqual(tree.check_match(("one", "three")), None)
        self.assertEqual(tree.check_match(("one", "two", "three")), None)
        self.assertEqual(tree.check_match(("one", "twoX", "three")), "twoX")
        self.assertEqual(tree.check_match(("one", "two")), "")
        self.assertEqual(tree.check_match(("one", "three", "two")), "two")
        self.assertEqual(tree.check_match(("two", "one", "three")), "two")
        self.assertEqual(tree.check_match(("two", "three")), "two")
        self.assertEqual(tree.check_match(("one",)), "")
        self.assertEqual(tree.check_match(("two",)), "two")
        self.assertEqual(tree.check_match(("three",)), "three")
        self.assertEqual(tree.check_match([]), "")


    def test_match_identifier(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self):
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
        self.assertEqual(fields, {"one": "one", "two": "foo", "three": "x",
                                  "four": "a b"})
        fields = {}
        self.assertEqual(tree.check_match(("one", "bar", "z", "baz"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": "one", "two": "bar", "three": "z",
                                  "four": "baz"})
        self.assertEqual(tree.check_match(("one", "foo", "x")), "")
        self.assertEqual(tree.check_match(("one", "foo", "w", "a")), "w")
        self.assertEqual(tree.check_match(("one", "x", "a")), "a")


    def test_match_full(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self):
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
        self.assertEqual(fields, {"one": "one", "two": "two", "three": "three",
                                  "six": "six", "eight": "foo bar"})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "seven", "foo"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": "one", "four": "four",
                                  "seven": "seven", "eight": "foo"})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "foo"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": "one", "four": "four", "eight": "foo"})
        fields = {}
        self.assertEqual(tree.check_match(("one", "four", "x", "foo", "bar"),
                                          fields=fields), None)
        self.assertEqual(fields, {"one": "one", "four": "four", "five": "x",
                                  "eight": "foo bar"})

        self.assertEqual(tree.check_match(("one", "two", "foo")), "foo")
        self.assertEqual(tree.check_match(("one", "four", "x")), "")
        self.assertEqual(tree.check_match(("one", "four", "six")), "")



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
            def get_values(self):
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


    def test_complete_full(self):
        class XYZIdent(cmdparser.Token):
            def get_values(self):
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

