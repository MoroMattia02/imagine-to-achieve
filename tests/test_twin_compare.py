"""WP 1.3: change features and the distance D-tilde (proposal Step 4, eqs. (11)-(12), P4; Step 7.2).

Acceptance (data_free_roadmap.md, WP 1.3), on random unit vectors: D-tilde is a pseudometric
(symmetry, triangle inequality, D(X, X) = 0); D <= 4 (P4 b); a constant offset b on phi_t and
phi_ref gives D = 0 (P4 c); S <= d(theta) for every twin sample; kappa = 0 when all twin samples
coincide (Step 7.2). Plus: windows outside the chunk do not matter, and averaging over views
commutes with eq. (11).
"""

from __future__ import annotations

import numpy as np
import pytest

from twin.cameras import PHYSICAL_CAMERAS
from twin.compare import average_views, change_features, d_tilde, grounded_scores

D = 32  # feature dimension (V-JEPA 2 is larger; the maths does not depend on it)
TW = 12  # windows in the whole video up to the end of chunk k
CHUNK = np.arange(4, 9)  # window positions T_k of chunk k


def _unit(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def _video(rng: np.random.Generator) -> np.ndarray:
    """Change features of one random clip: unit phi_t [TW, D] and unit phi_ref [D]."""
    return change_features(_unit(rng.normal(size=(TW, D))), _unit(rng.normal(size=D)))


# --- change features --------------------------------------------------------------------------


def test_change_features_is_the_difference_and_checks_unit_norm():
    rng = np.random.default_rng(0)
    phi, ref = _unit(rng.normal(size=(TW, D))), _unit(rng.normal(size=D))
    np.testing.assert_array_equal(change_features(phi, ref), phi - ref)
    with pytest.raises(ValueError, match="unit"):
        change_features(2.0 * phi, ref)
    with pytest.raises(ValueError, match="unit"):
        change_features(phi, 0.5 * ref)
    with pytest.raises(ValueError):
        change_features(phi[:, :-1], ref)  # dimension mismatch
    with pytest.raises(ValueError):
        change_features(phi[0], ref)  # phi must be [Tw, d]


# --- P4 (a): pseudometric ---------------------------------------------------------------------


def test_d_tilde_is_a_pseudometric():
    rng = np.random.default_rng(1)
    for _ in range(300):
        x, y, z = _video(rng), _video(rng), _video(rng)
        assert d_tilde(x, x, CHUNK) == 0.0
        assert d_tilde(x, y, CHUNK) == d_tilde(y, x, CHUNK)
        assert d_tilde(x, z, CHUNK) <= d_tilde(x, y, CHUNK) + d_tilde(y, z, CHUNK) + 1e-12
        assert d_tilde(x, y, CHUNK) >= 0.0
    # Random high-dimensional vectors are nearly orthogonal, where even squared distances obey
    # the triangle inequality. Collinear change features are the critical case: equality.
    a = _video(rng) / 4.0
    x, y, z = np.zeros_like(a), a, 2.0 * a
    assert d_tilde(x, z, CHUNK) == pytest.approx(d_tilde(x, y, CHUNK) + d_tilde(y, z, CHUNK))


def test_d_tilde_is_the_mean_euclidean_norm_over_the_chunk_windows():
    rng = np.random.default_rng(2)
    x, y = _video(rng), _video(rng)
    expected = np.mean([np.sqrt(np.sum((x[t] - y[t]) ** 2)) for t in CHUNK])  # eq. (12)
    assert d_tilde(x, y, CHUNK) == pytest.approx(expected, rel=1e-12)


def test_windows_outside_the_chunk_do_not_matter():
    rng = np.random.default_rng(3)
    x, y = _video(rng), _video(rng)
    y2 = y.copy()
    outside = np.setdiff1d(np.arange(TW), CHUNK)
    y2[outside] = _video(rng)[outside]
    assert d_tilde(x, y, CHUNK) == d_tilde(x, y2, CHUNK)


# --- P4 (b): bounded by 4, and the bound is attained -----------------------------------------


def test_d_tilde_is_at_most_four_and_four_is_attained():
    rng = np.random.default_rng(4)
    assert max(d_tilde(_video(rng), _video(rng), CHUNK) for _ in range(500)) <= 4.0
    e = np.zeros(D)
    e[0] = 1.0
    x = change_features(np.tile(-e, (TW, 1)), e)  # c = -2e
    y = change_features(np.tile(e, (TW, 1)), -e)  # c = +2e
    assert d_tilde(x, y, CHUNK) == 4.0


def test_bound_also_holds_after_averaging_views():
    rng = np.random.default_rng(5)
    for _ in range(100):
        xs = {v: _video(rng) for v in PHYSICAL_CAMERAS}
        ys = {v: _video(rng) for v in PHYSICAL_CAMERAS}
        assert d_tilde(average_views(xs), average_views(ys), CHUNK) <= 4.0


# --- P4 (c): a constant offset cancels -------------------------------------------------------


def test_constant_offset_on_phi_and_phi_ref_gives_zero():
    # Unit features that stay unit under one constant offset b: all of them in the slice
    # phi . u = beta of the sphere, and b = -2 beta u (a reflection of that slice).
    rng = np.random.default_rng(6)
    u = _unit(rng.normal(size=D))

    def on_slice(n, beta):
        v = rng.normal(size=(n, D))
        v = _unit(v - (v @ u)[:, None] * u)  # unit, orthogonal to u
        return beta * u + np.sqrt(1.0 - beta**2) * v

    for beta in (0.1, 0.5, 0.9):
        phi_x, ref_x = on_slice(TW, beta), on_slice(1, beta)[0]
        b = -2.0 * beta * u
        phi_y, ref_y = phi_x + b, ref_x + b  # still unit-normalised
        x, y = change_features(phi_x, ref_x), change_features(phi_y, ref_y)
        assert d_tilde(x, y, CHUNK) < 1e-14
        assert np.linalg.norm(phi_y - phi_x) > 0.1  # the features themselves do differ


# --- Step 7.2: grounded score S and twin spread kappa ----------------------------------------


def test_grounded_score_is_the_minimum_over_twin_samples():
    rng = np.random.default_rng(7)
    for K in (1, 2, 7):
        c_w = _video(rng)
        c_s = np.stack([_video(rng) for _ in range(K)])
        S, kappa = grounded_scores(c_w, c_s, CHUNK)
        d = [d_tilde(c_w, c_s[j], CHUNK) for j in range(K)]  # eq. (16)
        assert all(S <= dj for dj in d)
        assert S == min(d)
        pairs = [d_tilde(c_s[a], c_s[b], CHUNK) for a in range(K) for b in range(K)]
        assert kappa == pytest.approx(max(pairs), rel=1e-12)


def test_kappa_is_zero_when_all_twin_samples_coincide():
    rng = np.random.default_rng(8)
    c_w, one = _video(rng), _video(rng)
    S, kappa = grounded_scores(c_w, np.stack([one] * 5), CHUNK)
    assert kappa == 0.0
    assert S == d_tilde(c_w, one, CHUNK)


# --- views -----------------------------------------------------------------------------------


def test_average_views_commutes_with_change_features():
    # The proposal averages phi over cameras before eq. (11); averaging the per-view change
    # features is the same by linearity, and keeps the unit-norm check per view.
    rng = np.random.default_rng(9)
    phis = {v: _unit(rng.normal(size=(TW, D))) for v in PHYSICAL_CAMERAS}
    refs = {v: _unit(rng.normal(size=D)) for v in PHYSICAL_CAMERAS}
    per_view = {v: change_features(phis[v], refs[v]) for v in PHYSICAL_CAMERAS}
    phi_mean = np.mean([phis[v] for v in PHYSICAL_CAMERAS], axis=0)
    ref_mean = np.mean([refs[v] for v in PHYSICAL_CAMERAS], axis=0)
    np.testing.assert_allclose(average_views(per_view), phi_mean - ref_mean, atol=1e-15)
    # Insertion order of the dict does not change the result.
    reordered = dict(reversed(list(per_view.items())))
    np.testing.assert_array_equal(average_views(reordered), average_views(per_view))


def test_average_views_validates_names_and_shapes():
    rng = np.random.default_rng(10)
    good = {v: _video(rng) for v in PHYSICAL_CAMERAS}
    np.testing.assert_array_equal(average_views({"d435_rgb": good["d435_rgb"]}), good["d435_rgb"])
    with pytest.raises(ValueError, match="camera"):
        average_views({"main": good["d435_rgb"]})  # role names are not physical camera names
    with pytest.raises(ValueError):
        average_views({})
    with pytest.raises(ValueError):
        average_views({"d435_rgb": good["d435_rgb"], "d405_0_rgb": good["d405_0_rgb"][:-1]})


# --- validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "window_index",
    # A 2-entry mask has no duplicates and would be read as the indices [1, 0].
    [
        np.array([], dtype=int),
        np.array([0, TW]),
        np.array([-1]),
        np.array([3, 3]),
        np.array([True, False]),
    ],
    ids=["empty", "out_of_range", "negative", "duplicate", "boolean"],
)
def test_invalid_window_index_is_rejected(window_index):
    rng = np.random.default_rng(11)
    x, y = _video(rng), _video(rng)
    with pytest.raises(ValueError):
        d_tilde(x, y, window_index)


def test_shape_mismatches_are_rejected():
    rng = np.random.default_rng(12)
    x, y = _video(rng), _video(rng)
    with pytest.raises(ValueError):
        d_tilde(x, y[:-1], CHUNK)
    with pytest.raises(ValueError):
        grounded_scores(x, y, CHUNK)  # c_s must be [K, Tw, d]
    with pytest.raises(ValueError):
        grounded_scores(x, np.empty((0, TW, D)), CHUNK)
