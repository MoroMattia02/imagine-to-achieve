"""Chunk-0 verdicts and the probe weight p_{i,0} (WP 1.4).

Proposal Step 6 (eqs. (14)-(15), Definition 1, Propositions 6, 8, 9, 11, the table of Step 6.4)
and the chunk-0 case of eq. (19). Pure functions on scores; they run neither model:

- the twin's effect ``tau_S(theta) = Q_S(v, a; theta) - Q_S(v, a~; theta)`` for each sample theta
  of the uncertainty set (eq. (14)) -> ``twin_decision`` (Definition 1);
- Ctrl-World's common-seed estimate ``tau_hat_W`` (Proposition 6) -> ``common_seed_effect``; its
  pooled noise scale ``sigma_W`` and significance ``s_W = |tau_hat_W| / sigma_W >= s0`` (eq. (15))
  -> ``pooled_sigma``, ``significance``;
- the table of Step 6.4 -> ``verdict``; the J probes of one candidate -> ``combine_probes``; the
  per-group null action (Proposition 8) -> ``null_action_label``;
- eq. (19) at chunk 0 -> ``probe_weight``. The no-verdict case is floored at ``w_min`` (decision
  of 26 Nov; eq. (19) has no floor there): a candidate without a verdict never weighs less than
  a proven failure, and ``p`` stays in ``[w_min, 1]``.

Candidate pairs ``Delta_im`` (Step 6.2) -> ``candidate_pair_deltas``, ``ranking_agreement``. They
are for the audit only (E1, ranking agreement on decisive pairs): they mix plan and action
differences, so they never give a per-action verdict or a weight.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum
from typing import Literal

import numpy as np


class Label(Enum):
    """The five labels of Step 6.4 (a partition of all probes, Proposition 11)."""

    CONSISTENT = "consistent"
    WRONG_REACTION = "wrong reaction"
    IGNORES_ACTION = "ignores the action"
    INVENTS_EFFECT = "invents an effect"
    NO_VERDICT = "no verdict"


# Failure labels, in the order ``combine_probes`` reports them when a candidate's probes fail in
# different ways: an opposite-sign response first, then a response without a cause, then a
# missing response. Every failure gets the same weight w_min (eq. (19)); the order only matters
# for the E1 tables.
FAILURE_LABELS: tuple[Label, ...] = (
    Label.WRONG_REACTION,
    Label.INVENTS_EFFECT,
    Label.IGNORES_ACTION,
)

TwinDecision = Literal["effect+", "effect-", "none", "undecided"]
TWIN_DECISIONS: tuple[TwinDecision, ...] = ("effect+", "effect-", "none", "undecided")


def _finite(x: float, name: str) -> float:
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite, got {x}")
    return x


def _check_bool(x: object, name: str) -> bool:
    if not isinstance(x, (bool, np.bool_)):
        raise TypeError(f"{name} must be a bool, got {type(x).__name__}")
    return bool(x)


def _vector(x: np.ndarray, name: str, min_size: int) -> np.ndarray:
    v = np.asarray(x, dtype=np.float64)
    if v.ndim != 1 or v.size < min_size or not np.all(np.isfinite(v)):
        raise ValueError(f"{name} must be a finite 1-D array of size >= {min_size}, got {v.shape}")
    return v


# --- the twin: Definition 1 -------------------------------------------------------------------


def twin_decision(tau_s: np.ndarray, eta0: float, eta: float, phase_ok: bool) -> TwinDecision:
    """Is the twin sure? Definition 1 (Step 6.3), on ``tau_s [K]`` = tau_S(theta) of eq. (14).

    - ``"effect+"`` / ``"effect-"``: ``sign tau_S`` is the same for every theta and
      ``min |tau_S| > eta``;
    - ``"none"``: ``max |tau_S| < eta0``;
    - ``"undecided"``: otherwise, and always when ``phase_ok`` is False (outside the phases where
      the twin beats Ctrl-World, Step 5.2).

    ``eta >= eta0 >= 0`` is enforced: it makes the two sure cases disjoint (Proposition 11).
    """
    tau = _vector(tau_s, "tau_s", 1)
    eta0, eta = _finite(eta0, "eta0"), _finite(eta, "eta")
    if eta0 < 0.0:
        raise ValueError(f"eta0 must be >= 0, got {eta0}")
    if eta < eta0:
        raise ValueError(f"need eta >= eta0 (Proposition 11), got eta={eta}, eta0={eta0}")
    if not _check_bool(phase_ok, "phase_ok"):
        return "undecided"
    a = np.abs(tau)
    if a.min() > eta and (np.all(tau > 0) or np.all(tau < 0)):
        return "effect+" if tau[0] > 0 else "effect-"
    if a.max() < eta0:
        return "none"
    return "undecided"


# --- Ctrl-World: Proposition 6 and eq. (15) ---------------------------------------------------


def common_seed_effect(q_a: np.ndarray, q_alt: np.ndarray) -> float:
    """Common-seed estimate of tau_W, Proposition 6: ``mean_r (Q_W(a; xi_r) - Q_W(a~; xi_r))``.

    ``q_a [R]`` and ``q_alt [R]`` are Ctrl-World's scores of the action and of its probe, run from
    the same restored state with the same seed ``xi_r`` at position r. Unbiased, with variance
    ``Var(d) / R``; its sign errors are bounded by ``Var(d) / (R tau_W^2)`` (Proposition 9). The
    value equals ``mean(q_a) - mean(q_alt)``; the shared seeds act through ``Var(d)``, which is
    small when the two runs are positively correlated.
    """
    a, b = _vector(q_a, "q_a", 1), _vector(q_alt, "q_alt", 1)
    if a.shape != b.shape:
        raise ValueError(f"need one score per seed for both actions, got {a.shape}, {b.shape}")
    return float(np.mean(a - b))


def pooled_sigma(q_w: np.ndarray) -> float:
    """Ctrl-World's noise scale at chunk 0, pooled over candidates, eq. (15).

    ``q_w [n, R]``: n rows (the probed candidates of the group) of R >= 2 seeded scores each.
    ``sigma_W^2 = sum_i sum_r (q[i, r] - mean_r q[i])^2 / (n (R - 1))``, with n (R - 1) degrees
    of freedom; each row's own mean is removed.
    """
    q = np.asarray(q_w, dtype=np.float64)
    if q.ndim != 2 or q.shape[0] < 1 or q.shape[1] < 2 or not np.all(np.isfinite(q)):
        raise ValueError(f"q_w must be a finite [n >= 1, R >= 2] array, got shape {q.shape}")
    n, R = q.shape
    centred = q - q.mean(axis=1, keepdims=True)
    return float(math.sqrt(np.sum(centred**2) / (n * (R - 1))))


def significance(tau_hat: float, sigma: float, s0: float) -> tuple[float, bool]:
    """``s_W = |tau_hat_W| / sigma_W`` and whether ``s_W >= s0`` (eq. (15)).

    ``s0 > 0`` (Step 5.3: s0 = 2). A noise-free model (``sigma = 0``) gives ``s_W = inf`` for a
    non-zero response and ``s_W = 0`` for none.
    """
    tau_hat, sigma, s0 = _finite(tau_hat, "tau_hat"), _finite(sigma, "sigma"), _finite(s0, "s0")
    if sigma < 0.0:
        raise ValueError(f"sigma must be >= 0, got {sigma}")
    if s0 <= 0.0:
        raise ValueError(f"s0 must be > 0, got {s0}")
    if sigma > 0.0:
        s_w = abs(tau_hat) / sigma
    else:
        s_w = math.inf if tau_hat != 0.0 else 0.0
    return s_w, s_w >= s0


# --- the verdict: Step 6.4 --------------------------------------------------------------------


def verdict(twin_dec: TwinDecision, w_significant: bool, sign_tau_w: int) -> Label:
    """The table of Step 6.4.

    ===================== ======================================== ==================
    twin                  Ctrl-World significant (s_W >= s0)       not significant
    ===================== ======================================== ==================
    sure of an effect     same sign: consistent; else wrong reaction ignores the action
    sure of no effect     invents an effect                        consistent
    undecided             no verdict                               no verdict
    ===================== ======================================== ==================

    ``sign_tau_w`` is ``sign tau_hat_W`` in {-1, 0, 1}; a significant response cannot have sign 0
    (``s0 > 0``), so that input is rejected.
    """
    if twin_dec not in TWIN_DECISIONS:
        raise ValueError(f"twin_dec must be one of {TWIN_DECISIONS}, got {twin_dec!r}")
    significant = _check_bool(w_significant, "w_significant")
    if sign_tau_w not in (-1, 0, 1):
        raise ValueError(f"sign_tau_w must be -1, 0 or 1, got {sign_tau_w!r}")
    if significant and sign_tau_w == 0:
        raise ValueError("a significant response needs tau_hat_W != 0 (s0 > 0)")
    if twin_dec == "undecided":
        return Label.NO_VERDICT
    if twin_dec == "none":
        return Label.INVENTS_EFFECT if significant else Label.CONSISTENT
    if not significant:
        return Label.IGNORES_ACTION
    twin_sign = 1 if twin_dec == "effect+" else -1
    return Label.CONSISTENT if sign_tau_w == twin_sign else Label.WRONG_REACTION


def combine_probes(labels: Sequence[Label]) -> Label:
    """A probed candidate's chunk-0 verdict from its J >= 1 probes (Step 6.4).

    A failure if any probe fails (``FAILURE_LABELS`` fixes which one is reported when they
    differ); otherwise consistent if any probe is consistent; otherwise no verdict. Independent of
    the order of the probes. A candidate without probes is "not probed" (``probe_weight``).
    """
    labels = list(labels)
    if not labels:
        raise ValueError("no probe labels; a candidate without probes is 'not probed'")
    for lab in labels:
        if not isinstance(lab, Label):
            raise TypeError(f"expected Label values, got {lab!r}")
    for failure in FAILURE_LABELS:
        if failure in labels:
            return failure
    return Label.CONSISTENT if Label.CONSISTENT in labels else Label.NO_VERDICT


def null_action_label(object_motion_score: float, sigma: float, s0: float) -> Label:
    """Per-group label of the null action a_0 (no end-effector motion, gripper unchanged).

    By Proposition 8 the twin's state does not move under a_0, so the twin is sure of no effect
    (assuming eta0 > 0) without consulting the phase map. Ctrl-World's object motion
    ``object_motion_score >= 0``, divided by ``sigma`` as in eq. (15), decides: significant motion
    invents an effect, otherwise consistent. Reported for RQ1 and used as a negative control; it
    does not enter the weights.
    """
    score = _finite(object_motion_score, "object_motion_score")
    if score < 0.0:
        raise ValueError(f"object_motion_score is a magnitude (>= 0), got {score}")
    _, significant = significance(score, sigma, s0)
    return verdict("none", significant, 1 if score > 0.0 else 0)


# --- the probe weight: eq. (19) at chunk 0 ----------------------------------------------------


def _logistic_of_log_ratio(s_w: float, s0: float, alpha_w: float) -> float:
    """``sigma(alpha_w (log s_w - log s0))`` for ``s_w`` in [0, inf], without overflow."""
    if s_w == 0.0:
        return 0.0
    if math.isinf(s_w):
        return 1.0
    z = alpha_w * (math.log(s_w) - math.log(s0))
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def probe_weight(
    label: Label | None,
    s_w: float | None,
    s0: float,
    alpha_w: float,
    w_min: float,
    probed: bool,
) -> float:
    """Chunk-0 probe term ``p_{i,0}`` of eq. (19), in ``[w_min, 1]``.

    - not probed (``probed=False``, ``label=None``): 1, the paper's behaviour;
    - consistent: 1;
    - wrong reaction, ignores the action, invents an effect: ``w_min``;
    - no verdict: ``max(w_min, sigma(alpha_w (log s_W - log s0)))``, non-decreasing in ``s_W``.
      The floor is the decision of 26 Nov; eq. (19) has none here.

    ``w_min`` in (0, 1), ``s0 > 0`` and ``alpha_w > 0`` are fixed in Step 5. ``s_w`` is the
    candidate's ``s_W`` (eq. (15)); it is read only in the no-verdict case. How to choose it when
    the candidate has several probes is open (WP 2.2).
    """
    w_min = _finite(w_min, "w_min")
    if not 0.0 < w_min < 1.0:
        raise ValueError(f"w_min must be in (0, 1), got {w_min}")
    s0, alpha_w = _finite(s0, "s0"), _finite(alpha_w, "alpha_w")
    if s0 <= 0.0 or alpha_w <= 0.0:
        raise ValueError(f"need s0 > 0 and alpha_w > 0, got s0={s0}, alpha_w={alpha_w}")
    if not _check_bool(probed, "probed"):
        if label is not None:
            raise ValueError(f"an unprobed candidate has no label, got {label}")
        return 1.0
    if not isinstance(label, Label):
        raise ValueError(f"a probed candidate needs a Label, got {label!r}")
    if label is Label.CONSISTENT:
        return 1.0
    if label in FAILURE_LABELS:
        return w_min
    if s_w is None or math.isnan(float(s_w)) or float(s_w) < 0.0:
        raise ValueError(f"the no-verdict weight needs s_W in [0, inf], got {s_w!r}")
    return max(w_min, _logistic_of_log_ratio(float(s_w), s0, alpha_w))


# --- candidate pairs: Step 6.2 (audit only) ---------------------------------------------------


def candidate_pair_deltas(q: np.ndarray) -> np.ndarray:
    """``Delta[i, m] = Q(V_i, a_i) - Q(V_m, a_m)`` for the G candidates of a group (Step 6.2).

    ``q [G]``: each candidate's score on its own plan. Antisymmetric with a zero diagonal. This is
    the ranking FPO uses; it mixes plan and action differences, so it is used in the audit only.
    """
    v = _vector(q, "q", 2)
    return v[:, None] - v[None, :]


def ranking_agreement(delta_w: np.ndarray, delta_s: np.ndarray, decisive_mask: np.ndarray) -> float:
    """Share of decisive candidate pairs on which Ctrl-World and the twin rank alike (E1).

    ``delta_w, delta_s [G, G]``: candidate-pair differences in each model; ``decisive_mask
    [G, G]``: symmetric boolean mask of the pairs on which the twin is decisive (its rule is set
    by the audit, WP 5.3). Each unordered pair i < m counts once; agreement means
    ``sign Delta_W = sign Delta_S``. A decisive pair needs ``Delta_S != 0``. NaN if no pair is
    decisive.
    """
    dw = np.asarray(delta_w, dtype=np.float64)
    ds = np.asarray(delta_s, dtype=np.float64)
    mask = np.asarray(decisive_mask)
    if dw.ndim != 2 or dw.shape[0] != dw.shape[1] or ds.shape != dw.shape or mask.shape != dw.shape:
        raise ValueError(f"need [G, G] arrays, got {dw.shape}, {ds.shape}, {mask.shape}")
    if not (np.all(np.isfinite(dw)) and np.all(np.isfinite(ds))):
        raise ValueError("pair differences must be finite")
    if mask.dtype != np.bool_ or not np.array_equal(mask, mask.T):
        raise ValueError("decisive_mask must be a symmetric boolean array")
    iu = np.triu_indices(dw.shape[0], k=1)
    sel = mask[iu]
    if not sel.any():
        return math.nan
    w, s = dw[iu][sel], ds[iu][sel]
    if np.any(s == 0.0):
        raise ValueError("a decisive pair needs Delta_S != 0")
    return float(np.mean(np.sign(w) == np.sign(s)))
