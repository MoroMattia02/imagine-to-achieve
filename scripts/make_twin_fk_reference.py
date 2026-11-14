"""Generate the T1 FK reference table from the repo's own UR5 FK (run once).

    python scripts/make_twin_fk_reference.py

Samples 1000 joint vectors uniformly inside the UR5 joint limits (seed 0), runs
``ur5_joint_actions_to_eef_states`` from eef_pose_adapter.py (loaded by file path) in float64,
and writes tests/fixtures/twin_fk_reference_ur5.json (repo output stored as-is: position and
axis-angle). float64 matters: in float32 the repo function is off by up to ~6e-5 rad, which is
above the 1e-5 rad T1 tolerance.

The repo's matrix-to-quaternion step clamps each sqrt argument at 1e-8, which costs up to
~1e-4 rad when a quaternion component is below 5e-5. The script refuses to write a table
whose smallest component is below 5e-5, so the table never contains that artefact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from twin.repo_import import EEF_POSE_ADAPTER_PATH, load_eef_pose_adapter  # noqa: E402
from twin.robot import JOINT_LIMITS, TCP_OFFSET, fk  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "tests" / "fixtures" / "twin_fk_reference_ur5.json"
# The repo clamps sqrt(4 q_k^2) arguments at 1e-8, i.e. it alters q_k only when |q_k| < 5e-5.
MIN_QUAT_COMPONENT = 5e-5


def min_abs_quat_component(R: np.ndarray) -> float:
    """Smallest |q_k| of the unit quaternions of rotation matrices ``(N, 3, 3)``."""
    tr = np.trace(R, axis1=-2, axis2=-1)
    args = np.stack(
        [1.0 + tr, 1.0 + 2 * R[:, 0, 0] - tr, 1.0 + 2 * R[:, 1, 1] - tr, 1.0 + 2 * R[:, 2, 2] - tr],
        axis=-1,
    )
    return float((0.5 * np.sqrt(np.clip(args, 0.0, None))).min())


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    import torch

    rng = np.random.default_rng(args.seed)
    q = rng.uniform(JOINT_LIMITS[:, 0], JOINT_LIMITS[:, 1], size=(args.n, 6))

    adapter = load_eef_pose_adapter()
    joint_actions = np.concatenate([q, np.zeros((args.n, 1))], axis=1)[None]  # [1, N, 7]
    with torch.no_grad():
        out = adapter.ur5_joint_actions_to_eef_states(
            torch.from_numpy(joint_actions).to(torch.float64)
        )[0].numpy()
    pos, rotvec = out[:, :3], out[:, 3:6]

    min_q = min_abs_quat_component(fk(q)[:, :3, :3])
    if min_q < MIN_QUAT_COMPONENT:
        raise SystemExit(
            f"smallest quaternion component {min_q:.2e} < {MIN_QUAT_COMPONENT:.0e}: the repo's "
            "eps clamp would distort that row; choose another seed"
        )

    meta = {
        "description": "UR5 FK reference: repo ur5_joint_actions_to_eef_states on random joints",
        "source_function": "eef_pose_adapter.ur5_joint_actions_to_eef_states",
        "source_file": EEF_POSE_ADAPTER_PATH.relative_to(REPO_ROOT).as_posix(),
        "source_sha256": hashlib.sha256(EEF_POSE_ADAPTER_PATH.read_bytes()).hexdigest(),
        "git_commit": git_commit(),
        "generator": "scripts/make_twin_fk_reference.py",
        "torch_version": torch.__version__,
        "dtype": "float64",
        "n": args.n,
        "seed": args.seed,
        "sampling": "numpy default_rng(seed).uniform(lo, hi, size=(n, 6))",
        "joint_limits": JOINT_LIMITS.tolist(),
        "tcp_xyz": list(TCP_OFFSET),
        "tcp_rotvec": [0.0, 0.0, 0.0],
        "rotation_format": "axis-angle (repo output, principal branch, no branch_reference)",
        "min_abs_quat_component": min_q,
    }

    def rows(a: np.ndarray) -> str:
        # One row per line; json float repr round-trips float64 exactly.
        return "[\n" + ",\n".join("    " + json.dumps(r) for r in a.tolist()) + "\n  ]"

    text = (
        "{\n"
        f'  "meta": {json.dumps(meta, indent=4)},\n'
        f'  "q": {rows(q)},\n'
        f'  "pos": {rows(pos)},\n'
        f'  "rotvec": {rows(rotvec)}\n'
        "}\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")

    check = json.loads(args.out.read_text(encoding="utf-8"))
    assert np.array_equal(np.asarray(check["q"]), q), "JSON round-trip of q is not exact"
    assert np.array_equal(np.asarray(check["pos"]), pos), "JSON round-trip of pos is not exact"
    print(
        f"wrote {args.out.relative_to(REPO_ROOT).as_posix()}: n={args.n}, seed={args.seed}, "
        f"min |quat component|={min_q:.3e}, {args.out.stat().st_size / 1024:.0f} KiB"
    )


if __name__ == "__main__":
    main()
