"""Public CI logs must not show min/median/max for fewer than 5 records."""
import unittest

import diagnose_minutes_feasibility as feas
import validate_player_minutes as vpm


class SmallCellSuppression(unittest.TestCase):
    def test_small_cells_hide_values(self):
        for mod in (feas, vpm):
            for n in (1, 2, 4):
                out = mod.spread([6.43] * n)
                self.assertEqual(out, {"n": n, "suppressed": True}, mod.__name__)

    def test_large_cells_keep_values(self):
        for mod in (feas, vpm):
            out = mod.spread([1, 2, 3, 4, 5])
            self.assertEqual((out["min"], out["median"], out["max"], out["n"]), (1, 3, 5, 5))
            self.assertNotIn("suppressed", out)

    def test_empty_is_none(self):
        for mod in (feas, vpm):
            self.assertIsNone(mod.spread([]))


if __name__ == "__main__":
    unittest.main()
