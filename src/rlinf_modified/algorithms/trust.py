"""Trust-weighted rewards and suffix advantages (proposal Step 8.2; milestone T8; decision D1).

Each reward ``r[k, i]`` (chunk k, group member i) has a trust weight ``w[k, i]`` in (0, 1]
(eq. (18)). Neutral imputation, eq. (20):

    m_k = sum_i w_ik r_ik / sum_i w_ik,      r_hat_ik = w_ik r_ik + (1 - w_ik) m_k,

and ``r_hat`` replaces ``r`` in eq. (4): discounted suffix returns ``R_hat``, then group
normalisation ``A_ik = (R_hat_ik - mean_i R_hat_ik) / (s_k + eps)``. Decision D1 picks ``s_k``:

- ``"weighted"`` (option A, the proposal's eq. (4), default): std of the imputed returns R_hat;
- ``"unweighted"`` (option B, ablation from the implementation plan): std of the raw returns R.

Conventions are those of ``grpo_action_suffix_advantages`` and of the cross-rank production
formula (``validate_and_compute_group_suffix_advantages``): unbiased std, eps added to the std,
output cast to float32 and multiplied by the loss mask, and every member of a group enters the
mean and std whatever its mask. Groups come from an explicit group index, so production groups
that span ranks (``global_group_id``) fit directly (WP 5.1); all groups have the same size G >= 2.
Derivations of the D1 properties: docs/thesis/notes/d1_scale_policy.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch

StdSource = Literal["weighted", "unweighted"]
STD_SOURCES: tuple[str, ...] = ("weighted", "unweighted")


@dataclass(frozen=True)
class TrustStats:
    """Diagnostics of one trust-weighted advantage computation (for logging, Step 8.3 item 7)."""

    weight_below_one_share: float  # share of valid (loss-mask) entries with w < 1
    weight_mean: float  # mean weight over valid entries
    std_ratio: torch.Tensor  # [T, groups]: std of R_hat / std of R; NaN where std of R is 0
    adv_abs_max: float  # max |advantage| after masking


def group_members(group_index: torch.Tensor) -> torch.Tensor:
    """Column indices of every group, shape ``[groups, G]``.

    Groups are ordered by ascending label and members by ascending column. Raises unless every
    group has the same size G >= 2 (the unbiased std of eq. (4) needs two members).
    """
    gi = group_index.reshape(-1)
    if gi.numel() == 0 or gi.dtype.is_floating_point or gi.dtype == torch.bool:
        raise ValueError(f"group_index must be a non-empty integer tensor, got {gi.dtype}")
    labels, counts = torch.unique(gi, return_counts=True)
    if int(counts.min()) < 2 or bool((counts != counts[0]).any()):
        raise ValueError(f"all groups must have the same size >= 2, got sizes {counts.tolist()}")
    order = torch.argsort(gi, stable=True)
    return order.reshape(len(labels), int(counts[0]))


def suffix_returns(rewards: torch.Tensor, dones: torch.Tensor, gamma: float) -> torch.Tensor:
    """Discounted suffix returns ``R_ik = sum_{j>=k} gamma^(j-k) r_ij``, cut at done boundaries.

    Eq. (4); the same operations in the same order as ``grpo_action_suffix_advantages``, so the
    result is bit-identical for the same input.
    """
    running = torch.zeros(rewards.shape[1], dtype=rewards.dtype, device=rewards.device)
    out = torch.empty_like(rewards)
    for step in reversed(range(rewards.shape[0])):
        continuation = (~dones[step + 1]).to(rewards.dtype)
        running = rewards[step] + float(gamma) * running * continuation
        out[step] = running
    return out


def _impute(rewards: torch.Tensor, weights: torch.Tensor, members: torch.Tensor) -> torch.Tensor:
    """Eq. (20) with no range check on the weights (tests use it for w = 0, P14 (c)).

    Needs ``sum_i w_ik > 0`` in every group and chunk, which ``w >= w_min > 0`` guarantees.
    """
    w = weights.to(rewards.dtype)[:, members]  # [T, groups, G]
    r = rewards[:, members]
    total = w.sum(dim=-1, keepdim=True)
    if not bool((total > 0).all()):
        raise ValueError("the weights of every group and chunk must have a positive sum")
    m = (w * r).sum(dim=-1, keepdim=True) / total
    r_hat = torch.empty_like(rewards)
    r_hat[:, members] = w * r + (1.0 - w) * m
    return r_hat


def _normalise(
    R_hat: torch.Tensor,
    R_raw: torch.Tensor,
    members: torch.Tensor,
    std_source: StdSource,
    epsilon: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Group normalisation of eq. (4) with the D1 scale; returns (advantages, std_hat, std_raw).

    The advantages are unmasked and in the input dtype; the stds have shape ``[T, groups]``.
    """
    grouped = R_hat[:, members]  # [T, groups, G], laid out like the reshape in the old function
    mean = grouped.mean(dim=-1, keepdim=True)
    std_hat = grouped.std(dim=-1, keepdim=True)
    std_raw = R_raw[:, members].std(dim=-1, keepdim=True)
    std = std_hat if std_source == "weighted" else std_raw
    adv = torch.empty_like(R_hat)
    adv[:, members] = (grouped - mean) / (std + epsilon)
    return adv, std_hat.squeeze(-1), std_raw.squeeze(-1)


