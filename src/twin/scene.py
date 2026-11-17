"""Laptop scene and physics (milestone T3). SKELETON: interfaces only, nothing simulated yet.

Blocked on lab requests 3 (laptop measurements) and 4 (gripper geometry, how the lid is closed).
Theory, parameter prior and tests: docs/thesis/twin_detailed_guide.md section 4.

Planned contents:
* MJCF built in code (like twin.robot.ur5_mjcf_xml): table (static), laptop base (free joint),
  lid (hinge with frictionloss, damping, armature, range), gripper fingers on the UR5 flange.
* Position actuators on the six arm joints, driven by the T2 joint targets
  (twin.actions.ActionsToJoints), 16 substeps per 30 Hz frame (timestep 1/480 s).
* Acceptance (T3): scripted close shuts the lid; null action leaves every body still
  (< 1e-6 m after 5 s); deterministic; stable for 200 parameter draws; timestep-halving changes the
  final lid angle by < 0.5 deg.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

PHYSICS_TIMESTEP = 1.0 / 480.0  # s; 16 substeps per 30 Hz frame (guide section 3, step 6)
SUBSTEPS_PER_FRAME = 16


@dataclass(frozen=True)
class LaptopGeometry:
    """Laptop dimensions [m, rad]. Placeholders for a 13-15 inch laptop until request 3 (check)."""

    base_size: tuple[float, float, float] = (0.32, 0.22, 0.018)  # width, depth, height (check)
    lid_size: tuple[float, float, float] = (0.32, 0.21, 0.007)  # width, height, thickness (check)
    hinge_offset: tuple[float, float] = (0.0, 0.0)  # hinge line w.r.t. the base rear edge (check)
    lid_max_angle: float = 2.3  # rad, maximum opening (check)


@dataclass(frozen=True)
class PhysicsParams:
    """One element psi of the parameter belief (guide section 4, table "Parameters, prior").

    Constraint from the null-action test: hinge_frictionloss must exceed the lid gravity torque
    ``m g l sin(theta)`` over the working range, or the lid falls shut without the robot.
    """

    hinge_frictionloss: float = 0.3  # N m (check)
    hinge_damping: float = 0.05  # N m s/rad (check)
    hinge_armature: float = 1e-4
    lid_mass: float = 0.4  # kg (check)
    lid_com_fraction: float = 0.5  # COM height as a fraction of the lid height (check)
    base_mass: float = 1.0  # kg (check)
    mu_finger_lid: float = 0.6  # (check)
    mu_base_table: float = 0.5  # (check)
    solref: tuple[float, float] = (0.005, 1.0)
    solimp: tuple[float, float, float] = (0.9, 0.95, 0.001)
    controller_lag_frames: float = 0.0  # 0 to 2 frames, fitted on demos (guide section 8)


DEFAULT_GEOMETRY = LaptopGeometry()
DEFAULT_PARAMS = PhysicsParams()


@dataclass
class SceneState:
    """Scene state x = (px, py, yaw, theta) in frame W, plus the robot joints."""

    laptop_xy: np.ndarray = field(default_factory=lambda: np.zeros(2))  # m
    laptop_yaw: float = 0.0  # rad
    lid_angle: float = 0.0  # rad, 0 = closed
    q: np.ndarray = field(default_factory=lambda: np.zeros(6))  # arm joints [rad]
    gripper: float = 0.0  # absolute gripper command (dataset units)


@dataclass(frozen=True)
class GripperModel:
    """Map from the absolute gripper scalar to finger opening (request 4).

    ``closed_value`` and ``open_value`` are the action-statistics q01 / q99 of the gripper channel
    (the production clip range); ``max_opening`` is the finger gap when fully open (check).
    """

    closed_value: float
    open_value: float
    max_opening: float = 0.085  # m (check: depends on the gripper model)

    def opening(self, g: np.ndarray) -> np.ndarray:
        """Linear map fixed by the two end values, clipped to [0, max_opening]."""
        frac = (np.asarray(g, dtype=np.float64) - self.closed_value) / (
            self.open_value - self.closed_value
        )
        return np.clip(frac, 0.0, 1.0) * self.max_opening


@dataclass
class ChunkRollout:
    """What one chunk of physics returns (one entry per 30 Hz frame)."""

    states: list[SceneState]
    lid_angle: np.ndarray  # (H,)
    contact_finger_lid: np.ndarray  # (H,) bool
    max_penetration: np.ndarray  # (H,) m, diagnostic for unstable contact


class LaptopScene:
    """MuJoCo scene: UR5 + gripper + laptop + table, stepped by T2 joint targets."""

    def __init__(
        self,
        geometry: LaptopGeometry = DEFAULT_GEOMETRY,
        params: PhysicsParams = DEFAULT_PARAMS,
        gripper: GripperModel | None = None,
        T_WB: np.ndarray | None = None,
    ):
        self.geometry = geometry
        self.params = params
        self.gripper = gripper
        self.T_WB = np.eye(4) if T_WB is None else np.asarray(T_WB, dtype=np.float64)

    def mjcf_xml(self) -> str:
        """Full scene MJCF (robot from twin.robot, laptop and table from ``geometry``)."""
        raise NotImplementedError("T3: needs laptop dimensions and gripper geometry (lab 3, 4)")

    def reset(self, state: SceneState) -> None:
        """Set the laptop pose, lid angle and arm joints; let contacts settle with the arm held."""
        raise NotImplementedError("T3")

    def step_chunk(self, q_targets: np.ndarray, gripper: np.ndarray) -> ChunkRollout:
        """Drive the actuators to ``q_targets (H, 6)`` and finger opening ``gripper (H,)``."""
        raise NotImplementedError("T3")

    def get_state(self) -> SceneState:
        raise NotImplementedError("T3")
