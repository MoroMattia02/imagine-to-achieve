"""Headless three-view rendering (milestones T0 and T4). SKELETON.

T0 (next step, no lab data): off-screen 192x320 render with mujoco.Renderer, time per frame.
Backend: MUJOCO_GL=egl on Linux with a GPU (checked once on the RTX 4070 workstation, 17 Nov:
one 192x320 frame rendered); default GL on Windows; EGL on the GH200 nodes (check).
T4: cameras from twin.cameras, textured render, per-body segmentation masks. Guide section 6.
"""

from __future__ import annotations

import numpy as np


class TwinRenderer:
    def __init__(self, model, height: int = 192, width: int = 320):
        self.model = model
        self.height = height
        self.width = width

    def render(self, data, camera: str) -> np.ndarray:
        """RGB ``(H, W, 3)`` uint8 from a named MJCF camera."""
        raise NotImplementedError("T0")

    def render_masks(self, data, camera: str) -> dict[str, np.ndarray]:
        """Boolean masks per body group (robot, lid, base) for silhouette fitting (T4/T5)."""
        raise NotImplementedError("T4")
