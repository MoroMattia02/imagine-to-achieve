"""From 10-D policy actions to EEF targets and joint targets (milestone T2).

Pipeline for one chunk, identical to the production env path for the close config
(``CtrlWorldEnv._convert_via_analytic_ur5_rot6d``, world_model_ctrl_world_env.py:1599):

1. ``analytic_ur5_rot6d_delta_actions_to_eef_states`` (repo, imported by file path): 32 body-frame
   deltas ``[pos(3), rot6d(6), gripper_abs(1)]`` at 15 Hz chained as
   ``T_{i+1} = T_i dT``, gains 1.0.
2. Gripper clip to the action-statistics range [q01, q99]
   (``adapter_gripper_hard_mode: clip_only``).
3. ``resample_eef_state_sequence_by_fps`` (repo): 15 Hz -> 30 Hz, 64 states; xyz and gripper are
   linear, rotation is quaternion slerp (not linear axis-angle, as the guide first assumed).
4. Ctrl-World alignment: condition ``[s_t, ..., s_{t+63}]``; with ``ctrl_world_internal_rollout``
   the tracked state for the next chunk is ``s_{t+64}``.

Everything above runs in float32 under torch, as in production, so the twin's targets equal
Ctrl-World's conditioning bit for bit (tests/test_twin_actions.py). The twin then maps the 64
targets from the recorded-pose frame W into the robot base frame B (``T_BE = T_WB^-1 T_WE``) and
solves IK frame by frame (twin.ik.track_path).

Not here: the gripper -> finger opening map and the controller model (scene, T3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from twin.ik import DEFAULT_IK, UR5_MAX_JOINT_SPEED, IKConfig, PathIKResult, track_path
from twin.repo_import import load_eef_pose_adapter
from twin.transforms import geodesic_angle, invert_T, make_T, rotvec_to_matrix

ACTION_DIM = 10
IDENTITY_ROT6D = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])


@dataclass(frozen=True)
class AdapterConfig:
    """Conversion settings; defaults are the resolved production close config (Hydra, read 17 Nov).

    ``gripper_clip`` is ``(q01[-1], q99[-1])`` of the policy action statistics file
    (``action_stats_path`` in the config, not in the repo). ``None`` skips the clip; set it before
    comparing with Ctrl-World.
    """

    translation_gain: float = 1.0
    rotation_gain: float = 1.0
    translation_frame: str = "body"
    translation_sign: float = 1.0
    rotation_mode: str = "body"
    policy_fps: float = 15.0  # cosmos_action_fps
    ctrl_fps: float = 30.0  # ctrl_condition_fps
    resample: bool = True  # action_fps_resample
    ctrl_world_chunk: int | None = None  # None: round(H * ctrl_fps / policy_fps) = 64 for H = 32
    internal_rollout: bool = True  # ctrl_world_internal_rollout
    gripper_clip: tuple[float, float] | None = None


PRODUCTION_ADAPTER = AdapterConfig()


# --- checks on the raw 10-D vector -----------------------------------------------------------


@dataclass(frozen=True)
class ActionCheckConfig:
    """Thresholds. Hard errors stop the twin; soft limits only produce warnings.

    The soft step limits are physical plausibility bounds per 1/15 s policy step, not values
    measured on the demos (check against the demo action statistics).
    """

    max_translation_step: float = 0.05  # m per step (0.75 m/s, above UR5 TCP practice) (check)
    max_rotation_step: float = 0.35  # rad per step (~20 deg, 5 rad/s) (check)
    rot6d_norm_tol: float = 0.1  # |col norm - 1| above this: the network output is far from SO(3)
    rot6d_cos_tol: float = 0.1  # |cos(col0, col1)| above this: columns far from orthogonal
    degenerate_norm: float = 1e-6  # column norm below this: no direction (hard error)
    degenerate_cos: float = 0.999  # |cos| above this: SVD projection ill-defined (hard error)
    gripper_range: tuple[float, float] | None = None  # e.g. (q01, q99); None: no range check


DEFAULT_CHECK = ActionCheckConfig()


@dataclass
class ActionReport:
    ok: bool
    errors: list[str]
    warnings: list[str]
    trans_norm: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))  # (B, H) m
    rot_angle: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))  # (B, H) rad
    rot6d_col_norms: np.ndarray = field(default_factory=lambda: np.empty((0, 0, 2)))
    rot6d_cos: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    rot6d_residual: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))  # |raw - proj|
    nonfinite: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=bool))
    degenerate_rot6d: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=bool))
    gripper_out_of_range: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=bool))


def identity_actions(n: int, gripper: float = 0.0) -> np.ndarray:
    """``n`` null actions (no motion), gripper held at ``gripper``. Shape ``(n, 10)``."""
    a = np.zeros((n, ACTION_DIM))
    a[:, 3:9] = IDENTITY_ROT6D
    a[:, 9] = gripper
    return a


def _as_batch(actions: np.ndarray) -> np.ndarray | None:
    a = np.asarray(actions, dtype=np.float64)
    if a.ndim == 2:
        a = a[None]
    if a.ndim != 3 or a.shape[-1] != ACTION_DIM or a.shape[1] == 0:
        return None
    return a


def _steps(mask: np.ndarray) -> str:
    idx = np.argwhere(mask)
    shown = ", ".join(f"{b}:{h}" if mask.shape[0] > 1 else str(h) for b, h in idx[:8])
    return shown + (" ..." if len(idx) > 8 else "")


def check_actions(actions: np.ndarray, config: ActionCheckConfig = DEFAULT_CHECK) -> ActionReport:
    """Validate a ``(H, 10)`` or ``(B, H, 10)`` action chunk before it reaches the twin.

    Hard errors: wrong shape, non-finite values, degenerate rot6d (a zero column or parallel
    columns, for which the repo's SVD projection returns an arbitrary rotation).
    Warnings: translation or rotation step above the plausibility bound, rot6d far from
    orthonormal (the repo projects it silently), gripper outside ``gripper_range``.
    """
    a = _as_batch(actions)
    if a is None:
        shape = np.shape(actions)
        return ActionReport(False, [f"bad shape {shape}: expected (H, 10) or (B, H, 10)"], [])

    errors: list[str] = []
    warnings: list[str] = []
    nonfinite = ~np.isfinite(a).all(axis=-1)
    if nonfinite.any():
        errors.append(f"non-finite values at steps {_steps(nonfinite)}")
    a_safe = np.where(nonfinite[..., None], identity_actions(1)[0], a)

    c0, c1 = a_safe[..., 3:6], a_safe[..., 6:9]
    n0, n1 = np.linalg.norm(c0, axis=-1), np.linalg.norm(c1, axis=-1)
    norms = np.stack([n0, n1], axis=-1)
    tiny = (n0 < config.degenerate_norm) | (n1 < config.degenerate_norm)
    cos = np.where(tiny, 1.0, np.sum(c0 * c1, axis=-1) / np.maximum(n0 * n1, 1e-300))
    degenerate = (tiny | (np.abs(cos) > config.degenerate_cos)) & ~nonfinite
    if degenerate.any():
        errors.append(f"degenerate rot6d at steps {_steps(degenerate)}")

    # Rotation of each delta, decoded with the repo function on the usable steps.
    usable = ~(degenerate | nonfinite)
    rot6d = np.where(usable[..., None], a_safe[..., 3:9], IDENTITY_ROT6D)
    R = _repo_rot6d_to_matrix(rot6d)
    rot_angle = geodesic_angle(np.broadcast_to(np.eye(3), R.shape), R)
    residual = np.linalg.norm(
        rot6d - np.concatenate([R[..., :, 0], R[..., :, 1]], axis=-1), axis=-1
    )
    trans_norm = np.linalg.norm(a_safe[..., 0:3], axis=-1)

    def warn(mask: np.ndarray, what: str) -> None:
        mask = mask & usable
        if mask.any():
            warnings.append(f"{what} at {int(mask.sum())} steps ({_steps(mask)})")

    warn(
        trans_norm > config.max_translation_step,
        f"translation step > {config.max_translation_step} m",
    )
    warn(rot_angle > config.max_rotation_step, f"rotation step > {config.max_rotation_step} rad")
    warn(
        (np.abs(norms - 1.0) > config.rot6d_norm_tol).any(axis=-1)
        | (np.abs(cos) > config.rot6d_cos_tol),
        "rot6d far from orthonormal (projected by the repo)",
    )
    out_of_range = np.zeros_like(nonfinite)
    if config.gripper_range is not None:
        lo, hi = min(config.gripper_range), max(config.gripper_range)
        out_of_range = ((a_safe[..., 9] < lo) | (a_safe[..., 9] > hi)) & ~nonfinite
        warn(out_of_range, f"gripper outside [{lo}, {hi}] (will be clipped)")

    return ActionReport(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        trans_norm=trans_norm,
        rot_angle=rot_angle,
        rot6d_col_norms=norms,
        rot6d_cos=cos,
        rot6d_residual=residual,
        nonfinite=nonfinite,
        degenerate_rot6d=degenerate,
        gripper_out_of_range=out_of_range,
    )


def _repo_rot6d_to_matrix(rot6d: np.ndarray) -> np.ndarray:
    import torch

    repo = load_eef_pose_adapter()
    with torch.no_grad():
        R = repo._rot6d_to_matrix(torch.as_tensor(rot6d, dtype=torch.float32))
    return R.double().numpy()


# --- actions -> EEF targets (repo functions, float32) ----------------------------------------


@dataclass
class EEFTargets:
    """EEF states ``[x, y, z, rx, ry, rz, gripper]`` in frame W.

    Values are float32 (as in production) stored as float64.
    """

    policy_states: np.ndarray  # (B, H, 7), after each policy action (15 Hz)
    ctrl_states: np.ndarray  # (B, H_ctrl, 7), resampled to 30 Hz: times 1/30 ... H_ctrl/30
    ctrl_condition: np.ndarray  # (B, H_ctrl, 7), what Ctrl-World is conditioned on
    next_state: np.ndarray  # (B, 7), tracked EEF state the next chunk starts from


def actions_to_eef_targets(
    current_state: np.ndarray, actions: np.ndarray, config: AdapterConfig = PRODUCTION_ADAPTER
) -> EEFTargets:
    """Convert one chunk exactly as the production env does (see the module docstring).

    Args:
        current_state: tracked EEF state ``(7,)`` or ``(B, 7)`` in frame W.
        actions: ``(H, 10)`` or ``(B, H, 10)``.
    """
    import torch

    repo = load_eef_pose_adapter()
    a = _as_batch(actions)
    if a is None:
        raise ValueError(f"actions must be (H, 10) or (B, H, 10), got {np.shape(actions)}")
    s = np.asarray(current_state, dtype=np.float64)
    s = s[None] if s.ndim == 1 else s
    if s.ndim != 2 or s.shape[-1] < 7 or s.shape[0] != a.shape[0]:
        raise ValueError(f"current_state must be (7,) or (B, 7) matching actions, got {s.shape}")

    with torch.no_grad(), torch.autocast(device_type="cpu", enabled=False):
        current_states = torch.as_tensor(s, dtype=torch.float32)
        actions_t = torch.as_tensor(a, dtype=torch.float32)
        states = repo.analytic_ur5_rot6d_delta_actions_to_eef_states(
            current_states,
            actions_t,
            translation_gain=config.translation_gain,
            rotation_gain=config.rotation_gain,
            translation_frame=config.translation_frame,
            translation_sign=config.translation_sign,
            rotation_mode=config.rotation_mode,
        )
        current = repo.state_to_ctrl_world_eef_state(current_states)
        if config.gripper_clip is not None:
            # Same operation as CtrlWorldEnv._apply_adapter_gripper_hard_clamp, mode clip_only.
            lo, hi = (torch.as_tensor(v, dtype=states.dtype) for v in config.gripper_clip)
            states = states.clone()
            states[..., 6:7] = states[..., 6:7].clamp(
                min=torch.minimum(lo, hi), max=torch.maximum(lo, hi)
            )
        policy_states = states
        if config.resample:
            states = repo.resample_eef_state_sequence_by_fps(
                current,
                states,
                source_fps=config.policy_fps,
                target_fps=config.ctrl_fps,
                target_steps=config.ctrl_world_chunk,
            )
        dim = min(current.shape[-1], states.shape[-1])
        full = torch.cat([current[:, None, :dim], states[:, :, :dim]], dim=1)
        condition = full[:, :-1]
        next_state = full[:, -1] if config.internal_rollout else condition[:, -1]

    def np64(t):
        return t.numpy().astype(np.float64)

    return EEFTargets(np64(policy_states), np64(states), np64(condition), np64(next_state))


def eef_state_to_T(states: np.ndarray) -> np.ndarray:
    """``[x, y, z, rx, ry, rz, ...]`` (axis-angle) to ``(..., 4, 4)`` poses.

    Boundary conversion: the twin keeps matrices internally.
    """
    states = np.asarray(states, dtype=np.float64)
    return make_T(rotvec_to_matrix(states[..., 3:6]), states[..., :3])


# --- actions -> joint targets ----------------------------------------------------------------


@dataclass
class JointChunk:
    q: np.ndarray  # (H_ctrl, 6) joint targets at 30 Hz
    gripper: np.ndarray  # (H_ctrl,) absolute gripper command (clipped as in production)
    eef: EEFTargets
    action_check: ActionReport
    ik: PathIKResult
    next_state: np.ndarray  # (7,) tracked EEF state for the next chunk (shared with Ctrl-World)

    @property
    def feasible(self) -> bool:
        return self.action_check.ok and self.ik.feasible


class ActionsToJoints:
    """Per-env T2 stage: action chunk -> checked EEF targets -> joint targets in frame B.

    ``T_WB`` maps robot-base coordinates into the frame of the recorded EEF poses. It is unknown
    until estimated from demos (guide section 8) or given by the lab; identity is a placeholder.
    The EEF state is carried open loop exactly like Ctrl-World's (``next_state``), so both models
    follow the same commanded path; IK failures show up in ``JointChunk.ik``, not as drift.
    """

    def __init__(
        self,
        T_WB: np.ndarray | None = None,
        adapter: AdapterConfig = PRODUCTION_ADAPTER,
        ik_config: IKConfig = DEFAULT_IK,
        check_config: ActionCheckConfig = DEFAULT_CHECK,
        max_joint_speed: np.ndarray = UR5_MAX_JOINT_SPEED,
    ):
        self.T_WB = np.eye(4) if T_WB is None else np.asarray(T_WB, dtype=np.float64)
        self.T_BW = invert_T(self.T_WB)
        self.adapter = adapter
        self.ik_config = ik_config
        self.check_config = check_config
        self.max_joint_speed = max_joint_speed

    def step_chunk(
        self, current_state: np.ndarray, actions: np.ndarray, q_current: np.ndarray
    ) -> JointChunk:
        """One chunk for one env.

        ``current_state (7,)`` in W, ``actions (H, 10)``, current joints ``q_current (6,)``.
        """
        report = check_actions(actions, self.check_config)
        if not report.ok:
            raise ValueError("invalid action chunk: " + "; ".join(report.errors))
        eef = actions_to_eef_targets(current_state, actions, self.adapter)
        T_BE = self.T_BW[None] @ eef_state_to_T(eef.ctrl_states[0])
        ik = track_path(
            T_BE,
            q_current,
            dt=1.0 / (self.adapter.ctrl_fps if self.adapter.resample else self.adapter.policy_fps),
            config=self.ik_config,
            max_joint_speed=self.max_joint_speed,
        )
        return JointChunk(
            q=ik.q,
            gripper=eef.ctrl_states[0, :, 6].copy(),
            eef=eef,
            action_check=report,
            ik=ik,
            next_state=eef.next_state[0].copy(),
        )
