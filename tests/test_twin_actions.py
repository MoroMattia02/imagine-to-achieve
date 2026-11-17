"""T2: 10-D action checks and action -> EEF target conversion.

The twin must feed its IK with exactly the EEF states Ctrl-World is conditioned on. The
strongest test below (test_matches_production_env_conversion) runs the production env method
``CtrlWorldEnv._convert_via_analytic_ur5_rot6d`` on a stand-in ``self`` and compares outputs; it
is skipped if the vendored runtime cannot be imported. The convention tests use an independent
oracle: rot6d is *encoded* here (first two columns of a known rotation) and the twin pipeline,
which decodes with the repo function, must reproduce the body-frame chain T_{i+1} = T_i dT.
"""

from __future__ import annotations

import math
import sys
from types import MethodType, SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from twin.actions import (  # noqa: E402
    PRODUCTION_ADAPTER,
    ActionCheckConfig,
    AdapterConfig,
    actions_to_eef_targets,
    check_actions,
    identity_actions,
)
from twin.repo_import import REPO_ROOT  # noqa: E402
from twin.transforms import geodesic_angle, make_T, rotvec_to_matrix  # noqa: E402

F32_POS = 1e-5  # m; the repo chain runs in float32 (as in production)
F32_ROT = 1e-4  # rad


def _encode_rot6d(R):
    """Test oracle: rot6d = [col0, col1] of R (cosmos-framework convention)."""
    return np.concatenate([R[..., :, 0], R[..., :, 1]], axis=-1)


def _random_deltas(n, rng, max_trans=0.01, max_angle=0.05):
    trans = rng.uniform(-max_trans, max_trans, size=(n, 3))
    axes = rng.normal(size=(n, 3))
    axes /= np.linalg.norm(axes, axis=1, keepdims=True)
    angles = rng.uniform(0, max_angle, size=(n, 1))
    return trans, rotvec_to_matrix(axes * angles)


def _actions_from_deltas(trans, dR, gripper):
    return np.concatenate([trans, _encode_rot6d(dR), gripper[:, None]], axis=-1)


START = np.array([0.45, -0.10, 0.30, 2.9, -0.4, 0.2, 0.03])


# --- action checks ---------------------------------------------------------------------------


def test_check_accepts_valid_actions():
    rng = np.random.default_rng(0)
    trans, dR = _random_deltas(32, rng)
    report = check_actions(_actions_from_deltas(trans, dR, np.full(32, 0.03)))
    assert report.ok, report.errors
    assert report.warnings == []
    assert report.rot6d_residual.max() < 1e-6


@pytest.mark.parametrize("shape", [(32, 9), (32,), (2, 3, 32, 10)])
def test_check_rejects_wrong_shape(shape):
    report = check_actions(np.zeros(shape))
    assert not report.ok
    assert "shape" in report.errors[0]


def test_check_rejects_nonfinite_and_degenerate_rot6d():
    a = identity_actions(32)
    a[3, 0] = np.nan
    a[5, 3:9] = [1, 0, 0, 2, 0, 0]  # parallel columns: cross product is zero
    a[7, 3:9] = 0.0  # zero columns
    report = check_actions(a)
    assert not report.ok
    joined = " ".join(report.errors)
    assert "non-finite" in joined and "degenerate rot6d" in joined
    assert set(np.flatnonzero(report.degenerate_rot6d[0])) == {5, 7}


def test_check_warns_on_large_steps_and_gripper_out_of_range():
    a = identity_actions(32, gripper=0.03)
    a[2, 0] = 0.2  # 20 cm in one 1/15 s step
    a[4, 3:9] = _encode_rot6d(rotvec_to_matrix([0.0, 0.0, 1.0]))  # 57 deg in one step
    a[6, 9] = 0.5
    a[8, 3:9] = [1.3, 0, 0, 0, 0.8, 0]  # non-unit columns: projected, but worth a warning
    cfg = ActionCheckConfig(gripper_range=(0.0, 0.08))
    report = check_actions(a, cfg)
    assert report.ok
    text = " ".join(report.warnings)
    assert "translation" in text and "rotation" in text and "gripper" in text and "rot6d" in text
    assert report.rot_angle[0, 4] == pytest.approx(1.0, abs=1e-5)


# --- conversion conventions ------------------------------------------------------------------


def test_identity_actions_keep_pose_constant():
    out = actions_to_eef_targets(START, identity_actions(32, gripper=0.03))
    for states in (out.policy_states, out.ctrl_states):
        np.testing.assert_allclose(
            states[0, :, :3], np.broadcast_to(START[:3], states[0, :, :3].shape), atol=1e-6
        )
        R = rotvec_to_matrix(states[0, :, 3:6])
        assert geodesic_angle(R, rotvec_to_matrix(START[3:6])[None]).max() < F32_ROT


