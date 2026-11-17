"""numpy SO(3) / SE(3) helpers for the twin.

Rotations are kept as matrices inside the twin. Axis-angle (the repo's EEF state convention
``[x, y, z, rx, ry, rz, gripper]``) is converted only at the boundary, with these helpers.
rot6d is never converted here: the repo's own function is imported by path for that.
"""
from __future__ import annotations

import numpy as np

_SMALL_ANGLE = 1e-4


def skew(v: np.ndarray) -> np.ndarray:
    """``[v]x`` for ``v`` of shape ``(..., 3)``, returning ``(..., 3, 3)``."""
    v = np.asarray(v, dtype=np.float64)
    x, y, z = v[..., 0], v[..., 1], v[..., 2]
    zero = np.zeros_like(x)
    return np.stack(
        [
            np.stack([zero, -z, y], axis=-1),
            np.stack([z, zero, -x], axis=-1),
            np.stack([-y, x, zero], axis=-1),
        ],
        axis=-2,
    )


def rotvec_to_matrix(rotvec: np.ndarray) -> np.ndarray:
    """Rodrigues: axis-angle ``(..., 3)`` to rotation matrices ``(..., 3, 3)``.

    ``R = I + A [r]x + B [r]x^2`` with ``A = sin(t)/t`` and ``B = (1 - cos(t))/t^2``, where
    ``t = |r|``. A Taylor series is used for small ``t``, so the map is smooth at zero.
    """
    r = np.asarray(rotvec, dtype=np.float64)
    theta = np.linalg.norm(r, axis=-1)
    small = theta < _SMALL_ANGLE
    t = np.where(small, 1.0, theta)  # avoid 0/0 in the unused branch
    t2 = theta * theta
    A = np.where(small, 1.0 - t2 / 6.0 + t2 * t2 / 120.0, np.sin(t) / t)
    B = np.where(small, 0.5 - t2 / 24.0 + t2 * t2 / 720.0, (1.0 - np.cos(t)) / (t * t))
    K = skew(r)
    eye = np.broadcast_to(np.eye(3), K.shape)
    return eye + A[..., None, None] * K + B[..., None, None] * (K @ K)


def geodesic_angle(R_a: np.ndarray, R_b: np.ndarray) -> np.ndarray:
    """Geodesic distance on SO(3) (rad) between ``(..., 3, 3)`` rotation matrices.

    Uses ``atan2(sin, cos)`` of ``M = R_a^T R_b``, with ``sin = |vee(M - M^T)| / 2`` and
    ``cos = (tr M - 1) / 2``. Unlike ``arccos`` alone, this is accurate near 0 and near pi.
    """
    R_a = np.asarray(R_a, dtype=np.float64)
    R_b = np.asarray(R_b, dtype=np.float64)
    M = np.swapaxes(R_a, -1, -2) @ R_b
    vee = np.stack(
        [M[..., 2, 1] - M[..., 1, 2], M[..., 0, 2] - M[..., 2, 0], M[..., 1, 0] - M[..., 0, 1]],
        axis=-1,
    )
    sin = 0.5 * np.linalg.norm(vee, axis=-1)
    cos = 0.5 * (np.trace(M, axis1=-2, axis2=-1) - 1.0)
    return np.arctan2(sin, cos)


def so3_log(R: np.ndarray) -> np.ndarray:
    """Log map: rotation matrices ``(..., 3, 3)`` to axis-angle ``(..., 3)`` with norm in [0, pi].

    Inverse of :func:`rotvec_to_matrix`. Away from 0 and pi the axis comes from
    ``vee(R - R^T) / (2 sin t)``. Near 0 a series is used. Near pi, ``R - R^T`` vanishes, so the
    axis is taken from the largest column of ``(R + I) / 2`` (= ``n n^T`` at t = pi), with its
    sign fixed by ``vee(R - R^T)``. Only the symmetric part is used there:
    ``(R + R^T) / 2 = cos t I + (1 - cos t) n n^T`` holds exactly, with no skew contamination.
    """
    R = np.asarray(R, dtype=np.float64)
    vee = np.stack(
        [R[..., 2, 1] - R[..., 1, 2], R[..., 0, 2] - R[..., 2, 0], R[..., 1, 0] - R[..., 0, 1]],
        axis=-1,
    )
    sin = 0.5 * np.linalg.norm(vee, axis=-1)
    cos = 0.5 * (np.trace(R, axis1=-2, axis2=-1) - 1.0)
    theta = np.arctan2(sin, cos)

    # Regular and small-angle branch: r = vee * theta / (2 sin theta).
    small = theta < _SMALL_ANGLE
    safe_sin = np.where(small, 1.0, sin)
    t2 = theta * theta
    scale = np.where(small, 0.5 * (1.0 + t2 / 6.0 + 7.0 * t2 * t2 / 360.0), 0.5 * theta / safe_sin)
    out = vee * scale[..., None]

    # Near-pi branch.
    near_pi = theta > np.pi - 1e-3
    if np.any(near_pi):
        Rn = R[near_pi]
        c = cos[near_pi][..., None, None]
        S = (0.5 * (Rn + np.swapaxes(Rn, -1, -2)) - c * np.eye(3)) / (1.0 - c)  # = n n^T
        idx = np.argmax(np.diagonal(S, axis1=-2, axis2=-1), axis=-1)
        n = np.take_along_axis(S, idx[:, None, None].repeat(3, axis=1), axis=-1)[..., 0]
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        sign = np.where(np.sum(n * vee[near_pi], axis=-1) < 0.0, -1.0, 1.0)
        out[near_pi] = n * (sign * theta[near_pi])[..., None]
    return out


def invert_T(T: np.ndarray) -> np.ndarray:
    """Inverse of homogeneous transforms ``(..., 4, 4)``: ``[R^T, -R^T p; 0 1]``."""
    T = np.asarray(T, dtype=np.float64)
    R_t = np.swapaxes(T[..., :3, :3], -1, -2)
    return make_T(R_t, -np.einsum("...ij,...j->...i", R_t, T[..., :3, 3]))


def make_T(R: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Homogeneous transform ``[R p; 0 1]`` from ``(..., 3, 3)`` and ``(..., 3)``."""
    R = np.asarray(R, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    batch = np.broadcast_shapes(R.shape[:-2], p.shape[:-1])
    T = np.zeros(batch + (4, 4))
    T[..., :3, :3] = R
    T[..., :3, 3] = p
    T[..., 3, 3] = 1.0
    return T
