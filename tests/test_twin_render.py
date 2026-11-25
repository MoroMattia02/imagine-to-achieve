"""T0 (WP 1.1): headless off-screen render of the twin.

Acceptance (data_free_roadmap.md, WP 1.1; progress.md "T0 steps"): a 192x320 RGB frame from a
named camera, not one colour, and identical for two renders of the same state. The UR5 asset has
no camera, so the tests add a fixed one with MjSpec (the committed asset stays unchanged).

Timing of 100 frames (recorded in progress.md):  python tests/test_twin_render.py
(set MUJOCO_GL=egl on Linux when running it as a script; tests/conftest.py does it for pytest).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from twin.render import TwinRenderer  # noqa: E402
from twin.robot import ur5_mjcf_xml  # noqa: E402

CAMERA = "t0_cam"
Q_WORK = np.array([0.3, -1.2, 1.5, -1.9, -1.57, 0.4])


def look_at_quat(pos: np.ndarray, target: np.ndarray, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """MuJoCo camera quaternion looking from ``pos`` at ``target`` (camera looks along -z)."""
    z = pos - target
    z = z / np.linalg.norm(z)
    x = np.cross(up, z)
    x = x / np.linalg.norm(x)
    R = np.column_stack([x, np.cross(z, x), z])
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, R.reshape(-1))
    return quat


def model_with_camera() -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_string(ur5_mjcf_xml())
    pos = np.array([0.8, 0.9, 0.9])
    spec.worldbody.add_camera(
        name=CAMERA, pos=pos, quat=look_at_quat(pos, np.array([-0.25, -0.15, 0.25]))
    )
    return spec.compile()


def state(model: mujoco.MjModel, q: np.ndarray) -> mujoco.MjData:
    data = mujoco.MjData(model)
    data.qpos[:] = q
    mujoco.mj_forward(model, data)
    return data


@pytest.fixture(scope="module")
def model():
    model = model_with_camera()
    try:  # environment check only: is an OpenGL context available at all?
        mujoco.Renderer(model, height=8, width=8).close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no OpenGL context for off-screen rendering: {exc!r}")
    return model


@pytest.fixture(scope="module")
def renderer(model):
    r = TwinRenderer(model)
    yield r
    r.close()


def test_render_shape_dtype_and_not_one_colour(model, renderer):
    frame = renderer.render(state(model, Q_WORK), CAMERA)
    assert frame.shape == (192, 320, 3) and frame.dtype == np.uint8
    assert len(np.unique(frame.reshape(-1, 3), axis=0)) > 1
    # The arm is in view, not just a gradient: a clear share of pixels differs from the corner.
    assert (frame != frame[0, 0]).any(axis=-1).mean() > 0.01


def test_two_renders_of_the_same_state_are_identical(model, renderer):
    data = state(model, Q_WORK)
    a = renderer.render(data, CAMERA)
    b = renderer.render(data, CAMERA)
    assert not np.shares_memory(a, b)  # otherwise the comparison below would be vacuous
    np.testing.assert_array_equal(a, b)
    # A fresh MjData with the same q gives the same frame too.
    np.testing.assert_array_equal(a, renderer.render(state(model, Q_WORK), CAMERA))


def test_render_follows_the_state(model, renderer):
    a = renderer.render(state(model, Q_WORK), CAMERA)
    b = renderer.render(state(model, Q_WORK + np.array([0.4, 0.0, 0.0, 0.0, 0.0, 0.0])), CAMERA)
    assert (a != b).any(axis=-1).mean() > 0.005


def test_unknown_camera_is_an_error(model, renderer):
    with pytest.raises(KeyError, match="no_such_cam"):
        renderer.render(state(model, Q_WORK), "no_such_cam")


def time_frames(n: int = 100) -> float:
    """Mean ms per frame (update_scene + render + read-back) over ``n`` frames, one warm-up."""
    model = model_with_camera()
    data = state(model, Q_WORK)
    with TwinRenderer(model) as r:
        r.render(data, CAMERA)
        t0 = time.perf_counter()
        for _ in range(n):
            r.render(data, CAMERA)
        return 1e3 * (time.perf_counter() - t0) / n


if __name__ == "__main__":
    print(f"{time_frames():.2f} ms/frame (192x320, 100 frames)")
