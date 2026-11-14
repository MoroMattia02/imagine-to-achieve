"""UR5 kinematic model of the twin (milestone T1: numpy forward kinematics).

The constants are those of the repo FK ``ur5_joint_actions_to_eef_states``
(third_party/rlinf_runtime/rlinf/envs/world_model/eef_pose_adapter.py:461): the original UR5,
not the UR5e (lab request 5 is still open). That function produced Ctrl-World's conditioning
states, so the twin must reproduce it exactly; tests/test_twin_fk.py checks this against a
reference table generated from the repo function.
"""
from __future__ import annotations

import math

import numpy as np

# Standard DH, one row per joint: (a [m], d [m], alpha [rad]); T_{i-1,i} = Rz(q) Tz(d) Tx(a) Rx(alpha).
UR5_DH: tuple[tuple[float, float, float], ...] = (
    (0.0, 0.089159, math.pi / 2),
    (-0.425, 0.0, 0.0),
    (-0.39225, 0.0, 0.0),
    (0.0, 0.10915, math.pi / 2),
    (0.0, 0.09465, -math.pi / 2),
    (0.0, 0.0823, 0.0),
)

# TCP relative to the flange (frame 6): 0.18 m along z, no rotation (repo default).
TCP_OFFSET: tuple[float, float, float] = (0.0, 0.0, 0.18)

# Joint limits [rad], shape (6, 2). Original UR5: +-2*pi on every joint (check with the lab).
JOINT_LIMITS = np.array([[-2.0 * math.pi, 2.0 * math.pi]] * 6)


def dh_transform(a: float, d: float, alpha: float, theta: np.ndarray) -> np.ndarray:
    """Standard DH link transform for joint angles ``theta`` of shape ``(...)``; returns ``(..., 4, 4)``."""
    theta = np.asarray(theta, dtype=np.float64)
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    T = np.zeros(theta.shape + (4, 4))
    T[..., 0, 0] = ct
    T[..., 0, 1] = -st * ca
    T[..., 0, 2] = st * sa
    T[..., 0, 3] = a * ct
    T[..., 1, 0] = st
    T[..., 1, 1] = ct * ca
    T[..., 1, 2] = -ct * sa
    T[..., 1, 3] = a * st
    T[..., 2, 1] = sa
    T[..., 2, 2] = ca
    T[..., 2, 3] = d
    T[..., 3, 3] = 1.0
    return T


def fk(q: np.ndarray, *, tcp: bool = True) -> np.ndarray:
    """Forward kinematics ``T_BE(q)``: base frame B to TCP frame E (or flange if ``tcp=False``).

    Args:
        q: joint angles [rad], shape ``(..., 6)``.

    Returns:
        ``(..., 4, 4)`` homogeneous transforms (rotation as a matrix, no axis-angle).
    """
    q = np.asarray(q, dtype=np.float64)
    if q.shape[-1:] != (6,):
        raise ValueError(f"q must have shape (..., 6), got {q.shape}")
    T = np.broadcast_to(np.eye(4), q.shape[:-1] + (4, 4))
    for j, (a, d, alpha) in enumerate(UR5_DH):
        T = T @ dh_transform(a, d, alpha, q[..., j])
    if tcp:
        T_6E = np.eye(4)
        T_6E[:3, 3] = TCP_OFFSET
        T = T @ T_6E
    return T
