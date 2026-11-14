"""T1 (numpy part): UR5 DH forward kinematics parity with the repo FK.

The reference table `tests/fixtures/twin_fk_reference_ur5.json` was generated once with the
repo function `ur5_joint_actions_to_eef_states` (eef_pose_adapter.py) by
`scripts/make_twin_fk_reference.py`. Only test_reference_table_matches_live_repo_function
needs torch; every other test is numpy only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from twin.robot import JOINT_LIMITS, TCP_OFFSET, UR5_DH, fk
from twin.transforms import geodesic_angle, make_T, rotvec_to_matrix

FIXTURE = Path(__file__).parent / "fixtures" / "twin_fk_reference_ur5.json"
POS_TOL = 1e-5  # m, acceptance criterion of T1
ROT_TOL = 1e-5  # rad, acceptance criterion of T1


@pytest.fixture(scope="module")
def table():
    with FIXTURE.open() as f:
        data = json.load(f)
    return {
        "meta": data["meta"],
        "q": np.asarray(data["q"], dtype=np.float64),
        "pos": np.asarray(data["pos"], dtype=np.float64),
        "rotvec": np.asarray(data["rotvec"], dtype=np.float64),
    }


# --- transform helpers -------------------------------------------------------------------


def test_rotvec_to_matrix_known_cases():
    np.testing.assert_allclose(rotvec_to_matrix(np.zeros(3)), np.eye(3), atol=1e-15)
    rz90 = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    np.testing.assert_allclose(rotvec_to_matrix([0.0, 0.0, math.pi / 2]), rz90, atol=1e-15)
    rx180 = np.diag([1.0, -1.0, -1.0])
    np.testing.assert_allclose(rotvec_to_matrix([math.pi, 0.0, 0.0]), rx180, atol=1e-15)
    # Tiny angle: first-order term must survive (no division blow-up, no truncation to I).
    tiny = rotvec_to_matrix([0.0, 0.0, 1e-10])
    assert tiny[1, 0] == pytest.approx(1e-10, rel=1e-9)
    # Batched input.
    batch = rotvec_to_matrix(np.array([[0.0, 0.0, math.pi / 2], [math.pi, 0.0, 0.0]]))
    np.testing.assert_allclose(batch, np.stack([rz90, rx180]), atol=1e-15)


def test_geodesic_angle_known_cases():
    a = rotvec_to_matrix([0.1, -0.2, 0.3])
    assert geodesic_angle(a, a) < 1e-15
    for angle in (1e-9, 1e-3, 0.5, 2.0, math.pi - 1e-6):
        b = a @ rotvec_to_matrix([0.0, angle, 0.0])
        assert geodesic_angle(a, b) == pytest.approx(angle, rel=1e-9)
        assert geodesic_angle(b, a) == pytest.approx(geodesic_angle(a, b), rel=1e-12)


def test_make_T():
    R = rotvec_to_matrix([0.0, 0.0, 0.3])
    T = make_T(R, [1.0, 2.0, 3.0])
    assert T.shape == (4, 4)
    np.testing.assert_array_equal(T[:3, :3], R)
    np.testing.assert_array_equal(T[:3, 3], [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(T[3], [0.0, 0.0, 0.0, 1.0])


# --- forward kinematics -------------------------------------------------------------------


def test_constants_match_repo_function_source():
    # Values read from ur5_joint_actions_to_eef_states (eef_pose_adapter.py:461).
    assert UR5_DH == (
        (0.0, 0.089159, math.pi / 2),
        (-0.425, 0.0, 0.0),
        (-0.39225, 0.0, 0.0),
        (0.0, 0.10915, math.pi / 2),
        (0.0, 0.09465, -math.pi / 2),
        (0.0, 0.0823, 0.0),
    )
    assert TCP_OFFSET == (0.0, 0.0, 0.18)


def test_zero_configuration_matches_hand_computation():
    # At q = 0: x stays along x0; a2 + a3 = -0.81725. z is d1 - d5. The flange sits at
    # y = -(d4 + d6) = -0.19145, and the TCP adds 0.18 along z6 = -y0.
    T = fk(np.zeros(6))
    np.testing.assert_allclose(T[:3, 3], [-0.81725, -0.37145, 0.089159 - 0.09465], atol=1e-12)
    R_expected = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
    np.testing.assert_allclose(T[:3, :3], R_expected, atol=1e-12)
    np.testing.assert_array_equal(T[3], [0.0, 0.0, 0.0, 1.0])


def test_fk_matches_repo_reference_table(table):
    T = fk(table["q"])
    pos_err = np.linalg.norm(T[:, :3, 3] - table["pos"], axis=-1)
    rot_err = geodesic_angle(T[:, :3, :3], rotvec_to_matrix(table["rotvec"]))
    print(
        f"\nFK parity over {len(pos_err)} joint vectors: "
        f"pos max {pos_err.max():.3e} m, rot max {rot_err.max():.3e} rad"
    )
    assert pos_err.max() < POS_TOL, f"pos max {pos_err.max():.3e} at row {pos_err.argmax()}"
    assert rot_err.max() < ROT_TOL, f"rot max {rot_err.max():.3e} at row {rot_err.argmax()}"


def test_joint_wrapping_gives_same_pose():
    rng = np.random.default_rng(1)
    q = rng.uniform(-math.pi, math.pi, size=(50, 6))
    T = fk(q)
    for j in range(6):
        shift = np.zeros(6)
        shift[j] = 2 * math.pi
        for sign in (1.0, -1.0):
            T_shift = fk(q + sign * shift)
            np.testing.assert_allclose(T_shift[:, :3, 3], T[:, :3, 3], atol=1e-12)
            assert geodesic_angle(T_shift[:, :3, :3], T[:, :3, :3]).max() < 1e-12
    # The guide's case: a joint at 2*pi - eps and at -eps.
    eps = 1e-3
    for j in range(6):
        qa = np.zeros(6)
        qb = np.zeros(6)
        qa[j] = 2 * math.pi - eps
        qb[j] = -eps
        Ta, Tb = fk(qa), fk(qb)
        np.testing.assert_allclose(Ta[:3, 3], Tb[:3, 3], atol=1e-12)
        assert geodesic_angle(Ta[:3, :3], Tb[:3, :3]) < 1e-12


def test_fk_batch_shapes_and_so3_validity():
    rng = np.random.default_rng(2)
    q = rng.uniform(-2 * math.pi, 2 * math.pi, size=(3, 4, 6))
    T = fk(q)
    assert T.shape == (3, 4, 4, 4)
    np.testing.assert_allclose(fk(q.reshape(12, 6)), T.reshape(12, 4, 4), atol=0)
    np.testing.assert_allclose(fk(q[1, 2]), T[1, 2], atol=0)
    assert fk(q[0, 0]).shape == (4, 4)
    R = T[..., :3, :3]
    eye = np.broadcast_to(np.eye(3), R.shape)
    np.testing.assert_allclose(np.swapaxes(R, -1, -2) @ R, eye, atol=1e-12)
    np.testing.assert_allclose(np.linalg.det(R), 1.0, atol=1e-12)
    np.testing.assert_array_equal(T[..., 3, :], np.broadcast_to([0.0, 0.0, 0.0, 1.0], T.shape[:-2] + (4,)))


def test_fk_rejects_wrong_joint_count():
    with pytest.raises(ValueError):
        fk(np.zeros(5))


# --- reference table ----------------------------------------------------------------------


def test_reference_table_sanity(table):
    meta = table["meta"]
    assert table["q"].shape == (1000, 6)
    assert table["pos"].shape == (1000, 3)
    assert table["rotvec"].shape == (1000, 3)
    assert meta["dtype"] == "float64"
    assert meta["n"] == 1000
    lo, hi = JOINT_LIMITS[:, 0], JOINT_LIMITS[:, 1]
    assert np.all(table["q"] >= lo) and np.all(table["q"] <= hi)
    # Repo quaternion clamp (eps=1e-8 on 4 q_k^2) alters q_k only when |q_k| < 5e-5.
    assert meta["min_abs_quat_component"] >= 5e-5


def test_reference_table_matches_live_repo_function(table):
    torch = pytest.importorskip("torch")
    from twin.repo_import import load_eef_pose_adapter

    adapter = load_eef_pose_adapter()
    q = table["q"]
    joint_actions = np.concatenate([q, np.zeros((len(q), 1))], axis=1)[None]
    out = adapter.ur5_joint_actions_to_eef_states(
        torch.from_numpy(joint_actions).to(torch.float64)
    )[0].numpy()
    np.testing.assert_allclose(out[:, :3], table["pos"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out[:, 3:6], table["rotvec"], rtol=0, atol=1e-12)
