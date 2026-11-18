import unittest
from modern.backend.importing import parser_settings


class ParserOptionsTests(unittest.TestCase):
    def test_gtk_options(self):
        self.assertEqual(parser_settings({}), (1, -1))
        for comment in (0, 1):
            for rounding in (-1, 0, 1, 2, 1.5, 2.5):
                self.assertEqual(parser_settings(dict(comment_position=comment, rounding=rounding)), (comment, rounding))

    def test_invalid_options(self):
        for params in ({'comment_position': True}, {'comment_position': 2}, {'rounding': '2'}, {'rounding': 3}):
            with self.assertRaises(ValueError):
                parser_settings(params)
