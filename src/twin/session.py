"""Per-env twin session (milestone T7), driven chunk by chunk with Ctrl-World's actions.

Works today in kinematics-only mode (``scene=None``): actions -> checks -> EEF targets -> IK, which
already gives the reachability statistic of guide section 3 (share of chunks where IK fails, hits
a limit, exceeds joint speed or flips branch). Physics, rendering and comparison are added as T3,
T4 and the comparison step land; until then those calls raise NotImplementedError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from twin.actions import ActionsToJoints, JointChunk
from twin.scene import ChunkRollout, LaptopScene, SceneState


@dataclass
class ChunkResult:
    joints: JointChunk
    rollout: ChunkRollout | None = None  # None in kinematics-only mode
    renders: dict[str, np.ndarray] = field(default_factory=dict)  # per physical camera (T4)


class TwinSession:
    def __init__(self, actions_to_joints: ActionsToJoints, scene: LaptopScene | None = None):
        self.a2j = actions_to_joints
        self.scene = scene
        self.eef_state: np.ndarray | None = None
        self.q: np.ndarray | None = None
        self.history: list[ChunkResult] = []

    def reset(
        self, eef_state: np.ndarray, q0: np.ndarray, scene_state: SceneState | None = None
    ) -> None:
        """Start an episode: tracked EEF state (frame W, as in the env) and initial joints.

        ``q0`` comes from the dataset joints or twin.ik.initial_configuration; ``scene_state``
        from the cached initialiser fit (T5).
        """
        self.eef_state = np.asarray(eef_state, dtype=np.float64).copy()
        self.q = np.asarray(q0, dtype=np.float64).copy()
        self.history = []
        if self.scene is not None:
            state = scene_state if scene_state is not None else SceneState(q=self.q.copy())
            self.scene.reset(state)

    def step_chunk(self, actions: np.ndarray) -> ChunkResult:
        if self.eef_state is None or self.q is None:
            raise RuntimeError("call reset() first")
        joints = self.a2j.step_chunk(self.eef_state, actions, self.q)
        rollout = None
        if self.scene is not None:
            rollout = self.scene.step_chunk(joints.q, joints.gripper)
        result = ChunkResult(joints=joints, rollout=rollout)
        self.history.append(result)
        self.eef_state = joints.next_state
        self.q = joints.q[-1].copy()
        return result

    def reachability_summary(self) -> dict[str, float]:
        """Fractions of chunks so far with each IK feasibility problem."""
        n = max(len(self.history), 1)
        ik = [r.joints.ik for r in self.history]
        return {
            "chunks": float(len(self.history)),
            "ik_failed": sum(not k.converged.all() for k in ik) / n,
            "at_limit": sum(bool(k.at_limit.any()) for k in ik) / n,
            "speed_violation": sum(bool(k.speed_violation.any()) for k in ik) / n,
            "branch_switch": sum(bool(k.branch_switch.any()) for k in ik) / n,
            "action_warnings": sum(bool(r.joints.action_check.warnings) for r in self.history) / n,
        }
