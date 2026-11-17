"""T2 end to end (synthetic): 10-D action chunk -> EEF targets -> joint targets.

No dataset: the start state is FK of a known joint vector, mapped into a world frame W by an
assumed ``T_WB``. The acceptance check is that FK of the joint targets reproduces the EEF
targets the conversion produced (1 mm / 0.1 deg), chunk after chunk, in both frames.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("torch")

from twin.actions import ActionsToJoints, eef_state_to_T, identity_actions  # noqa: E402
from twin.robot import fk  # noqa: E402
from twin.transforms import geodesic_angle, make_T, rotvec_to_matrix, so3_log  # noqa: E402

Q_WORK = np.array([0.3, -1.2, 1.5, -1.9, -1.57, 0.4])
ACC_POS = 1e-3
ACC_ROT = math.radians(0.1)


def _state_from_T(T, gripper=0.03):
    return np.r_[T[:3, 3], so3_log(T[:3, :3]), gripper]


def _smooth_actions(rng, n=32):
    """Small, smooth body-frame deltas (a few mm and tenths of a degree per 1/15 s step)."""
    t = np.arange(n) / 15.0
    trans = 0.004 * np.sin(2 * math.pi * 0.4 * t[:, None] + rng.uniform(0, 6, size=3))
    rotvec = 0.01 * np.sin(2 * math.pi * 0.3 * t[:, None] + rng.uniform(0, 6, size=3))
    dR = rotvec_to_matrix(rotvec)
    rot6d = np.concatenate([dR[:, :, 0], dR[:, :, 1]], axis=-1)
    return np.concatenate([trans, rot6d, np.full((n, 1), 0.03)], axis=-1)


@pytest.mark.parametrize(
    "T_WB",
    [np.eye(4), make_T(rotvec_to_matrix([0.0, 0.0, 0.7]), np.array([0.1, -0.4, 0.75]))],
    ids=["identity", "offset"],
)
def test_five_chunks_track_targets(T_WB):
    rng = np.random.default_rng(0)
    twin = ActionsToJoints(T_WB=T_WB)
    state = _state_from_T(T_WB @ fk(Q_WORK))
    q = Q_WORK.copy()
    for _ in range(5):
        chunk = twin.step_chunk(state, _smooth_actions(rng), q)
        assert chunk.action_check.ok
        assert chunk.q.shape == (64, 6) and chunk.gripper.shape == (64,)
        assert chunk.ik.converged.all()
        T_W_targets = eef_state_to_T(chunk.eef.ctrl_states[0])
        T_W_twin = T_WB[None] @ fk(chunk.q)
        pos = np.linalg.norm(T_W_twin[:, :3, 3] - T_W_targets[:, :3, 3], axis=-1)
        rot = geodesic_angle(T_W_twin[:, :3, :3], T_W_targets[:, :3, :3])
        assert pos.max() < ACC_POS and rot.max() < ACC_ROT
        assert not chunk.ik.speed_violation.any()
        assert chunk.feasible
        state, q = chunk.next_state, chunk.q[-1]


def test_null_chunk_keeps_joints_still():
    twin = ActionsToJoints()
    state = _state_from_T(fk(Q_WORK))
    chunk = twin.step_chunk(state, identity_actions(32, gripper=0.03), Q_WORK)
    assert np.abs(chunk.q - Q_WORK[None]).max() < 1e-4  # float32 round trip of the start state


def test_unreachable_chunk_is_reported_not_raised():
    twin = ActionsToJoints()
    state = _state_from_T(fk(Q_WORK))
    a = identity_actions(32, gripper=0.03)
    a[:, 0] = 0.05  # 5 cm per step along the EEF x axis: 1.6 m in one chunk
    chunk = twin.step_chunk(state, a, Q_WORK)
    assert not chunk.ik.converged.all()
    assert not chunk.feasible
    assert np.all(np.isfinite(chunk.q))


def test_invalid_actions_stop_before_ik():
    twin = ActionsToJoints()
    a = identity_actions(32)
    a[0, 3:9] = 0.0
    with pytest.raises(ValueError, match="degenerate rot6d"):
        twin.step_chunk(_state_from_T(fk(Q_WORK)), a, Q_WORK)
