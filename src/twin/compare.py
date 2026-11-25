"""Comparison of a rendered and a generated video through change features (WP 1.3).

Proposal Step 4 (eqs. (11)-(12), Proposition 4, Lemma 5) and Step 7.2 (eq. (16)). Works on
feature arrays and does not know the encoder (V-JEPA 2 comes in WP 4.2):

- per physical camera v: ``phi_t`` is the pooled, unit-normalised feature of the window ending at
  t, and ``phi_ref`` the feature of a still clip of frame 0 (same preprocessing for every view);
- change since frame 0, eq. (11): ``c_t = phi_t - phi_ref``, per view (unit norm is checked);
- averaged over cameras with ``average_views``; eq. (11) is linear, so this equals the change of
  the camera-averaged features that the proposal describes;
- eq. (12): ``D(X, Y) = mean_{t in T_k} ||c_t(X) - c_t(Y)||_2`` over the windows of chunk k.

Since every per-view ``||c_t|| <= 2`` and averaging cannot increase a norm bound, D <= 4 (P4 (b)),
so the scores ``Q = -D`` of eq. (13) lie in [-4, 0] (Lemma 5).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from twin.cameras import PHYSICAL_CAMERAS

UNIT_NORM_TOL = 1e-5  # float32 encoder outputs are unit-normalised to ~1e-7


def _check_unit(x: np.ndarray, name: str, tol: float) -> None:
    err = np.abs(np.linalg.norm(x, axis=-1) - 1.0)
    if not np.all(err <= tol):
        raise ValueError(f"{name} must be unit-normalised (max |norm - 1| = {err.max():.3g})")


def change_features(
    phi: np.ndarray, phi_ref: np.ndarray, *, tol: float = UNIT_NORM_TOL
) -> np.ndarray:
    """Change since frame 0 of one camera's clip, eq. (11): ``c [Tw, d] = phi - phi_ref``.

    ``phi [Tw, d]`` (one feature per window) and ``phi_ref [d]`` must be unit-normalised.
    """
    phi = np.asarray(phi, dtype=np.float64)
    phi_ref = np.asarray(phi_ref, dtype=np.float64)
    if phi.ndim != 2 or phi_ref.ndim != 1 or phi.shape[1] != phi_ref.shape[0]:
        raise ValueError(f"need phi [Tw, d] and phi_ref [d], got {phi.shape} and {phi_ref.shape}")
    _check_unit(phi, "phi", tol)
    _check_unit(phi_ref, "phi_ref", tol)
    return phi - phi_ref


def average_views(per_view: Mapping[str, np.ndarray]) -> np.ndarray:
    """Average of per-camera arrays (change features, or features) of equal shape (Step 4).

    Keys are physical camera names (``twin.cameras.PHYSICAL_CAMERAS``: ``d405_0_rgb``,
    ``d405_1_rgb``, ``d435_rgb``), not role names. The views are summed in that fixed order, so
    the result does not depend on the order of the mapping.
    """
    if not per_view:
        raise ValueError("no views given")
    unknown = sorted(set(per_view) - set(PHYSICAL_CAMERAS))
    if unknown:
        raise ValueError(f"unknown camera names {unknown}; use {PHYSICAL_CAMERAS}")
    arrays = [np.asarray(per_view[v], dtype=np.float64) for v in PHYSICAL_CAMERAS if v in per_view]
    if any(a.shape != arrays[0].shape for a in arrays):
        raise ValueError(f"views differ in shape: {[a.shape for a in arrays]}")
    return np.mean(arrays, axis=0)


def _windows(window_index: np.ndarray, n_windows: int) -> np.ndarray:
    w = np.asarray(window_index)
    if w.ndim != 1 or w.size == 0 or not np.issubdtype(w.dtype, np.integer):
        raise ValueError("window_index must be a non-empty 1-D integer array (not a mask)")
    if w.min() < 0 or w.max() >= n_windows or np.unique(w).size != w.size:
        raise ValueError(f"window_index must hold distinct positions in [0, {n_windows})")
    return w


def _mean_window_distance(c_x: np.ndarray, c_y: np.ndarray, w: np.ndarray) -> float:
    return float(np.mean(np.linalg.norm(c_x[w] - c_y[w], axis=-1)))


def d_tilde(c_x: np.ndarray, c_y: np.ndarray, window_index: np.ndarray) -> float:
    """Distance of two clips within one chunk, eq. (12) (P4: pseudometric, at most 4).

    ``c_x, c_y [Tw, d]``: change features over the whole video up to the end of the chunk
    (measured from frame 0, as in eq. (16)); ``window_index``: the positions ``T_k`` of the
    chunk's windows. Returns ``mean_{t in T_k} ||c_x[t] - c_y[t]||_2``.
    """
    c_x, c_y = np.asarray(c_x, dtype=np.float64), np.asarray(c_y, dtype=np.float64)
    if c_x.ndim != 2 or c_x.shape != c_y.shape:
        raise ValueError(f"need two [Tw, d] arrays of equal shape, got {c_x.shape}, {c_y.shape}")
    return _mean_window_distance(c_x, c_y, _windows(window_index, c_x.shape[0]))


def grounded_scores(
    c_w: np.ndarray, c_s: np.ndarray, window_index: np.ndarray
) -> tuple[float, float]:
    """Grounded disagreement ``S`` and twin spread ``kappa`` at chunk k (Step 7.2, eq. (16)).

    ``c_w [Tw, d]``: Ctrl-World's change features; ``c_s [K, Tw, d]``: the twin's, one per
    sample theta of the uncertainty set (K >= 1). ``S = min_theta d(theta)`` with
    ``d(theta) = D(c_w, c_s[theta])``, and
    ``kappa = max_{theta, theta'} D(c_s[theta], c_s[theta'])`` (0 for K = 1 or coincident samples).
    """
    c_w, c_s = np.asarray(c_w, dtype=np.float64), np.asarray(c_s, dtype=np.float64)
    if c_w.ndim != 2 or c_s.ndim != 3 or c_s.shape[1:] != c_w.shape or c_s.shape[0] == 0:
        raise ValueError(f"need c_w [Tw, d] and c_s [K>=1, Tw, d], got {c_w.shape}, {c_s.shape}")
    w = _windows(window_index, c_w.shape[0])
    K = c_s.shape[0]
    S = min(_mean_window_distance(c_w, c_s[j], w) for j in range(K))
    kappa = max(
        (_mean_window_distance(c_s[a], c_s[b], w) for a in range(K) for b in range(a + 1, K)),
        default=0.0,
    )
    return S, kappa