def test_body_frame_chain_matches_oracle():
    rng = np.random.default_rng(1)
    trans, dR = _random_deltas(32, rng)
    out = actions_to_eef_targets(START, _actions_from_deltas(trans, dR, np.full(32, 0.03)))
    T = make_T(rotvec_to_matrix(START[3:6]), START[:3])
    for i in range(32):
        T = T @ make_T(dR[i], trans[i])  # T_{i+1} = T_i dT, delta in the current EEF frame
        s = out.policy_states[0, i]
        assert np.linalg.norm(s[:3] - T[:3, 3]) < F32_POS
        assert geodesic_angle(rotvec_to_matrix(s[3:6]), T[:3, :3]) < F32_ROT


def test_translation_is_expressed_in_body_frame():
    start = START.copy()
    start[3:6] = [0.0, 0.0, math.pi / 2]  # EEF x axis points along world +y
    a = identity_actions(1)
    a[0, 0] = 0.01
    out = actions_to_eef_targets(start, a)
    np.testing.assert_allclose(out.policy_states[0, 0, :3] - start[:3], [0.0, 0.01, 0.0], atol=1e-6)


def test_resampling_and_ctrl_world_alignment():
    rng = np.random.default_rng(2)
    trans, dR = _random_deltas(32, rng)
    out = actions_to_eef_targets(START, _actions_from_deltas(trans, dR, rng.uniform(0, 0.08, 32)))
    assert out.policy_states.shape == (1, 32, 7)
    assert out.ctrl_states.shape == (1, 64, 7)
    # 30 Hz frame 2k+1 is at time (k+1)/15 s: the k-th policy state.
    np.testing.assert_allclose(out.ctrl_states[0, 1::2], out.policy_states[0], atol=1e-6)
    # Ctrl-World condition = [s_t, s_{t+1}, ..., s_{t+63}]; internal rollout -> next = s_{t+64}.
    np.testing.assert_allclose(out.ctrl_condition[0, 0], START, atol=1e-6)
    np.testing.assert_allclose(out.ctrl_condition[0, 1:], out.ctrl_states[0, :-1], atol=0)
    np.testing.assert_allclose(out.next_state[0], out.ctrl_states[0, -1], atol=0)


def test_gripper_is_absolute_and_clipped():
    a = identity_actions(32)
    a[:, 9] = np.linspace(-0.1, 0.2, 32)
    cfg = AdapterConfig(**{**PRODUCTION_ADAPTER.__dict__, "gripper_clip": (0.0, 0.08)})
    out = actions_to_eef_targets(START, a, cfg)
    np.testing.assert_allclose(out.policy_states[0, :, 6], np.clip(a[:, 9], 0.0, 0.08), atol=1e-7)


# --- parity with the production env code path ------------------------------------------------


def _production_env_class():
    runtime = str(REPO_ROOT / "third_party" / "rlinf_runtime")
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    try:
        from rlinf.envs.world_model.world_model_ctrl_world_env import CtrlWorldEnv
    except Exception as exc:  # heavy runtime deps missing
        pytest.skip(f"vendored runtime not importable: {exc!r}")
    return CtrlWorldEnv


def _fake_env(cls, current_state, q01, q99):
    """Stand-in ``self`` with the attributes the production conversion reads (close config)."""
    fake = SimpleNamespace(
        current_states=torch.as_tensor(current_state, dtype=torch.float32)[None],
        device=torch.device("cpu"),
        adapter_translation_gain=1.0,
        adapter_rotation_gain=1.0,
        adapter_translation_frame="body",
        adapter_translation_sign=1.0,
        adapter_rotation_mode="body",
        adapter_gripper_hard_clamp=True,
        adapter_gripper_hard_mode="clip_only",
        adapter_gripper_hard_threshold=0.0,
        action_stats={"q01": np.asarray(q01), "q99": np.asarray(q99)},
        action_fps_resample=True,
        cosmos_action_fps=15.0,
        ctrl_condition_fps=30.0,
        ctrl_world_chunk=64,
        ctrl_world_internal_rollout=True,
    )
    for name in (
        "_apply_adapter_gripper_hard_clamp",
        "_align_adapter_states_for_ctrl_world",
        "_maybe_resample_adapter_states",
    ):
        setattr(fake, name, MethodType(getattr(cls, name), fake))
    return fake


def test_matches_production_env_conversion():
    cls = _production_env_class()
    rng = np.random.default_rng(3)
    trans, dR = _random_deltas(32, rng, max_trans=0.02, max_angle=0.1)
    actions = _actions_from_deltas(trans, dR, rng.uniform(-0.02, 0.1, 32))[None].astype(np.float32)
    q01 = np.r_[np.full(9, -1.0), 0.0]
    q99 = np.r_[np.full(9, 1.0), 0.08]
    fake = _fake_env(cls, START, q01, q99)
    condition, next_state = cls._convert_via_analytic_ur5_rot6d(fake, actions)

    cfg = AdapterConfig(**{**PRODUCTION_ADAPTER.__dict__, "gripper_clip": (0.0, 0.08)})
    out = actions_to_eef_targets(START, actions[0], cfg)
    np.testing.assert_array_equal(out.ctrl_condition.astype(np.float32), condition)
    np.testing.assert_array_equal(out.next_state.astype(np.float32), next_state)
