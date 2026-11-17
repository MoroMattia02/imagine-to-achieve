"""T2 (synthetic part): UR5 Jacobian, analytic IK, damped-least-squares IK and path tracking.

Acceptance (twin_implementation_plan.md, T2, synthetic): FK(IK(x)) = x within 1 mm and 0.1 deg
for reachable poses, and no joint jumps along smooth paths. Numpy only, except the Jacobian
cross-check against MuJoCo's mj_jacSite (skipped without mujoco).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from twin.ik import (
    IKConfig,
    branch_of,
    ik_analytic,
    ik_dls,
    initial_configuration,
    jacobian,
    nearest_equivalent,
    track_path,
)
from twin.robot import JOINT_LIMITS, fk
from twin.transforms import geodesic_angle, make_T, rotvec_to_matrix, so3_log

ACC_POS = 1e-3  # m, T2 acceptance
ACC_ROT = math.radians(0.1)  # rad, T2 acceptance

# A typical UR "elbow up, wrist down" working configuration, away from all singularities.
Q_WORK = np.array([0.3, -1.2, 1.5, -1.9, -1.57, 0.4])


def _wrap(x):
    return (np.asarray(x) + math.pi) % (2.0 * math.pi) - math.pi


def _pose_errors(T_a, T_b):
    pos = np.linalg.norm(T_a[..., :3, 3] - T_b[..., :3, 3], axis=-1)
    rot = geodesic_angle(T_a[..., :3, :3], T_b[..., :3, :3])
    return pos, rot


def _regular_samples(n, seed):
    """Random joint vectors in (-pi, pi] away from the three UR5 singularities."""
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        q = rng.uniform(-math.pi, math.pi, size=6)
        T = fk(q)
        p5 = T[:3, 3] - (0.18 + 0.0823) * T[:3, 2]  # wrist centre (frame 5 origin)
        shoulder = math.hypot(p5[0], p5[1]) - 0.10915  # 0 when the wrist centre is on the base axis
        if abs(math.sin(q[4])) > 0.05 and abs(math.sin(q[2])) > 0.05 and shoulder > 0.02:
            out.append(q)
    return np.array(out)


# --- so3_log ---------------------------------------------------------------------------------


def test_so3_log_inverts_rodrigues_including_near_pi():
    rng = np.random.default_rng(1)
    axes = rng.normal(size=(200, 3))
    axes /= np.linalg.norm(axes, axis=1, keepdims=True)
    for angle in (0.0, 1e-9, 1e-4, 0.3, 2.0, math.pi - 1e-5, math.pi - 1e-9):
        r = axes * angle
        r_back = so3_log(rotvec_to_matrix(r))
        np.testing.assert_allclose(
            geodesic_angle(rotvec_to_matrix(r_back), rotvec_to_matrix(r)), 0.0, atol=1e-8
        )
        assert np.all(np.linalg.norm(r_back, axis=1) <= math.pi + 1e-12)


# --- Jacobian --------------------------------------------------------------------------------


def test_jacobian_matches_finite_differences():
    rng = np.random.default_rng(2)
    h = 1e-6
    for q in rng.uniform(-math.pi, math.pi, size=(50, 6)):
        J = jacobian(q)
        T0 = fk(q)
        for j in range(6):
            dq = np.zeros(6)
            dq[j] = h
            Tp, Tm = fk(q + dq), fk(q - dq)
            v = (Tp[:3, 3] - Tm[:3, 3]) / (2 * h)
            # Spatial angular velocity: log(R(q+h) R(q)^T) / h.
            w = (so3_log(Tp[:3, :3] @ T0[:3, :3].T) - so3_log(Tm[:3, :3] @ T0[:3, :3].T)) / (2 * h)
            np.testing.assert_allclose(J[:3, j], v, atol=1e-7)
            np.testing.assert_allclose(J[3:, j], w, atol=1e-7)


def test_jacobian_matches_mujoco_jac_site():
    mujoco = pytest.importorskip("mujoco")
    from twin.robot import load_ur5_model

    model = load_ur5_model()
    data = mujoco.MjData(model)
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tcp")
    rng = np.random.default_rng(3)
    for q in rng.uniform(-math.pi, math.pi, size=(50, 6)):
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacSite(model, data, jacp, jacr, site)
        np.testing.assert_allclose(jacobian(q), np.vstack([jacp, jacr]), atol=1e-12)


# --- analytic IK -----------------------------------------------------------------------------


def test_analytic_ik_solutions_reproduce_pose_and_contain_the_original():
    qs = _regular_samples(500, seed=4)
    for q in qs:
        T = fk(q)
        sols = ik_analytic(T)
        assert 1 <= len(sols) <= 8
        pos, rot = _pose_errors(fk(sols), T[None])
        assert pos.max() < 1e-9 and rot.max() < 1e-9
        diff = np.abs(_wrap(sols - q[None])).max(axis=1)
        assert diff.min() < 1e-7, "the generating joint vector must be one of the solutions"


def test_analytic_ik_regular_pose_has_eight_distinct_branches():
    sols = ik_analytic(fk(Q_WORK))
    assert len(sols) == 8
    assert len({branch_of(s) for s in sols}) == 8


def test_analytic_ik_unreachable_returns_empty():
    T = make_T(np.eye(3), np.array([2.0, 0.0, 0.5]))  # far beyond the ~1.1 m reach
    assert len(ik_analytic(T)) == 0


def test_nearest_equivalent_respects_limits_and_reference():
    q = np.array([3.0, -3.0, 0.1, 0.0, 1.0, -1.0])
    ref = q + np.array([-2 * math.pi, 2 * math.pi, 0, 0, 0, 2 * math.pi]) + 0.01
    out = nearest_equivalent(q, ref)
    np.testing.assert_allclose(out, ref - 0.01, atol=1e-12)
    assert np.all(out >= JOINT_LIMITS[:, 0]) and np.all(out <= JOINT_LIMITS[:, 1])


# --- damped least squares -------------------------------------------------------------------


def test_dls_converges_from_perturbed_seed():
    qs = _regular_samples(300, seed=5)
    rng = np.random.default_rng(6)
    for q in qs:
        T = fk(q)
        res = ik_dls(T, q + rng.normal(scale=0.1, size=6))
        assert res.converged, (q, res)
        pos, rot = _pose_errors(fk(res.q), T)
        assert pos < ACC_POS and rot < ACC_ROT
        assert pos < 1e-6 and rot < 1e-6  # the solver tolerance, much tighter than acceptance


def test_dls_unreachable_target_reports_failure_without_exploding():
    T = make_T(np.eye(3), np.array([1.5, 0.0, 0.3]))
    res = ik_dls(T, Q_WORK)
    assert not res.converged
    assert np.all(np.isfinite(res.q))
    assert res.pos_err > 0.2


def test_dls_at_wrist_singularity_stays_bounded():
    q_sing = Q_WORK.copy()
    q_sing[4] = 0.0  # wrist 2 at zero: axes of wrist 1 and wrist 3 align
    T = fk(q_sing)
    res = ik_dls(T, q_sing + 0.05)
    assert np.all(np.isfinite(res.q))
    assert np.abs(res.q - q_sing).max() < 1.0
    assert res.min_singular_value < 1e-2
    pos, rot = _pose_errors(fk(res.q), T)
    assert pos < ACC_POS and rot < ACC_ROT


def test_dls_respects_joint_limits():
    limits = JOINT_LIMITS.copy()
    limits[2] = [-0.5, 0.5]  # elbow cannot reach the target's 1.5 rad
    res = ik_dls(fk(Q_WORK), Q_WORK * 0.9, IKConfig(joint_limits=limits))
    assert limits[2, 0] <= res.q[2] <= limits[2, 1]
    assert res.at_limit[2]
    assert not res.converged


# --- path tracking ---------------------------------------------------------------------------


def _smooth_joint_path(n=64, dt=1 / 30, seed=7):
    rng = np.random.default_rng(seed)
    t = np.arange(n + 1) * dt
    amp = rng.uniform(0.05, 0.25, size=6)
    freq = rng.uniform(0.3, 1.0, size=6)
    phase = rng.uniform(0, 2 * math.pi, size=6)
    return Q_WORK + amp * (np.sin(2 * math.pi * freq * t[:, None] + phase) - np.sin(phase))


def test_track_path_recovers_smooth_joint_path_on_same_branch():
    q_path = _smooth_joint_path()
    T_targets = fk(q_path[1:])
    res = track_path(T_targets, q_path[0], dt=1 / 30)
    assert res.converged.all()
    pos, rot = _pose_errors(fk(res.q), T_targets)
    assert pos.max() < 1e-6 and rot.max() < 1e-6
    np.testing.assert_allclose(res.q, q_path[1:], atol=1e-5)
    assert not res.speed_violation.any()
    assert not res.branch_switch.any()


def test_track_path_flags_joint_speed_violation():
    q_path = _smooth_joint_path()
    q_path[40:] += np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.5])  # 0.5 rad wrist-3 jump in 1/30 s
    res = track_path(fk(q_path[1:]), q_path[0], dt=1 / 30)
    assert res.speed_violation[39]  # index 39 is the step from frame 39 to frame 40
    assert res.speed_violation.sum() == 1


def test_initial_configuration_picks_reference_branch():
    T = fk(Q_WORK)
    for sol in ik_analytic(T):
        q0 = initial_configuration(T, reference_q=sol + 0.05)
        np.testing.assert_allclose(_wrap(q0 - sol), 0.0, atol=1e-7)
