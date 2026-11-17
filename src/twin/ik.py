"""UR5 inverse kinematics (milestone T2): Jacobian, closed form, damped least squares, paths.

All poses are ``T_BE`` (base B to TCP E) as 4x4 matrices, the output of :func:`twin.robot.fk`.

* :func:`jacobian`: geometric Jacobian at the TCP, rows ``[v; w]`` in the base frame. With standard
  DH, joint i turns about the z axis of frame i-1, so column i is
  ``[z_{i-1} x (p_E - o_{i-1}); z_{i-1}]``.
* :func:`ik_analytic`: the closed-form solutions (up to eight: shoulder x elbow x wrist),
  derived for the DH chain of ``twin.robot`` (see the comments in the function). Used to
  pick the initial branch and as a feasibility oracle. Every returned solution is checked by FK.
* :func:`ik_dls`: damped least squares from a warm start, the per-frame solver for paths. It stays
  on the branch of its seed, which is what a continuous motion needs.
* :func:`track_path`: warm-started DLS along a target sequence, with the feasibility flags used by
  the twin (convergence, joint limits, joint speed, branch switch, distance to singularity).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from twin.robot import JOINT_LIMITS, TCP_OFFSET, UR5_DH, dh_transform, fk
from twin.transforms import geodesic_angle, invert_T, make_T, so3_log

# Maximum joint speed of the original UR5 (CB3): 180 deg/s on every joint (check with the
# datasheet / lab; UR5e base and shoulder are also 180 deg/s, wrists 180 deg/s).
UR5_MAX_JOINT_SPEED = np.full(6, math.pi)

_A2, _A3 = UR5_DH[1][0], UR5_DH[2][0]
_D4, _D6 = UR5_DH[3][1], UR5_DH[5][1]
_T_6E = make_T(np.eye(3), np.asarray(TCP_OFFSET))
_T_E6 = invert_T(_T_6E)


def _wrap_pi(x: np.ndarray) -> np.ndarray:
    """Wrap angles to [-pi, pi)."""
    return (np.asarray(x) + math.pi) % (2.0 * math.pi) - math.pi


# --- Jacobian --------------------------------------------------------------------------------


def joint_frames(q: np.ndarray) -> np.ndarray:
    """``T_B,i`` for i = 0..6 (frame 0 = base), shape ``(7, 4, 4)``, for one joint vector."""
    q = np.asarray(q, dtype=np.float64)
    frames = np.empty((7, 4, 4))
    frames[0] = np.eye(4)
    for i, (a, d, alpha) in enumerate(UR5_DH):
        frames[i + 1] = frames[i] @ dh_transform(a, d, alpha, q[i])
    return frames


def jacobian(q: np.ndarray) -> np.ndarray:
    """Geometric Jacobian ``(6, 6)`` of the TCP: ``[v; w] = J(q) dq`` in the base frame."""
    frames = joint_frames(q)
    p_E = (frames[6] @ _T_6E)[:3, 3]
    z = frames[:6, :3, 2]
    o = frames[:6, :3, 3]
    return np.vstack([np.cross(z, p_E - o).T, z.T])


# --- closed form -----------------------------------------------------------------------------


def branch_of(q: np.ndarray) -> tuple[int, int, int]:
    """UR5 branch ``(shoulder, elbow, wrist)`` of a joint vector, each +1 or -1.

    shoulder: which of the two theta_1 roots (sign of cos(theta_1 - phi), phi = azimuth of the
    wrist centre); elbow: sign of sin(theta_3); wrist: sign of sin(theta_5). The branch changes
    only through a singularity (shoulder: wrist centre on the base axis; elbow: arm stretched or
    folded; wrist: theta_5 = 0 or pi).
    """
    q = np.asarray(q, dtype=np.float64)
    T06 = fk(q, tcp=False)
    p5 = T06[:3, 3] - _D6 * T06[:3, 2]
    phi = math.atan2(p5[1], p5[0])
    return (
        1 if math.cos(q[0] - phi) >= 0 else -1,
        1 if math.sin(q[2]) >= 0 else -1,
        1 if math.sin(q[4]) >= 0 else -1,
    )


def ik_analytic(T_BE: np.ndarray, *, wrist_eps: float = 1e-9, tol: float = 1e-7) -> np.ndarray:
    """All closed-form UR5 solutions for one TCP pose, wrapped to [-pi, pi). Shape ``(n, 6)``.

    Derivation for this DH chain (``A_i = Rz(q_i) Tz(d_i) Tx(a_i) Rx(alpha_i)``):

    1. Flange ``T06 = T_BE T_tcp^-1``; wrist centre (frame-5 origin) ``p5 = p6 - d6 z6``.
    2. In frame 1 the wrist centre has z = d4: ``s1 p5x - c1 p5y = d4``, so with
       ``r = |p5_xy|`` and ``phi = atan2(p5y, p5x)``: ``q1 = phi + asin(d4/r)`` or
       ``phi + pi - asin(d4/r)``. Needs ``r >= |d4|``.
    3. ``R16 = Rz(q2+q3+q4) Ry(-q5) Rz(q6)``; its third row is ``s1 R06[0,:] - c1 R06[1,:]``
       ``= (s5 c6, -s5 s6, c5)``: gives ``q5 = +-acos(c5)`` and, if ``s5 != 0``, ``q6``.
    4. ``T14 = A1^-1 T06 (A5 A6)^-1 = Rz(q2)Tx(a2)Rz(q3)Tx(a3)Rz(q4)Tz(d4)Rx(pi/2)``: ``q2+q3+q4``
       from its first column, and a planar 2R problem in its translation gives ``q3 = +-acos``
       and ``q2``; ``q4`` is the remainder.

    At a wrist singularity (``|s5| < wrist_eps``) only ``q4 + q6`` is defined; ``q6 = 0`` is used.
    Solutions whose FK misses the pose by more than ``tol`` (m or rad) are dropped, so numerical
    edge cases return fewer solutions rather than wrong ones.
    """
    T_BE = np.asarray(T_BE, dtype=np.float64)
    T06 = T_BE @ _T_E6
    R06, p6 = T06[:3, :3], T06[:3, 3]
    p5 = p6 - _D6 * R06[:, 2]
    r = math.hypot(p5[0], p5[1])
    if r < abs(_D4):
        return np.empty((0, 6))
    phi = math.atan2(p5[1], p5[0])
    gamma = math.asin(_D4 / r)

    sols = []
    for q1 in (phi + gamma, phi + math.pi - gamma):
        s1, c1 = math.sin(q1), math.cos(q1)
        row = s1 * R06[0, :] - c1 * R06[1, :]
        c5 = float(np.clip(row[2], -1.0, 1.0))
        for q5 in (math.acos(c5), -math.acos(c5)):
            s5 = math.sin(q5)
            q6 = 0.0 if abs(s5) < wrist_eps else math.atan2(-row[1] / s5, row[0] / s5)
            A1 = dh_transform(*UR5_DH[0], np.float64(q1))
            A56 = dh_transform(*UR5_DH[4], np.float64(q5)) @ dh_transform(
                *UR5_DH[5], np.float64(q6)
            )
            T14 = invert_T(A1) @ T06 @ invert_T(A56)
            q234 = math.atan2(T14[1, 0], T14[0, 0])
            x, y = T14[0, 3], T14[1, 3]
            c3 = (x * x + y * y - _A2 * _A2 - _A3 * _A3) / (2.0 * _A2 * _A3)
            if abs(c3) > 1.0 + 1e-9:
                continue
            c3 = float(np.clip(c3, -1.0, 1.0))
            for q3 in (math.acos(c3), -math.acos(c3)):
                s3 = math.sin(q3)
                q2 = math.atan2(y, x) - math.atan2(_A3 * s3, _A2 + _A3 * c3)
                q4 = q234 - q2 - q3
                sols.append([q1, q2, q3, q4, q5, q6])
    if not sols:
        return np.empty((0, 6))
    sols = _wrap_pi(np.array(sols))
    T_check = fk(sols)
    ok = (np.linalg.norm(T_check[:, :3, 3] - T_BE[:3, 3], axis=-1) < tol) & (
        geodesic_angle(T_check[:, :3, :3], T_BE[None, :3, :3]) < tol
    )
    sols = sols[ok]
    # Remove duplicates (e.g. elbow fully stretched gives q3 = +-0).
    unique = []
    for s in sols:
        if all(np.abs(_wrap_pi(s - u)).max() > 1e-9 for u in unique):
            unique.append(s)
    return np.array(unique).reshape(-1, 6)


def nearest_equivalent(
    q: np.ndarray, q_ref: np.ndarray, joint_limits: np.ndarray = JOINT_LIMITS
) -> np.ndarray:
    """Per joint, the representative ``q + 2 pi k`` inside the limits that is closest to ``q_ref``.

    UR joints turn +-2 pi, so a wrapped solution has up to two representatives. Joints for which
    no representative fits inside the limits are clipped (and will show up as ``at_limit``).
    """
    q = np.asarray(q, dtype=np.float64)
    q_ref = np.asarray(q_ref, dtype=np.float64)
    k = np.round((q_ref - q) / (2.0 * math.pi))
    out = q + 2.0 * math.pi * k
    for shift in (-1.0, 1.0):  # move inside the limits if the closest one is outside
        cand = out + shift * 2.0 * math.pi
        outside = (out < joint_limits[:, 0]) | (out > joint_limits[:, 1])
        inside = (cand >= joint_limits[:, 0]) & (cand <= joint_limits[:, 1])
        out = np.where(outside & inside, cand, out)
    return np.clip(out, joint_limits[:, 0], joint_limits[:, 1])


def initial_configuration(
    T_BE: np.ndarray, reference_q: np.ndarray, joint_limits: np.ndarray = JOINT_LIMITS
) -> np.ndarray:
    """Joint vector for ``T_BE`` on the branch closest to ``reference_q`` (frame 0 of a demo).

    Use the recorded joints when the dataset has them; this is the fallback when only the EEF
    pose is known. ``reference_q`` is the lab's usual working pose (check with the lab).
    """
    sols = ik_analytic(T_BE)
    if len(sols) == 0:
        raise ValueError("pose is outside the UR5 workspace (no closed-form solution)")
    reps = np.array([nearest_equivalent(s, reference_q, joint_limits) for s in sols])
    return reps[np.argmin(np.abs(reps - reference_q).sum(axis=1))]


# --- damped least squares --------------------------------------------------------------------


@dataclass(frozen=True)
class IKConfig:
    """Damped-least-squares settings. Tolerances are far below the T2 acceptance (1 mm, 0.1 deg)."""

    pos_tol: float = 1e-6  # m
    rot_tol: float = 1e-6  # rad
    max_iters: int = 100
    # Singular-value-based damping (Nakamura & Hanafusa style): no damping while the smallest
    # singular value is above sigma_threshold, rising smoothly to damping_max at a singularity.
    # The damping is also scaled by min(1, |e| / damping_error_scale): it protects large steps
    # near a singularity but fades out close to the solution, where the undamped step is small
    # anyway. Without this, reachable poses near the elbow or wrist singularity converge only
    # linearly (rate s^2 / (s^2 + lambda^2)) and stall above the tolerance.
    damping_max: float = 0.05
    sigma_threshold: float = 0.05
    damping_error_scale: float = 0.01  # m or rad
    damping_floor: float = 1e-10  # lambda^2, keeps s / (s^2 + lambda^2) finite at s = 0
    max_step: float = 0.5  # rad per iteration, largest single-joint update
    joint_limits: np.ndarray = field(default_factory=lambda: JOINT_LIMITS.copy())


DEFAULT_IK = IKConfig()


@dataclass
class IKResult:
    q: np.ndarray
    converged: bool
    iters: int
    pos_err: float  # m
    rot_err: float  # rad
    at_limit: np.ndarray  # (6,) bool, joint sits on a limit
    min_singular_value: float  # of J at the solution; ~0 near a singularity


def pose_error(T_target: np.ndarray, T: np.ndarray) -> np.ndarray:
    """6-D error ``[p_t - p; log(R_t R^T)]`` in the base frame (spatial rotation error)."""
    e_p = T_target[:3, 3] - T[:3, 3]
    e_r = so3_log(T_target[:3, :3] @ T[:3, :3].T)
    return np.concatenate([e_p, e_r])


def ik_dls(T_target: np.ndarray, q_seed: np.ndarray, config: IKConfig = DEFAULT_IK) -> IKResult:
    """Damped least squares from ``q_seed``: ``dq = V diag(s/(s^2+lambda^2)) U^T e``."""
    lo, hi = config.joint_limits[:, 0], config.joint_limits[:, 1]
    q = np.clip(np.asarray(q_seed, dtype=np.float64), lo, hi)
    it = 0
    for it in range(1, config.max_iters + 1):
        e = pose_error(T_target, fk(q))
        if np.linalg.norm(e[:3]) < config.pos_tol and np.linalg.norm(e[3:]) < config.rot_tol:
            it -= 1
            break
        U, s, Vt = np.linalg.svd(jacobian(q))
        s_min = s[-1]
        lam2 = 0.0
        if s_min < config.sigma_threshold:
            lam2 = (1.0 - (s_min / config.sigma_threshold) ** 2) * config.damping_max**2
            lam2 *= min(1.0, float(np.linalg.norm(e)) / config.damping_error_scale)
        lam2 = max(lam2, config.damping_floor)
        dq = Vt.T @ ((s / (s * s + lam2)) * (U.T @ e))
        step = np.abs(dq).max()
        if step > config.max_step:
            dq *= config.max_step / step
        q = np.clip(q + dq, lo, hi)
    T = fk(q)
    e = pose_error(T_target, T)
    pos_err, rot_err = float(np.linalg.norm(e[:3])), float(np.linalg.norm(e[3:]))
    tol_q = 1e-9
    return IKResult(
        q=q,
        converged=pos_err < config.pos_tol and rot_err < config.rot_tol,
        iters=it,
        pos_err=pos_err,
        rot_err=rot_err,
        at_limit=(q <= lo + tol_q) | (q >= hi - tol_q),
        min_singular_value=float(np.linalg.svd(jacobian(q), compute_uv=False)[-1]),
    )


# --- paths -----------------------------------------------------------------------------------


@dataclass
class PathIKResult:
    """Per-frame IK results along a path of N targets. Index i is the step into target i."""

    q: np.ndarray  # (N, 6)
    converged: np.ndarray  # (N,) bool
    pos_err: np.ndarray  # (N,) m
    rot_err: np.ndarray  # (N,) rad
    at_limit: np.ndarray  # (N, 6) bool
    joint_step: np.ndarray  # (N, 6) |q_i - q_{i-1}| (q_{-1} = start)
    speed_violation: np.ndarray  # (N,) bool, some joint faster than max_joint_speed
    min_singular_value: np.ndarray  # (N,)
    branch_switch: np.ndarray  # (N,) bool, UR5 branch differs from the previous frame
    iters: np.ndarray  # (N,)

    @property
    def feasible(self) -> bool:
        """Reachable, inside the limits, within the joint speed, no branch flip."""
        return bool(
            self.converged.all()
            and not self.at_limit.any()
            and not self.speed_violation.any()
            and not self.branch_switch.any()
        )


def track_path(
    T_targets: np.ndarray,
    q_start: np.ndarray,
    *,
    dt: float,
    config: IKConfig = DEFAULT_IK,
    max_joint_speed: np.ndarray = UR5_MAX_JOINT_SPEED,
) -> PathIKResult:
    """Warm-started DLS along ``T_targets (N, 4, 4)``, starting from the joint state ``q_start``.

    ``T_targets[i]`` is the pose at time ``(i + 1) dt`` and ``q_start`` the joints at time 0. Each
    frame is seeded with the previous solution, so the path stays on the start branch unless it
    is forced through a singularity (flagged by ``branch_switch``). No angle normalisation is
    done: joints keep their +-2 pi range, so continuity is never broken by wrapping.
    """
    T_targets = np.asarray(T_targets, dtype=np.float64)
    n = T_targets.shape[0]
    q_prev = np.asarray(q_start, dtype=np.float64)
    branch_prev = branch_of(q_prev)
    out = {
        k: []
        for k in (
            "q",
            "converged",
            "pos_err",
            "rot_err",
            "at_limit",
            "min_singular_value",
            "branch_switch",
            "iters",
        )
    }
    for i in range(n):
        res = ik_dls(T_targets[i], q_prev, config)
        branch = branch_of(res.q)
        out["q"].append(res.q)
        out["converged"].append(res.converged)
        out["pos_err"].append(res.pos_err)
        out["rot_err"].append(res.rot_err)
        out["at_limit"].append(res.at_limit)
        out["min_singular_value"].append(res.min_singular_value)
        out["branch_switch"].append(branch != branch_prev)
        out["iters"].append(res.iters)
        q_prev, branch_prev = res.q, branch
    q = np.array(out["q"]).reshape(n, 6)
    steps = np.abs(np.diff(np.vstack([np.asarray(q_start, dtype=np.float64)[None], q]), axis=0))
    return PathIKResult(
        q=q,
        converged=np.array(out["converged"], dtype=bool),
        pos_err=np.array(out["pos_err"]),
        rot_err=np.array(out["rot_err"]),
        at_limit=np.array(out["at_limit"], dtype=bool).reshape(n, 6),
        joint_step=steps,
        speed_violation=(steps > max_joint_speed[None] * dt).any(axis=1),
        min_singular_value=np.array(out["min_singular_value"]),
        branch_switch=np.array(out["branch_switch"], dtype=bool),
        iters=np.array(out["iters"]),
    )
