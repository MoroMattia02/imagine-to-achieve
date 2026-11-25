"""Headless rendering of the twin (milestones T0 and T4).

T0 (done, WP 1.1): off-screen RGB frames from a named MJCF camera with ``mujoco.Renderer``,
192x320 by default (the Ctrl-World view size). Backend: ``MUJOCO_GL=egl`` on Linux (set by
tests/conftest.py for pytest), MuJoCo's default GL on Windows; EGL on the GH200 nodes (check).
T4 (not started): cameras from twin.cameras, textured render, per-body segmentation masks.
Guide section 6.
"""

from __future__ import annotations

import numpy as np


class TwinRenderer:
    """Off-screen renderer for one ``MjModel``; reuse it across frames (the GL context is costly).

    The rendered state is whatever ``data`` holds: call ``mj_forward`` (or ``mj_kinematics``)
    after changing ``qpos``. Rendering never modifies ``data``.
    """

    def __init__(self, model, height: int = 192, width: int = 320):
        import mujoco

        self._mujoco = mujoco
        self.model = model
        self.height = height
        self.width = width
        self._renderer = mujoco.Renderer(model, height=height, width=width)

    def render(self, data, camera: str) -> np.ndarray:
        """RGB ``(H, W, 3)`` uint8 from the MJCF camera named ``camera`` (a new array each call)."""
        mj = self._mujoco
        if mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_CAMERA, camera) < 0:
            names = [self.model.camera(i).name for i in range(self.model.ncam)]
            raise KeyError(f"no camera {camera!r} in the model; cameras: {names}")
        self._renderer.update_scene(data, camera=camera)
        return self._renderer.render()

    def render_masks(self, data, camera: str) -> dict[str, np.ndarray]:
        """Boolean masks per body group (robot, lid, base) for silhouette fitting (T4/T5)."""
        raise NotImplementedError("T4")

    def close(self) -> None:
        self._renderer.close()

    def __enter__(self) -> TwinRenderer:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
