#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end tests for the decision-layer skill.

Copies the skill into a throwaway temp dir and drives it via subprocess, exactly
as an agent would, so the real policy.json / decision_log.txt are never touched.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
SCRIPTS = ["common.py", "decide.py", "learn.py", "decide_unattended.py", "review.py"]


def run(script, args, cwd, env=None):
    out = subprocess.run(
        [PY, script] + args, cwd=cwd, capture_output=True, text=True, env=env
    )
    if out.returncode != 0:
        raise AssertionError(f"{script} failed:\n{out.stderr}")
    return out.stdout


class DecisionLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dl_test_")
        for s in SCRIPTS:
            shutil.copy(os.path.join(SKILL_DIR, s), os.path.join(self.tmp, s))
        self.log = os.path.join(self.tmp, "decision_log.txt")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _decide(self, cls, cands, risk="low"):
        out = run("decide.py", [
            "--class", cls, "--scope", "content_style", "--risk", risk,
            "--candidates", cands,
        ], self.tmp)
        return json.loads(out)

    def _learn(self, cls, outcome, chosen="", scope=""):
        args = ["--class", cls, "--outcome", outcome]
        if chosen:
            args += ["--chosen", chosen]
        if scope:
            args += ["--scope", scope]
        return json.loads(run("learn.py", args, self.tmp))

    def test_gap_to_auto(self):
        # 1) unknown class -> gap + CONFIRM
        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertTrue(d["is_gap"])
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertIsNone(d["learned_choice"])

        # 2) confirm -> conf 0.5, learned_choice recorded
        L = self._learn("news_angle", "confirm", chosen="straight")
        self.assertEqual(L["confidence"], 0.5)
        self.assertEqual(L["was_gap"], True)

        # 3) decide again -> CONFIRM (still < 0.7) but now known, learned_choice shown
        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertFalse(d["is_gap"])
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertEqual(d["learned_choice"], "straight")

        # 4) confirm again -> conf 0.7 -> AUTO
        L = self._learn("news_angle", "confirm", chosen="straight")
        self.assertEqual(L["confidence"], 0.7)
        self.assertEqual(L["mode"], "AUTO")

        # 5) decide -> AUTO
        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertEqual(d["mode"], "AUTO")

    def test_override_drops_confidence(self):
        self._learn("x", "confirm", chosen="a")          # 0.3 -> 0.5
        L = self._learn("x", "override", chosen="b")     # 0.5 * 0.5 = 0.25
        self.assertAlmostEqual(L["confidence"], 0.25)
        self.assertEqual(L["learned_choice"], "b")

    def test_always_confirm_overrides_high_confidence(self):
        # inject high confidence + hard rule by editing the auto-created policy
        pol = os.path.join(self.tmp, "policy.json")
        run("decide.py", ["--class", "_seed", "--candidates", "[]"], self.tmp)  # ensures policy.json exists
        with open(pol, encoding="utf-8") as f:
            data = json.load(f)
        data["always_confirm"] = ["forceme"]
        data["confidence"]["forceme"] = 0.95
        with open(pol, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        d = self._decide("forceme", '[{"id":"a","label":"A","score":0.9}]')
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertTrue(d["risky"])

    def test_risky_scope_forces_confirm(self):
        d = self._decide("mail", '[{"id":"send","label":"Send","score":0.9}]', risk="low")
        # external_send is a risky scope even at init conf 0.3 -> CONFIRM anyway,
        # but verify risky flag triggers regardless of confidence
        d2 = self._decide("mail", '[{"id":"send","label":"Send","score":0.9}]', risk="high")
        self.assertTrue(d2["risky"])
        self.assertEqual(d2["mode"], "CONFIRM")

    def test_unattended_writes_relative_log(self):
        out = run("decide_unattended.py", [
            "--class", "yt_sel", "--scope", "content_style", "--risk", "low",
            "--candidates", '[{"id":"recent_top","label":"Recent top","score":0.7}]',
            "--log", self.log,
        ], self.tmp)
        j = json.loads(out)
        self.assertEqual(j["chosen_id"], "recent_top")
        self.assertTrue(os.path.exists(self.log))
        with open(self.log, encoding="utf-8") as f:
            line = f.read().strip()
        self.assertIn("class=yt_sel", line)
        self.assertIn("gap=Y", line)  # first time -> gap

        # review should list it as pending
        rev = run("review.py", ["--log", self.log], self.tmp)
        self.assertIn("yt_sel", rev)

        # apply confirm -> next decide would be AUTO (conf 0.5, still < 0.7 -> still pending once)
        run("review.py", ["--apply", "--class", "yt_sel", "--outcome", "confirm",
                          "--chosen", "recent_top", "--log", self.log], self.tmp)
        # after one confirm conf=0.5, still CONFIRM; verify learned
        d = self._decide("yt_sel", '[{"id":"recent_top","label":"Recent top","score":0.7}]')
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertEqual(d["learned_choice"], "recent_top")


if __name__ == "__main__":
    unittest.main(verbosity=2)
