"""Tests for the implemented parts of the T3-T7 skeleton; the rest raises NotImplementedError."""

from __future__ import annotations

import numpy as np
import pytest

from twin.cameras import CameraIntrinsics, project
from twin.scene import GripperModel, LaptopScene
from twin.transforms import make_T, rotvec_to_matrix


def test_gripper_model_end_values_and_clip():
    g = GripperModel(closed_value=0.0, open_value=0.08, max_opening=0.085)
    np.testing.assert_allclose(
        g.opening([0.0, 0.04, 0.08, -1.0, 1.0]), [0.0, 0.0425, 0.085, 0.0, 0.085]
    )


def test_project_principal_point_and_offset():
    K = CameraIntrinsics(600.0, 600.0, 320.0, 240.0, 640, 480).K()
    T_WC = make_T(rotvec_to_matrix([0.2, -0.1, 0.3]), np.array([0.5, 0.1, 1.0]))
    on_axis = T_WC[:3, 3] + 2.0 * T_WC[:3, 2]
    off_axis = on_axis + 0.1 * T_WC[:3, 0]  # 0.1 m along camera x at 2 m depth -> +30 px in u
    uv, z = project(K, T_WC, np.stack([on_axis, off_axis]))
    np.testing.assert_allclose(z, [2.0, 2.0])
    np.testing.assert_allclose(uv, [[320.0, 240.0], [350.0, 240.0]], atol=1e-9)


def test_scene_is_a_stub():
    with pytest.raises(NotImplementedError):
        LaptopScene().mjcf_xml()


def test_session_kinematics_only():
    pytest.importorskip("torch")
    from twin.actions import ActionsToJoints, identity_actions
    from twin.robot import fk
    from twin.session import TwinSession
    from twin.transforms import so3_log

    q0 = np.array([0.3, -1.2, 1.5, -1.9, -1.57, 0.4])
    T = fk(q0)
    session = TwinSession(ActionsToJoints())
    session.reset(np.r_[T[:3, 3], so3_log(T[:3, :3]), 0.03], q0)
    a = identity_actions(32, gripper=0.03)
    a[:, 2] = 0.002  # 2 mm per step along the EEF z axis
    for _ in range(3):
        session.step_chunk(a)
    summary = session.reachability_summary()
    assert summary["chunks"] == 3 and summary["ik_failed"] == 0 and summary["speed_violation"] == 0
    # 3 chunks x 32 steps x 2 mm along the start z axis (no rotation in the actions).
    np.testing.assert_allclose(fk(session.q)[:3, 3], T[:3, 3] + 0.192 * T[:3, 2], atol=1e-4)
