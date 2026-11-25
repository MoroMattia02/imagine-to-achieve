"""WP 1.1: scripts/twin_view.py, the interactive viewer (run by hand on the Windows laptop).

The viewer window itself cannot be tested here (no display). These tests check what can be:
``--help`` works headless, trajectory files load and are validated, the demo chunk goes through
ActionsToJoints to a feasible, smooth joint path, and the options reach the player.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from twin.ik import UR5_MAX_JOINT_SPEED
from twin.robot import fk

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "twin_view.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("twin_view", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tv():
    return _load_script()


def test_help_runs_without_a_display():
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, env=env, timeout=60
    )
    assert out.returncode == 0, out.stderr
    for flag in ("--model", "--replay", "--demo-chunk"):
        assert flag in out.stdout


def test_load_trajectory_json_and_npz(tv, tmp_path):
    q = np.random.default_rng(0).uniform(-1.0, 1.0, size=(5, 6))
    (tmp_path / "t.json").write_text(json.dumps({"q": q.tolist(), "fps": 15.0}))
    np.savez(tmp_path / "t.npz", q=q)
    q_json, fps_json = tv.load_trajectory(tmp_path / "t.json")
    q_npz, fps_npz = tv.load_trajectory(tmp_path / "t.npz")
    np.testing.assert_array_equal(q_json, q)
    np.testing.assert_array_equal(q_npz, q)
    assert fps_json == 15.0 and fps_npz == tv.DEFAULT_FPS


@pytest.mark.parametrize(
    "q", [np.zeros((4, 5)), np.zeros(6), np.zeros((0, 6)), np.full((3, 6), np.nan)]
)
def test_load_trajectory_rejects_bad_arrays(tv, tmp_path, q):
    np.savez(tmp_path / "bad.npz", q=q)
    with pytest.raises(ValueError):
        tv.load_trajectory(tmp_path / "bad.npz")


def test_load_trajectory_rejects_unknown_suffix(tv, tmp_path):
    (tmp_path / "t.csv").write_text("0,0,0,0,0,0\n")
    with pytest.raises(ValueError, match="suffix"):
        tv.load_trajectory(tmp_path / "t.csv")


def test_demo_chunk_is_feasible_smooth_and_closed(tv):
    pytest.importorskip("torch")  # the repo action conversion needs torch
    n_chunks = 2
    q, fps = tv.demo_chunk_trajectory(n_chunks)
    assert fps == 30.0
    assert q.shape == (1 + 64 * n_chunks, 6) and np.isfinite(q).all()
    speed = np.abs(np.diff(q, axis=0)) * fps
    assert (speed <= UR5_MAX_JOINT_SPEED).all()
    T0, T1 = fk(q[0]), fk(q[-1])
    assert np.linalg.norm(T1[:3, 3] - T0[:3, 3]) < 1e-4  # each chunk is a closed loop
    assert np.ptp(fk(q)[:, :3, 3], axis=0).max() > 0.02  # and it does move (cm scale)


def test_options_reach_the_player(tv, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tv, "play", lambda q, fps, *, loop: calls.append((q, fps, loop)))
    q = np.random.default_rng(1).uniform(-1.0, 1.0, size=(7, 6))
    np.savez(tmp_path / "t.npz", q=q, fps=10.0)

    assert tv.main(["--replay", str(tmp_path / "t.npz"), "--loop"]) == 0
    np.testing.assert_array_equal(calls[-1][0], q)
    assert calls[-1][1:] == (10.0, True)

    assert tv.main(["--model", "ur5"]) == 0  # static arm at the home pose
    np.testing.assert_array_equal(calls[-1][0], tv.HOME_Q[None])
    assert calls[-1][2] is False

    with pytest.raises(SystemExit):
        tv.main(["--replay", "x.npz", "--demo-chunk"])  # mutually exclusive