def _check_weights(
    rewards: torch.Tensor, weights: torch.Tensor, group_index: torch.Tensor, w_min: float | None
) -> torch.Tensor:
    if rewards.ndim != 2:
        raise ValueError(f"rewards must be [T,N], got {tuple(rewards.shape)}")
    if weights.shape != rewards.shape:
        raise ValueError(f"weights must match rewards: {weights.shape} != {rewards.shape}")
    if group_index.numel() != rewards.shape[1]:
        raise ValueError(f"group_index must have N={rewards.shape[1]} entries")
    if not torch.isfinite(weights).all():
        raise ValueError("weights contain NaN or Inf")
    if w_min is not None and not 0.0 < w_min <= 1.0:
        raise ValueError(f"w_min must be in (0, 1], got {w_min}")
    low = 0.0 if w_min is None else w_min
    below = weights <= 0.0 if w_min is None else weights < w_min
    if bool(below.any()) or bool((weights > 1.0).any()):
        bound = "(0, 1]" if w_min is None else f"[{low}, 1]"
        raise ValueError(f"weights must lie in {bound}")
    return group_members(group_index)


def trust_weighted_rewards(
    rewards: torch.Tensor,
    weights: torch.Tensor,
    group_index: torch.Tensor,
    *,
    w_min: float | None = None,
) -> torch.Tensor:
    """Imputed rewards ``r_hat [T, N]`` of eq. (20) (Step 8.2; properties P14 (a), (b), (d)).

    ``weights`` must be finite and in (0, 1], or in ``[w_min, 1]`` when ``w_min`` is given; the
    floor itself is set where the weights are built (eqs. (18)-(19)).
    """
    members = _check_weights(rewards, weights, group_index, w_min)
    return _impute(rewards, weights, members)


def trust_weighted_suffix_advantages(
    rewards: torch.Tensor,
    weights: torch.Tensor,
    dones: torch.Tensor,
    loss_mask: torch.Tensor,
    group_index: torch.Tensor,
    *,
    gamma: float,
    std_source: StdSource = "weighted",
    epsilon: float = 1e-6,
    w_min: float | None = None,
) -> tuple[torch.Tensor, TrustStats]:
    """Trust-weighted GRPO suffix advantages: eq. (20) into eq. (4) (Step 8.2, P14, D1).

    Args:
        rewards: ``[T, N]`` chunk rewards (T chunks, N trajectories).
        weights: ``[T, N]`` trust weights, see ``trust_weighted_rewards``.
        dones: ``[T+1, N]`` boolean done boundaries.
        loss_mask: ``[T, N]``; multiplies the output only.
        group_index: ``[N]`` integer group label per trajectory (equal group sizes >= 2).
        gamma: discount in [0, 1].
        std_source: D1 scale, ``"weighted"`` (A, default) or ``"unweighted"`` (B).
        epsilon: added to the std, as in eq. (4).

    Returns:
        ``(advantages, stats)``: float32 ``[T, N]`` advantages times the mask, and TrustStats.
        With ``weights == 1`` the advantages equal ``grpo_action_suffix_advantages`` bit for bit.
    """
    if rewards.ndim != 2:
        raise ValueError(f"rewards must be [T,N], got {tuple(rewards.shape)}")
    if loss_mask.shape != rewards.shape:
        raise ValueError("loss_mask shape must match rewards")
    if dones.shape != (rewards.shape[0] + 1, rewards.shape[1]):
        raise ValueError("dones must have shape [T+1,N]")
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must be in [0,1]")
    if std_source not in STD_SOURCES:
        raise ValueError(f"std_source must be one of {STD_SOURCES}, got {std_source!r}")
    if not epsilon >= 0.0:
        raise ValueError(f"epsilon must be >= 0, got {epsilon}")
    if not torch.isfinite(rewards).all():
        raise ValueError("rewards contain NaN or Inf")
    members = _check_weights(rewards, weights, group_index, w_min)

    r_hat = _impute(rewards, weights, members)
    R_hat = suffix_returns(r_hat, dones, gamma)
    R_raw = suffix_returns(rewards, dones, gamma)
    adv, std_hat, std_raw = _normalise(R_hat, R_raw, members, std_source, epsilon)
    advantages = adv.float() * loss_mask.to(dtype=torch.float32)

    valid = loss_mask.to(torch.bool)
    w_valid = weights[valid].double()
    nan = float("nan")
    stats = TrustStats(
        weight_below_one_share=float((w_valid < 1.0).double().mean()) if w_valid.numel() else nan,
        weight_mean=float(w_valid.mean()) if w_valid.numel() else nan,
        std_ratio=torch.where(std_raw > 0, std_hat / std_raw, torch.full_like(std_hat, nan)),
        adv_abs_max=float(advantages.abs().max()),
    )
    return advantages, stats
