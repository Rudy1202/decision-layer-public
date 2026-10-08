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
SCRIPTS = ["common.py", "decide.py", "learn.py", "decide_unattended.py", "review.py", "correct.py"]


def run(script, args, cwd, env=None):
    out = subprocess.run(
        [PY, script] + args, cwd=cwd, capture_output=True, text=True, env=env
    )
    if out.returncode != 0:
        raise AssertionError(f"{script} failed:\nSTDOUT:{out.stdout}\nSTDERR:{out.stderr}")
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

    def _learn(self, cls, outcome, chosen="", scope="", rationale=""):
        args = ["--class", cls, "--outcome", outcome]
        if chosen:
            args += ["--chosen", chosen]
        if scope:
            args += ["--scope", scope]
        if rationale:
            args += ["--rationale", rationale]
        return json.loads(run("learn.py", args, self.tmp))

    def _seed_policy(self, **overrides):
        pol = os.path.join(self.tmp, "policy.json")
        run("decide.py", ["--class", "_seed", "--candidates", "[]"], self.tmp)  # ensures policy.json exists
        with open(pol, encoding="utf-8") as f:
            data = json.load(f)
        data.update(overrides)
        with open(pol, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def test_gap_to_auto(self):
        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertTrue(d["is_gap"])
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertIsNone(d["learned_choice"])

        L = self._learn("news_angle", "confirm", chosen="straight")
        self.assertEqual(L["confidence"], 0.5)
        self.assertEqual(L["was_gap"], True)

        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertFalse(d["is_gap"])
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertEqual(d["learned_choice"], "straight")

        L = self._learn("news_angle", "confirm", chosen="straight")
        self.assertEqual(L["confidence"], 0.7)
        self.assertEqual(L["mode"], "AUTO")

        d = self._decide("news_angle", '[{"id":"straight","label":"S","score":0.8}]')
        self.assertEqual(d["mode"], "AUTO")

    def test_override_drops_confidence(self):
        self._learn("x", "confirm", chosen="a")          # 0.3 -> 0.5
        L = self._learn("x", "override", chosen="b")     # 0.5 * 0.5 = 0.25
        self.assertAlmostEqual(L["confidence"], 0.25)
        self.assertEqual(L["learned_choice"], "b")

    def test_always_confirm_overrides_high_confidence(self):
        self._seed_policy(always_confirm=["forceme"], confidence={"forceme": 0.95})
        d = self._decide("forceme", '[{"id":"a","label":"A","score":0.9}]')
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertTrue(d["risky"])

    def test_auto_scope_goes_auto_immediately(self):
        # pre-authorized SAFE class -> AUTO even at init confidence 0.3
        self._seed_policy(auto_scopes=["fast_cls"])
        d = self._decide("fast_cls", '[{"id":"go","label":"Go","score":0.9}]')
        self.assertEqual(d["mode"], "AUTO")
        self.assertTrue(d["auto_scope"])

        # but risky scope can never be auto_scopes
        self._seed_policy(auto_scopes=["fast_cls"], risky_scopes=["content_style"])
        d2 = self._decide("fast_cls", '[{"id":"go","label":"Go","score":0.9}]', risk="low")
        self.assertEqual(d2["mode"], "CONFIRM")  # content_style now risky -> gated

    def test_risky_scope_forces_confirm(self):
        d = self._decide("mail", '[{"id":"send","label":"Send","score":0.9}]', risk="high")
        self.assertTrue(d["risky"])
        self.assertEqual(d["mode"], "CONFIRM")

    def test_correct_py_persona_driven_plan(self):
        out = run("correct.py", [
            "--error", "ImportError: cannot import name 'X'",
            "--class", "fix_import",
        ], self.tmp)
        self.assertIn("backup", out)
        self.assertIn("plan", out)
        self.assertIn("verify", out)
        j = json.loads(run("correct.py", [
            "--error", "boom", "--json",
        ], self.tmp))
        self.assertEqual(j["style"]["backup_before_change"], True)
        self.assertIn("steps", j)
        self.assertTrue(any(s["action"] == "backup" for s in j["steps"]))

    def test_unattended_writes_jsonl_log(self):
        out = run("decide_unattended.py", [
            "--class", "yt_sel", "--scope", "content_style", "--risk", "low",
            "--candidates", '[{"id":"recent_top","label":"Recent top","score":0.7}]',
            "--log", self.log,
        ], self.tmp)
        j = json.loads(out)
        self.assertEqual(j["chosen_id"], "recent_top")
        self.assertTrue(os.path.exists(self.log))
        with open(self.log, encoding="utf-8") as f:
            first = json.loads(f.readline().strip())
        self.assertEqual(first["class"], "yt_sel")
        self.assertEqual(first["gap"], "Y")  # first time -> gap

        rev = run("review.py", ["--log", self.log], self.tmp)
        self.assertIn("yt_sel", rev)

        # JSON output of review
        revj = json.loads(run("review.py", ["--log", self.log, "--json"], self.tmp))
        self.assertEqual(revj["pending"][0]["class"], "yt_sel")

        run("review.py", ["--apply", "--class", "yt_sel", "--outcome", "confirm",
                          "--chosen", "recent_top", "--log", self.log], self.tmp)
        d = self._decide("yt_sel", '[{"id":"recent_top","label":"Recent top","score":0.7}]')
        self.assertEqual(d["mode"], "CONFIRM")
        self.assertEqual(d["learned_choice"], "recent_top")

    def test_legacy_text_log_lines_skipped(self):
        # old pipe-delimited lines must not crash the JSONL parser
        with open(self.log, "w", encoding="utf-8") as f:
            f.write("2026-01-01 00:00 | class=old | mode=CONFIRM | conf=0.3 | chosen=x | gap=Y | pending_review\n")
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-02-01 00:00:00", "class": "newc",
                                "mode": "CONFIRM", "conf": 0.3, "chosen": "y",
                                "is_gap": True, "auto_scope": False, "gap": "Y"}) + "\n")
        revj = json.loads(run("review.py", ["--log", self.log, "--json"], self.tmp))
        classes = [r["class"] for r in revj["pending"]]
        self.assertIn("newc", classes)
        self.assertNotIn("old", classes)  # legacy text line skipped

    def test_decay_lowers_stale_confidence(self):
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        self._seed_policy(confidence={"stale": 0.9}, last_seen={"stale": old}, decay_days=30)
        d = self._decide("stale", '[{"id":"a","label":"A","score":0.9}]')
        # 0.9 * 0.7 = 0.63 -> below 0.7 -> CONFIRM again (freshness works)
        self.assertLess(d["confidence"], 0.7)
        self.assertEqual(d["mode"], "CONFIRM")


if __name__ == "__main__":
    unittest.main(verbosity=2)
