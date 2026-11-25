"""Interactive MuJoCo viewer for the twin (WP 1.1). Needs a display: run it on the Windows laptop.

    python scripts/twin_view.py                      # the UR5 arm at the home pose (--model ur5)
    python scripts/twin_view.py --replay q.json      # play a joint trajectory q(t), shape (T, 6)
    python scripts/twin_view.py --demo-chunk         # synthetic action chunks -> ActionsToJoints

Trajectory files: ``.json`` as ``{"q": [[q0..q5], ...], "fps": 30}`` or ``.npz`` with arrays
``q`` and optionally ``fps`` (default 30 Hz, the Ctrl-World condition rate). ``.npz`` is
gitignored, so keep such files out of the repo. The viewer ships with the ``mujoco`` package; it
is imported only when a window is opened, so ``--help`` and the helpers work without a display.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_FPS = 30.0
# A typical UR "elbow up, wrist down" working pose, away from singularities (as in the IK tests).
HOME_Q = np.array([0.3, -1.2, 1.5, -1.9, -1.57, 0.4])
DEMO_CHUNK_STEPS = 32  # policy actions per chunk at 15 Hz (production H)
DEMO_STEP = 0.004  # m per policy step; one chunk traces a closed circle of radius ~2 cm


def load_trajectory(path: Path) -> tuple[np.ndarray, float]:
    """Joint trajectory ``q (T, 6)`` [rad] and its rate [Hz] from a ``.json`` or ``.npz`` file."""
    path = Path(path)
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        q, fps = raw["q"], raw.get("fps", DEFAULT_FPS)
    elif path.suffix == ".npz":
        with np.load(path) as raw:
            q = raw["q"]
            fps = raw["fps"] if "fps" in raw.files else DEFAULT_FPS
    else:
        raise ValueError(f"unknown trajectory suffix {path.suffix!r}; use .json or .npz")
    q = np.asarray(q, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != 6 or len(q) == 0:
        raise ValueError(f"q must have shape (T, 6) with T >= 1, got {q.shape}")
    if not np.isfinite(q).all():
        raise ValueError("q contains NaN or Inf")
    fps = float(fps)
    if not fps > 0.0:
        raise ValueError(f"fps must be positive, got {fps}")
    return q, fps


def demo_chunk_trajectory(n_chunks: int = 3) -> tuple[np.ndarray, float]:
    """Joint path for ``n_chunks`` smooth synthetic action chunks, starting at ``HOME_Q``.

    Each chunk translates the EEF around a closed circle in its own x-y plane (body frame, no
    rotation), through the same conversion and IK as the twin (``ActionsToJoints`` in a
    kinematics-only ``TwinSession``). Returns ``q (1 + 64 n_chunks, 6)`` at 30 Hz.
    """
    from twin.actions import ActionsToJoints, identity_actions
    from twin.robot import fk
    from twin.session import TwinSession
    from twin.transforms import so3_log

    k = np.arange(DEMO_CHUNK_STEPS)
    actions = identity_actions(DEMO_CHUNK_STEPS)
    phase = 2.0 * np.pi * k / DEMO_CHUNK_STEPS
    actions[:, 0] = DEMO_STEP * np.cos(phase)
    actions[:, 1] = DEMO_STEP * np.sin(phase)

    a2j = ActionsToJoints()
    session = TwinSession(a2j)
    T0 = fk(HOME_Q)
    session.reset(np.r_[T0[:3, 3], so3_log(T0[:3, :3]), 0.0], HOME_Q)
    path = [HOME_Q[None]]
    for _ in range(n_chunks):
        result = session.step_chunk(actions)
        if not result.joints.feasible:
            raise RuntimeError(f"demo chunk not feasible: {session.reachability_summary()}")
        path.append(result.joints.q)
    return np.concatenate(path), a2j.adapter.ctrl_fps


def play(q: np.ndarray, fps: float, *, loop: bool) -> None:
    """Show ``q`` in the passive MuJoCo viewer at ``fps``; holds the last frame until closed."""
    import mujoco
    import mujoco.viewer

    from twin.robot import load_ur5_model

    model = load_ur5_model()
    data = mujoco.MjData(model)
    dt = 1.0 / fps
    with mujoco.viewer.launch_passive(model, data) as viewer:
        i = 0
        while viewer.is_running():
            t_start = time.perf_counter()
            with viewer.lock():
                data.qpos[:] = q[i]
                mujoco.mj_forward(model, data)
            viewer.sync()
            if i + 1 < len(q):
                i += 1
            elif loop:
                i = 0
            time.sleep(max(0.0, dt - (time.perf_counter() - t_start)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", choices=["ur5"], default="ur5", help="model to show")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--replay", type=Path, help="joint trajectory file (.json or .npz)")
    source.add_argument(
        "--demo-chunk", action="store_true", help="play synthetic action chunks through T2"
    )
    parser.add_argument("--chunks", type=int, default=3, help="chunks for --demo-chunk")
    parser.add_argument("--loop", action="store_true", help="restart the trajectory at the end")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.replay is not None:
        q, fps = load_trajectory(args.replay)
    elif args.demo_chunk:
        q, fps = demo_chunk_trajectory(args.chunks)
    else:
        q, fps = HOME_Q[None], DEFAULT_FPS
    play(q, fps, loop=args.loop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
