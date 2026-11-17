"""Scene initialiser (milestone T5). SKELETON.

Offline, once per start episode (32 train + 8 eval), cached by episode id; never in the RL loop.
SAM 3 masks of the first frame (three views) + render-and-compare fit of x = (px, py, yaw, theta),
keeping the near-optimal set rather than one point. Needs T3, T4, SAM 3 weights and the dataset.
Guide section 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from twin.scene import SceneState

SCENE_CACHE_DIR = Path("scene_cache")  # scene_cache/episode_XXX.json (not committed)


@dataclass
class EpisodeFit:
    episode_id: int
    best: SceneState
    near_optimal: list[SceneState]  # states within the fit tolerance (ambiguity set)
    iou_per_view: dict[str, float]
    q0: np.ndarray  # initial joints: recorded if available, else twin.ik.initial_configuration


def fit_episode(episode_id: int) -> EpisodeFit:
    raise NotImplementedError("T5: needs T3 scene, T4 cameras, SAM 3 and the dataset")


def load_cached_fit(episode_id: int, cache_dir: Path = SCENE_CACHE_DIR) -> EpisodeFit:
    raise NotImplementedError("T5")
