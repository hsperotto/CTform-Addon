import unittest

from freecad.CTformFreeCADInterface.identifiers import readable_id


class ReadableIdTests(unittest.TestCase):
    def test_normalizes_human_names(self):
        self.assertEqual(readable_id("UpperPunch"), "upper-punch")
        self.assertEqual(readable_id("AISI H13 / Tool Steel"), "aisi-h13-tool-steel")

    def test_adds_suffix_for_collisions(self):
        existing = ["h13-tool-steel", "h13-tool-steel-2"]
        self.assertEqual(readable_id("H13 Tool Steel", existing), "h13-tool-steel-3")

    def test_uses_fallback_for_empty_or_non_ascii_names(self):
        self.assertEqual(readable_id("---", fallback="tool"), "tool")


if __name__ == "__main__":
    unittest.main()