import csv, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compute_multirater_agreement as m
import build_multirater_packets as b

WIKI = [[0,0,0,0,14],[0,2,6,4,2],[0,0,3,5,6],[0,3,9,2,0],[2,2,8,1,1],
        [7,7,0,0,0],[3,2,6,3,0],[2,5,3,2,2],[6,5,2,1,0],[0,2,2,3,7]]

class T(unittest.TestCase):
    def test_fleiss_known(self):  # Wikipedia worked example: kappa = 0.210
        self.assertAlmostEqual(m.fleiss_kappa_counts(WIKI), 0.2099, places=3)
    def test_fleiss_perfect(self):
        self.assertAlmostEqual(m.fleiss_kappa_counts([[3,0],[0,3],[3,0],[0,3]]), 1.0)
    def test_alpha_hand(self):  # hand-computed 0.125
        self.assertAlmostEqual(m.krippendorff_alpha([[0,0],[1,1],[0,1],[1,0]]), 0.125)
    def test_alpha_ordinal_binary_equals_nominal(self):
        u = [[0,0,1],[1,1,1],[0,1,0],[1,0,0]]
        self.assertAlmostEqual(m.krippendorff_alpha(u,"ordinal",[0,1]), m.krippendorff_alpha(u,"nominal"))
    def test_alpha_ordinal_penalizes_far(self):
        near = m.krippendorff_alpha([[0,1],[1,1],[2,2],[3,3],[0,0]],"ordinal",[0,1,2,3])
        far = m.krippendorff_alpha([[0,3],[1,1],[2,2],[3,3],[0,0]],"ordinal",[0,1,2,3])
        self.assertGreater(near, far)
    def test_alpha_missing(self):
        self.assertAlmostEqual(m.krippendorff_alpha([[0,0,None],[1,1,1],[None,0,0]]), 1.0)
    def test_cohen(self):
        self.assertAlmostEqual(m.cohen_kappa([1,1,0,0],[1,1,0,0]), 1.0)
        self.assertAlmostEqual(m.cohen_kappa([1,0,1,0],[0,1,0,1]), -1.0)
    def test_cp(self):  # 0 events of 33 at 97.5%: 1-0.025^(1/33)
        self.assertAlmostEqual(m.cp_upper(0,33), 1-0.025**(1/33), places=6)
        self.assertAlmostEqual(m.cp_lower(33,33), 0.025**(1/33), places=6)
    def test_majority_tie_unsupported_first(self):
        self.assertEqual(m.majority([1,0]), 0); self.assertEqual(m.majority([1,1,0]), 1)
    def test_shuffle_gap_and_seed(self):
        cq = [f"Q{i%33}" for i in range(188)]
        o1 = b.constrained_shuffle(cq, 1); o2 = b.constrained_shuffle(cq, 1); o3 = b.constrained_shuffle(cq, 2)
        self.assertEqual(o1, o2); self.assertNotEqual(o1, o3)
        self.assertGreaterEqual(b.check_gap([cq[i] for i in o1]), 20)
        self.assertEqual(sorted(o1), list(range(188)))
    def test_rater_seeds_differ(self):
        self.assertNotEqual(b.rater_seed("x","R1"), b.rater_seed("x","R2"))

if __name__ == "__main__":
    unittest.main()
