"""Cameras (milestone T4). SKELETON: data types and the pinhole projection only.

Blocked on lab request 2 (intrinsics, extrinsics, wrist mount). Guide section 5.

View naming (resolved by reading, 17 Nov): main = d405_0_rgb, wrist = d435_rgb, side/extra =
d405_1_rgb (cosmos_framework camera_layout.py CLOSE_DESKTOP_* layouts, consistent with the
production config comment). The plan's "main = d435_rgb" is wrong. The terminal-goal reward
remaps these names again, so the twin keys views by the physical camera name below and never by
"main" / "wrist" / "extra".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PHYSICAL_CAMERAS = ("d405_0_rgb", "d405_1_rgb", "d435_rgb")  # dataset key suffixes
DATASET_IMAGE_SIZE = (480, 640)  # (H, W) of the recorded views
LOOP_IMAGE_SIZE = (192, 320)  # (H, W) per view in the RL loop


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole intrinsics in the OpenCV convention (x right, y down, z forward)."""

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]])

    def resized(self, height: int, width: int) -> CameraIntrinsics:
        """Intrinsics after a plain resize (no crop). 480x640 -> 192x320 is NOT aspect-preserving
        (0.4 vs 0.5); check how the env resizes before relying on this."""
        sx, sy = width / self.width, height / self.height
        return CameraIntrinsics(
            self.fx * sx,
            self.fy * sy,
            (self.cx + 0.5) * sx - 0.5,
            (self.cy + 0.5) * sy - 0.5,
            width,
            height,
        )


@dataclass(frozen=True)
class Camera:
    name: str  # one of PHYSICAL_CAMERAS
    intrinsics: CameraIntrinsics
    T_WC: np.ndarray  # camera (OpenCV axes) to world W; wrist camera: T_EC instead (check mount)
    attached_to_eef: bool = False


def project(K: np.ndarray, T_WC: np.ndarray, p_W: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Project world points ``(N, 3)`` to pixels ``(N, 2)``; also returns depth ``(N,)``.

    MuJoCo cameras look along -z with y up; convert with diag(1, -1, -1) when building the MJCF
    camera from ``T_WC`` (check sign conventions in the T4 projected-TCP test).
    """
    p_W = np.atleast_2d(np.asarray(p_W, dtype=np.float64))
    R, t = T_WC[:3, :3], T_WC[:3, 3]
    p_C = (p_W - t) @ R  # R^T (p - t), row-vector form
    z = p_C[:, 2]
    uv = (p_C @ K.T)[:, :2] / z[:, None]
    return uv, z
