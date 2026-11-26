"""Conformal threshold, divergence chunk and grounded weights (WP 1.5).

Proposal Step 7 (7.3 decision rule, 7.4 eq. (17) and Proposition 12), eq. (18) of Step 8.1 with
its soft ablation, and the calibration rules of Steps 5 and 7.3, written as functions so that the
numbers cannot drift:

- abstention: the twin abstains at chunk k if ``kappa_k > kappa_max`` or chunk k lies outside the
  phases where it beats Ctrl-World (Step 5.2) -> ``abstains``;
- trajectory score, eq. (17): ``T = max_k S_k / m_k`` over the chunks that do not abstain
  -> ``trajectory_score``;
- split-conformal threshold ``q_alpha``: the ``ceil((n+1)(1-alpha))``-th smallest calibration
  score, 1-based -> ``conformal_threshold``; a rollout is flagged iff ``T > q_alpha``, which happens
  with probability at most alpha under exchangeability (Proposition 12);
- divergence chunk ``k*``: the first non-abstaining chunk with ``S_k / m_k > q_alpha``
  -> ``divergence_chunk``;
- grounded term ``g`` of eq. (18) (hard step, or the soft ablation) -> ``grounded_weights``, and
  ``w = p g`` -> ``combined_weights`` (not clipped at w_min, decided 26 Nov);
- calibration: the 20/20 split of the demonstrations (Step 5), ``m_k`` = median score per chunk
  on the fitting half (Step 7.3), ``q_alpha`` on the calibration half (Step 7.4), the appearance
  floor ``eta0`` and ``eta = 2 eta0`` (Step 5.3), and the defaults ``s0 = 2``, ``alpha = 0.1``.

Indices are 0-based chunks k = 0..N-1; ``k* = None`` stands for the proposal's ``k* = inf``.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

APPEARANCE_PERCENTILE = 95.0  # eta0 = 95th percentile of |Delta Q_S| (Step 5.3)
ETA_OVER_ETA0 = 2.0  # eta = 2 eta0 (Step 5.3)


@dataclass(frozen=True)
class RefereeDefaults:
    """Fixed referee constants: ``s0 = 2`` pooled noise standard deviations (Step 5.3) and
    ``alpha = 0.1`` (Step 7.4)."""

    s0: float = 2.0
    alpha: float = 0.1


DEFAULTS = RefereeDefaults()


@dataclass(frozen=True)
class Calibration:
    """Result of ``calibrate``: ``m [N]`` (fitting half), ``q_alpha`` and the calibration
    trajectory scores ``T_calib`` in the order of ``calib_ids`` (calibration half)."""

    m: np.ndarray
    q_alpha: float
    T_calib: np.ndarray


# --- validation helpers -----------------------------------------------------------------------


def _alpha(alpha: float) -> Fraction:
    a = float(alpha)
    if not (math.isfinite(a) and 0.0 < a < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    return Fraction(repr(a))  # 0.1 is read as 1/10 exactly


def _index(x: object, name: str) -> int:
    if isinstance(x, bool) or not isinstance(x, (int, np.integer)):
        raise ValueError(f"{name} must be an integer, got {x!r}")
    return int(x)


def _unit_interval(x: float, name: str, *, closed_low: bool) -> float:
    v = float(x)
    ok = (0.0 <= v if closed_low else 0.0 < v) and v <= 1.0
    if not (math.isfinite(v) and ok):
        raise ValueError(f"{name} must be in {'[' if closed_low else '('}0, 1], got {x}")
    return v


def _w_min(w_min: float) -> float:
    v = float(w_min)
    if not (math.isfinite(v) and 0.0 < v < 1.0):
        raise ValueError(f"w_min must be in (0, 1), got {w_min}")
    return v


def _not_nan(x: float, name: str) -> float:
    v = float(x)
    if math.isnan(v):
        raise ValueError(f"{name} must not be NaN")
    return v


def _scores(S: np.ndarray, m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    S = np.asarray(S, dtype=np.float64)
    m = np.asarray(m, dtype=np.float64)
    if S.ndim != 1 or S.size == 0 or m.shape != S.shape:
        raise ValueError(f"need S [N] and m [N] of equal shape, got {S.shape}, {m.shape}")
    if not (np.all(np.isfinite(S)) and np.all(S >= 0.0)):
        raise ValueError("S must be finite and >= 0 (a minimum of distances)")
    if not (np.all(np.isfinite(m)) and np.all(m > 0.0)):
        raise ValueError("m must be finite and > 0")
    return S, m


def _mask(x: np.ndarray, name: str, shape: tuple[int, ...]) -> np.ndarray:
    a = np.asarray(x)
    if a.dtype != np.bool_ or a.shape != shape:
        raise ValueError(f"{name} must be a bool array of shape {shape}, got {a.dtype} {a.shape}")
    return a


def _logistic(z: float) -> float:
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


# --- Step 7.3-7.4: abstention, trajectory score, threshold, divergence -----------------------


def abstains(kappa: np.ndarray, kappa_max: float, phase_ok: np.ndarray) -> np.ndarray:
    """Chunks where the twin abstains (Step 7.3): ``kappa_k > kappa_max`` or not ``phase_ok_k``.

    ``kappa [N]`` is the twin's own spread (Step 7.2, eq. (16)); ``phase_ok [N]`` marks the chunks
    inside the phases where the twin beats Ctrl-World (Step 5.2).
    """
    kappa = np.asarray(kappa, dtype=np.float64)
    if kappa.ndim != 1 or kappa.size == 0 or not np.all(np.isfinite(kappa)):
        raise ValueError(f"kappa must be a finite 1-D array, got shape {kappa.shape}")
    kappa_max = float(kappa_max)
    if not math.isfinite(kappa_max):
        raise ValueError(f"kappa_max must be finite, got {kappa_max}")
    ok = _mask(phase_ok, "phase_ok", kappa.shape)
    return (kappa > kappa_max) | ~ok


def trajectory_score(S: np.ndarray, m: np.ndarray, abstain: np.ndarray) -> float:
    """Trajectory score of eq. (17): ``T = max_k S_k / m_k`` over the non-abstaining chunks.

    ``S [N]``: grounded disagreement per chunk (``S = min_theta d(theta)``, eq. (16)); ``m [N]``:
    per-chunk scale; ``abstain [N]``: from ``abstains``. ``-inf`` if every chunk abstains (such a
    rollout is never flagged), the same rule for calibration and test scores.
    """
    S, m = _scores(S, m)
    keep = ~_mask(abstain, "abstain", S.shape)
    return float(np.max(S[keep] / m[keep])) if keep.any() else -math.inf


def conformal_rank(n: int, alpha: float) -> int:
    """1-based rank ``ceil((n+1)(1-alpha))`` of the split-conformal threshold (Step 7.4).

    Computed in exact rationals, with alpha read as the decimal it prints as, so that integer
    cases (e.g. n = 19, alpha = 0.1 gives exactly 18) are not shifted by float rounding.
    """
    n = _index(n, "n")
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    return math.ceil((n + 1) * (1 - _alpha(alpha)))


def conformal_threshold(T_scores: np.ndarray, alpha: float = DEFAULTS.alpha) -> float:
    """Split-conformal threshold ``q_alpha`` (Step 7.4, Proposition 12).

    The ``ceil((n+1)(1-alpha))``-th smallest of the n calibration trajectory scores (1-based);
    with n = 20 and alpha = 0.1, the 19th smallest. Raises if that rank exceeds n, i.e. if
    ``n < (1 - alpha) / alpha`` (n < 9 for alpha = 0.1). Scores may be ``-inf`` (calibration
    demonstrations on which the twin abstained everywhere), not NaN.
    """
    T = np.asarray(T_scores, dtype=np.float64)
    if T.ndim != 1 or T.size == 0 or np.any(np.isnan(T)) or np.any(T == math.inf):
        raise ValueError("T_scores must be a non-empty 1-D array without NaN or +inf")
    n = T.size
    k = conformal_rank(n, alpha)
    if k > n:
        a = _alpha(alpha)
        need = math.ceil((1 - a) / a)
        raise ValueError(f"{n} calibration scores are too few for alpha={alpha}: need n >= {need}")
    return float(np.sort(T)[k - 1])


def divergence_chunk(
    S: np.ndarray,
    m: np.ndarray,
    kappa: np.ndarray,
    kappa_max: float,
    phase_ok: np.ndarray,
    q_alpha: float,
) -> int | None:
    """Divergence chunk ``k*`` of one candidate (Step 7.3).

    The first chunk that does not abstain and has ``S_k / m_k > q_alpha``; ``None`` if there is
    none (the proposal's ``k* = inf``). Flagged at some chunk iff
    ``trajectory_score(S, m, abstains(kappa, kappa_max, phase_ok)) > q_alpha`` (Proposition 12).
    """
    S, m = _scores(S, m)
    ab = abstains(kappa, kappa_max, phase_ok)
    if ab.shape != S.shape:
        raise ValueError(f"kappa and phase_ok must have shape {S.shape}")
    flags = ~ab & (S / m > _not_nan(q_alpha, "q_alpha"))
    return int(np.argmax(flags)) if flags.any() else None


# --- eq. (18): grounded term and combined weight ----------------------------------------------


def grounded_weights(
    k_star: int | None,
    N: int,
    w_min: float,
    *,
    soft: bool = False,
    S: np.ndarray | None = None,
    m: np.ndarray | None = None,
    scale: float | None = None,
    q_alpha: float | None = None,
    abstain: np.ndarray | None = None,
) -> np.ndarray:
    """Grounded term ``g [N]`` of eq. (18).

    Hard (default): ``g_k = 1`` for ``k < k*`` and ``w_min`` for ``k >= k*``; all ones if
    ``k* = None``.

    Soft (``soft=True``, the Step 8.1 ablation; form decided 26 Nov):
    ``g_k = w_min + (1 - w_min) * sigmoid((q_alpha - R_k) / scale)``, where ``R_k`` is the running
    max of ``S_j / m_j`` over the non-abstaining chunks ``j <= k`` (``g_k = 1`` while there is
    none). It keeps "from k* on, distrusted" (``g`` is non-increasing in k), equals
    ``(1 + w_min) / 2`` at ``R_k = q_alpha``, and tends to the hard step as ``scale -> 0``. It
    needs ``S, m, scale, q_alpha, abstain``, and ``k_star`` must be the divergence chunk of those
    inputs, so that the hard and soft arms agree on which candidates diverged.
    """
    N = _index(N, "N")
    if N < 1:
        raise ValueError(f"N must be >= 1, got {N}")
    w_min = _w_min(w_min)
    if k_star is not None:
        k_star = _index(k_star, "k_star")
        if not 0 <= k_star < N:
            raise ValueError(f"k_star must be a chunk index in [0, {N}) or None, got {k_star}")
    soft_inputs = {"S": S, "m": m, "scale": scale, "q_alpha": q_alpha, "abstain": abstain}
    if not soft:
        given = [k for k, v in soft_inputs.items() if v is not None]
        if given:
            raise ValueError(f"{given} are used only with soft=True")
        g = np.ones(N)
        if k_star is not None:
            g[k_star:] = w_min
        return g

    missing = [k for k, v in soft_inputs.items() if v is None]
    if missing:
        raise ValueError(f"soft=True needs {missing}")
    S, m = _scores(S, m)
    if S.shape != (N,):
        raise ValueError(f"S and m must have shape ({N},), got {S.shape}")
    ab = _mask(abstain, "abstain", (N,))
    scale = float(scale)
    if not (math.isfinite(scale) and scale > 0.0):
        raise ValueError(f"scale must be finite and > 0, got {scale}")
    q = _not_nan(q_alpha, "q_alpha")
    ratio = S / m
    flags = ~ab & (ratio > q)
    expected = int(np.argmax(flags)) if flags.any() else None
    if k_star != expected:
        raise ValueError(f"k_star={k_star} disagrees with the inputs (divergence chunk {expected})")
    g = np.ones(N)
    running = -math.inf
    for k in range(N):
        if not ab[k]:
            running = max(running, float(ratio[k]))
        if running > -math.inf:
            g[k] = w_min + (1.0 - w_min) * _logistic((q - running) / scale)
    return g


def combined_weights(p0: float, g: np.ndarray) -> np.ndarray:
    """Trust weights ``w_k = p_k g_k`` of eq. (18) for one candidate, with ``p_k = 1`` for k >= 1.

    ``p0``: the chunk-0 probe term (eq. (19), ``twin.verdict.probe_weight``); ``g [N]``: the
    grounded term. Not clipped at w_min (decided 26 Nov, as eq. (18)): with ``p0, g >= w_min``,
    ``w`` lies in ``[w_min^2, 1]``, and goes below w_min only at chunk 0, when the probes failed
    and the rollout diverged at chunk 0. Always > 0, so ``m_k`` of eq. (20) is defined.
    """
    p0 = _unit_interval(p0, "p0", closed_low=False)
    g = np.asarray(g, dtype=np.float64)
    if g.ndim != 1 or g.size == 0 or not np.all(np.isfinite(g)) or not np.all((g > 0) & (g <= 1)):
        raise ValueError("g must be a 1-D array with values in (0, 1]")
    w = g.copy()
    w[0] = p0 * g[0]
    return w


# --- calibration rules (Steps 5, 5.3, 7.3, 7.4) -----------------------------------------------


def split_fit_calibration(
    episode_ids: Sequence[Hashable], seed: int
) -> tuple[tuple[Hashable, ...], tuple[Hashable, ...]]:
    """Split the demonstrations into a fitting and a calibration half (Step 5: 20/20 of 40).

    The ids are sorted first, so the split depends only on the set of ids and the seed; each half
    is returned sorted. With an odd count the calibration half gets the extra episode. The
    permutation comes from ``numpy.random.default_rng(seed)``; record the split that was used
    (numpy does not promise the same stream across versions).
    """
    ids = list(episode_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("episode ids must be unique")
    if len(ids) < 2:
        raise ValueError("need at least two episodes to split")
    ordered = sorted(ids)
    perm = np.random.default_rng(_index(seed, "seed")).permutation(len(ordered))
    half = len(ordered) // 2
    fit = tuple(sorted(ordered[i] for i in perm[:half]))
    calib = tuple(sorted(ordered[i] for i in perm[half:]))
    return fit, calib


def per_chunk_scale(S_fit: np.ndarray) -> np.ndarray:
    """Per-chunk scale ``m [N]`` (Step 7.3): the median score per chunk over the **fitting** half.

    ``S_fit [n_fit, N]``: the real demonstrations' grounded scores ``S_real`` (eq. (17)). Raises if
    a median is 0, since ``m`` normalises S.
    """
    S = np.asarray(S_fit, dtype=np.float64)
    if S.ndim != 2 or S.shape[0] < 1 or S.shape[1] < 1:
        raise ValueError(f"S_fit must be [n_fit >= 1, N >= 1], got shape {S.shape}")
    if not (np.all(np.isfinite(S)) and np.all(S >= 0.0)):
        raise ValueError("S_fit must be finite and >= 0")
    m = np.median(S, axis=0)
    if np.any(m <= 0.0):
        raise ValueError(f"a per-chunk median is 0 and cannot normalise: m = {m}")
    return m


def calibrate(
    scores: Mapping[Hashable, np.ndarray],
    abstain: Mapping[Hashable, np.ndarray],
    fit_ids: Sequence[Hashable],
    calib_ids: Sequence[Hashable],
    alpha: float = DEFAULTS.alpha,
) -> Calibration:
    """Calibration of the divergence rule (Steps 7.3-7.4) on real demonstrations.

    ``scores[id] = S_real [N]`` and ``abstain[id] [N]`` per demonstration. ``m`` uses only
    ``fit_ids`` (``per_chunk_scale``); the trajectory scores (eq. (17)) and ``q_alpha`` use only
    ``calib_ids``, normalised by that ``m``. The two id sets must be disjoint; other ids in the
    mappings are ignored.
    """
    fit, calib = list(fit_ids), list(calib_ids)
    if len(set(fit)) != len(fit) or len(set(calib)) != len(calib):
        raise ValueError("fit_ids and calib_ids must not contain duplicates")
    if not set(fit).isdisjoint(calib):
        raise ValueError("fit_ids and calib_ids must be disjoint")
    if not fit or not calib:
        raise ValueError("both halves must be non-empty")
    m = per_chunk_scale(np.stack([np.asarray(scores[i], dtype=np.float64) for i in fit]))
    T = np.array([trajectory_score(scores[i], m, abstain[i]) for i in calib])
    return Calibration(m=m, q_alpha=conformal_threshold(T, alpha), T_calib=T)


def appearance_floor(delta_q_s_appearance: np.ndarray) -> tuple[float, float]:
    """Appearance floor ``eta0`` and the effect threshold ``eta = 2 eta0`` (Step 5.3).

    ``eta0`` is the 95th percentile (numpy's default linear interpolation) of ``|Delta Q_S|`` over
    appearance-only changes of the render (lighting, texture), with geometry and actions fixed.
    """
    d = np.abs(np.asarray(delta_q_s_appearance, dtype=np.float64)).ravel()
    if d.size == 0 or not np.all(np.isfinite(d)):
        raise ValueError("need a non-empty, finite array of score differences")
    eta0 = float(np.percentile(d, APPEARANCE_PERCENTILE))
    return eta0, ETA_OVER_ETA0 * eta0
