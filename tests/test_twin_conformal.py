"""WP 1.5: conformal threshold, divergence chunk and grounded weights (proposal Step 7,
eqs. (17)-(18), Proposition 12; calibration rules of Steps 5 and 7.3; Step 8.1 soft ablation).

Acceptance (data_free_roadmap.md, WP 1.5):
1. coverage: over 20,000 simulated calibration sets of 20 continuous exchangeable scores, the
   flag rate on a fresh score is <= alpha and >= alpha - 1/(n+1), up to binomial error;
2. abstaining chunks never flag;
3. grounded_weights is 1 before k* and w_min from k* on;
4. w = p g stays in [w_min^2, 1]; it can go below w_min, and is not clipped (decided 26 Nov);
5. per_chunk_scale uses only the fitting half and q_alpha only the calibration half.
Plus: the 1-based order-statistic index, P12's "flagged iff T > q", the soft grounded term
(logistic around q_alpha on the running max, decided 26 Nov), and the other calibration rules.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from twin.conformal import (
    DEFAULTS,
    RefereeDefaults,
    abstains,
    appearance_floor,
    calibrate,
    combined_weights,
    conformal_rank,
    conformal_threshold,
    divergence_chunk,
    grounded_weights,
    per_chunk_scale,
    split_fit_calibration,
    trajectory_score,
)

N = 5  # chunks per rollout


def _logistic(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


# --- the order statistic ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "alpha", "rank"),
    # (9, 0.7): in floats 1 - 0.7 = 0.30000000000000004 and the ceiling would give 4, not 3.
    [
        (20, 0.1, 19),
        (19, 0.1, 18),
        (9, 0.1, 9),
        (40, 0.1, 37),
        (9, 0.3, 7),
        (99, 0.05, 95),
        (9, 0.7, 3),
    ],
)
def test_conformal_rank_is_ceil_n_plus_one_times_one_minus_alpha(n, alpha, rank):
    assert conformal_rank(n, alpha) == rank


def test_conformal_threshold_is_that_order_statistic():
    rng = np.random.default_rng(0)
    T = rng.exponential(size=20)
    assert conformal_threshold(T, 0.1) == np.sort(T)[18]  # the 19th smallest (proposal)
    assert conformal_threshold(T[::-1], 0.1) == conformal_threshold(T, 0.1)
    assert conformal_threshold(T) == conformal_threshold(T, DEFAULTS.alpha)


def test_too_few_calibration_scores_are_rejected():
    rng = np.random.default_rng(1)
    conformal_threshold(rng.normal(size=9), 0.1)  # n = 9 is the smallest for alpha = 0.1
    with pytest.raises(ValueError, match="calibration"):
        conformal_threshold(rng.normal(size=8), 0.1)
    for bad_alpha in (0.0, 1.0, -0.1, math.nan):
        with pytest.raises(ValueError):
            conformal_threshold(rng.normal(size=20), bad_alpha)
    with pytest.raises(ValueError):
        conformal_threshold(np.array([0.1] * 19 + [math.nan]), 0.1)


# --- 1. coverage (P12) ------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "alpha"), [(20, 0.1), (9, 0.1), (49, 0.2)])
def test_coverage_of_a_fresh_exchangeable_score(n, alpha):
    rng = np.random.default_rng(2)
    sims = 20_000
    scores = rng.lognormal(0.0, 1.0, size=(sims, n + 1))  # continuous, exchangeable
    flags = [scores[s, n] > conformal_threshold(scores[s, :n], alpha) for s in range(sims)]
    rate = float(np.mean(flags))
    exact = (n + 1 - conformal_rank(n, alpha)) / (n + 1)
    se = math.sqrt(exact * (1.0 - exact) / sims)
    assert alpha - 1.0 / (n + 1) - 3 * se <= rate <= alpha + 3 * se  # acceptance 1
    assert abs(rate - exact) < 4 * se  # and the exact split-conformal value


def _trajectories(rng, n, scale_by_chunk):
    """Exchangeable rollouts: S [n, N] >= 0 and random abstention, i.i.d. across rollouts."""
    S = rng.gamma(2.0, 1.0, size=(n, N)) * scale_by_chunk
    kappa = rng.uniform(0.0, 1.0, size=(n, N))
    phase_ok = rng.random((n, N)) < 0.8
    return S, kappa, phase_ok


def test_coverage_of_the_whole_pipeline():
    # P12 end to end: fit m on one half, q on the other, flag a fresh real execution if it
    # diverges at any chunk. The rate must stay at most alpha.
    rng = np.random.default_rng(3)
    sims, n, alpha, kappa_max = 4000, 20, 0.1, 0.9
    scale_by_chunk = np.array([0.5, 1.0, 1.5, 2.5, 4.0])  # S grows with k
    flagged = 0
    for _ in range(sims):
        S_fit, _, _ = _trajectories(rng, n, scale_by_chunk)
        m = per_chunk_scale(S_fit)
        S, kappa, phase_ok = _trajectories(rng, n + 1, scale_by_chunk)
        ab = [abstains(kappa[j], kappa_max, phase_ok[j]) for j in range(n)]
        T = [trajectory_score(S[j], m, ab[j]) for j in range(n)]
        q = conformal_threshold(np.array(T), alpha)
        flagged += divergence_chunk(S[n], m, kappa[n], kappa_max, phase_ok[n], q) is not None
    rate = flagged / sims
    exact = 2.0 / 21.0
    assert rate <= alpha + 3 * math.sqrt(exact * (1 - exact) / sims)


def test_flagged_iff_trajectory_score_exceeds_threshold():
    # The "if and only if" in the proof of P12, and the divergence chunk is the first flag.
    rng = np.random.default_rng(4)
    for _ in range(2000):
        S, kappa, phase_ok = _trajectories(rng, 1, np.ones(N))
        S, kappa, phase_ok = S[0], kappa[0], phase_ok[0]
        m = rng.uniform(0.5, 2.0, size=N)
        q = float(rng.uniform(0.5, 3.0))
        kappa_max = float(rng.uniform(0.0, 1.0))
        ab = abstains(kappa, kappa_max, phase_ok)
        k_star = divergence_chunk(S, m, kappa, kappa_max, phase_ok, q)
        assert (k_star is not None) == (trajectory_score(S, m, ab) > q)
        flags = [k for k in range(N) if not ab[k] and S[k] / m[k] > q]
        assert k_star == (flags[0] if flags else None)


# --- 2. abstention ----------------------------------------------------------------------------


def test_abstaining_chunks_never_flag():
    rng = np.random.default_rng(5)
    m = np.ones(N)
    for _ in range(1000):
        S = rng.uniform(0.0, 2.0, size=N)
        kappa = rng.uniform(0.0, 1.0, size=N)
        phase_ok = rng.random(N) < 0.7
        ab = abstains(kappa, 0.5, phase_ok)
        S[ab] = 1e6  # enormous disagreement, but the twin abstains there
        k_star = divergence_chunk(S, m, kappa, 0.5, phase_ok, 2.5)
        assert k_star is None or not ab[k_star]
    # Every chunk abstains: never flagged, and the trajectory score is -inf.
    S = np.full(N, 1e6)
    assert divergence_chunk(S, m, np.ones(N), 0.5, np.ones(N, dtype=bool), 0.0) is None
    assert divergence_chunk(S, m, np.zeros(N), 0.5, np.zeros(N, dtype=bool), 0.0) is None
    assert trajectory_score(S, m, np.ones(N, dtype=bool)) == -math.inf


def test_abstention_rule():
    kappa = np.array([0.1, 0.5, 0.6, 0.2, 0.0])
    phase_ok = np.array([True, True, True, False, True])
    np.testing.assert_array_equal(
        abstains(kappa, 0.5, phase_ok), [False, False, True, True, False]
    )  # kappa > kappa_max is strict; outside the phases the twin abstains
    with pytest.raises(ValueError):
        abstains(kappa, 0.5, phase_ok.astype(int))
    with pytest.raises(ValueError):
        abstains(kappa[:-1], 0.5, phase_ok)


def test_divergence_chunk_hand_example():
    m = np.array([1.0, 2.0, 2.0, 4.0, 4.0])
    S = np.array([1.0, 6.0, 8.0, 4.0, 20.0])  # S / m = 1, 3, 4, 1, 5
    kappa = np.array([0.0, 0.9, 0.1, 0.1, 0.1])  # chunk 1 abstains (kappa > 0.5)
    ok = np.ones(N, dtype=bool)
    assert divergence_chunk(S, m, kappa, 0.5, ok, 2.0) == 2
    assert divergence_chunk(S, m, kappa, 1.0, ok, 2.0) == 1
    assert divergence_chunk(S, m, kappa, 0.5, ok, 5.0) is None  # S / m = 5 is not > 5
    assert trajectory_score(S, m, abstains(kappa, 0.5, ok)) == 5.0


# --- 3. grounded weights (hard) ---------------------------------------------------------------


@pytest.mark.parametrize("k_star", [None, 0, 1, 3, N - 1])
def test_grounded_weights_step(k_star):
    g = grounded_weights(k_star, N, 0.1)
    for k in range(N):
        assert g[k] == (1.0 if k_star is None or k < k_star else 0.1)


def test_grounded_weights_validation():
    with pytest.raises(ValueError):
        grounded_weights(N, N, 0.1)  # k* must be a chunk index
    with pytest.raises(ValueError):
        grounded_weights(-1, N, 0.1)
    with pytest.raises(ValueError):
        grounded_weights(None, N, 0.0)
    with pytest.raises(ValueError):
        grounded_weights(None, N, 0.1, S=np.ones(N))  # soft-only inputs without soft=True


# --- soft grounded term (Step 8.1 ablation) ---------------------------------------------------


def _soft_case(rng):
    S = rng.gamma(2.0, 1.0, size=N)
    m = rng.uniform(0.5, 2.0, size=N)
    kappa = rng.uniform(0.0, 1.0, size=N)
    phase_ok = rng.random(N) < 0.8
    return S, m, kappa, phase_ok


def test_soft_weights_formula_bounds_and_monotonicity():
    rng = np.random.default_rng(6)
    for _ in range(500):
        S, m, kappa, phase_ok = _soft_case(rng)
        q, w_min, scale = float(rng.uniform(1, 3)), float(rng.uniform(0.01, 0.5)), 0.3
        ab = abstains(kappa, 0.7, phase_ok)
        k_star = divergence_chunk(S, m, kappa, 0.7, phase_ok, q)
        g = grounded_weights(
            k_star, N, w_min, soft=True, S=S, m=m, scale=scale, q_alpha=q, abstain=ab
        )
        assert np.all((w_min <= g) & (g <= 1.0))
        assert np.all(np.diff(g) <= 0.0)  # once distrusted, stays distrusted
        running = -math.inf
        for k in range(N):
            if not ab[k]:
                running = max(running, S[k] / m[k])
            expected = (
                1.0
                if running == -math.inf
                else (w_min + (1.0 - w_min) * _logistic((q - running) / scale))
            )
            assert g[k] == pytest.approx(expected, rel=1e-12)


def test_soft_weights_tend_to_the_hard_step():
    rng = np.random.default_rng(7)
    for _ in range(300):
        S, m, kappa, phase_ok = _soft_case(rng)
        ab = abstains(kappa, 0.7, phase_ok)
        k_star = divergence_chunk(S, m, kappa, 0.7, phase_ok, 2.0)
        soft = grounded_weights(
            k_star, N, 0.1, soft=True, S=S, m=m, scale=1e-9, q_alpha=2.0, abstain=ab
        )
        np.testing.assert_allclose(soft, grounded_weights(k_star, N, 0.1), atol=1e-12)


def test_soft_weights_midpoint_and_abstention():
    m = np.ones(N)
    S = np.array([2.0, 0.5, 9.0, 0.5, 0.5])
    ab = np.array([True, False, True, False, False])  # chunk 2's large S is ignored
    g = grounded_weights(None, N, 0.2, soft=True, S=S, m=m, scale=0.5, q_alpha=2.0, abstain=ab)
    assert g[0] == 1.0  # no non-abstaining chunk yet
    assert g[1] == pytest.approx(0.2 + 0.8 * _logistic(1.5 / 0.5))
    assert g[2] == g[1] and g[3] == g[1] and g[4] == g[1]
    S[1] = 2.0  # R = q gives the midpoint
    g = grounded_weights(None, N, 0.2, soft=True, S=S, m=m, scale=0.5, q_alpha=2.0, abstain=ab)
    assert g[1] == pytest.approx(0.6)


def test_soft_weights_validation():
    S, m, ab = np.ones(N), np.ones(N), np.zeros(N, dtype=bool)
    kw = dict(S=S, m=m, scale=0.5, q_alpha=2.0, abstain=ab)
    grounded_weights(None, N, 0.1, soft=True, **kw)
    for missing in kw:
        with pytest.raises(ValueError):
            partial = {k: v for k, v in kw.items() if k != missing}
            grounded_weights(None, N, 0.1, soft=True, **partial)
    with pytest.raises(ValueError):
        grounded_weights(None, N, 0.1, soft=True, **{**kw, "scale": 0.0})
    with pytest.raises(ValueError):
        # k* must agree with the inputs: S / m = 1 < q, so nothing diverged
        grounded_weights(2, N, 0.1, soft=True, **kw)


# --- 4. combined weight w = p g (eq. (18)), no clip -------------------------------------------


def test_combined_weight_is_p_at_chunk_zero_times_g():
    g = grounded_weights(2, N, 0.1)
    w = combined_weights(0.4, g)
    np.testing.assert_array_equal(w, [0.4, 1.0, 0.1, 0.1, 0.1])  # p_{i,k} = 1 for k >= 1


def test_combined_weight_stays_in_w_min_squared_to_one_and_is_not_clipped():
    rng = np.random.default_rng(8)
    w_min = 0.1
    lowest = 1.0
    for _ in range(2000):
        p0 = float(rng.choice([1.0, w_min, rng.uniform(w_min, 1.0)]))
        k_star = rng.choice([None, *range(N)])
        w = combined_weights(p0, grounded_weights(k_star, N, w_min))
        assert np.all((w_min**2 <= w) & (w <= 1.0))
        lowest = min(lowest, w.min())
    # Below w_min only at chunk 0, when the probes failed and the rollout diverged at once.
    assert lowest == pytest.approx(w_min**2)
    w = combined_weights(w_min, grounded_weights(0, N, w_min))
    assert w[0] == pytest.approx(w_min**2) and np.all(w[1:] == w_min)


def test_combined_weight_validation():
    with pytest.raises(ValueError):
        combined_weights(0.0, np.ones(N))
    with pytest.raises(ValueError):
        combined_weights(1.5, np.ones(N))
    with pytest.raises(ValueError):
        combined_weights(0.5, np.array([1.0, 0.0]))
    with pytest.raises(ValueError):
        combined_weights(0.5, np.ones((2, N)))


# --- 5. calibration rules: split, scale, threshold --------------------------------------------


def test_split_fit_calibration():
    ids = [f"ep{i:03d}" for i in range(40)]
    fit, calib = split_fit_calibration(ids, seed=0)
    assert len(fit) == 20 and len(calib) == 20
    assert set(fit).isdisjoint(calib) and set(fit) | set(calib) == set(ids)
    assert split_fit_calibration(ids, seed=0) == (fit, calib)  # reproducible
    assert split_fit_calibration(ids[::-1], seed=0) == (fit, calib)  # input order irrelevant
    assert any(split_fit_calibration(ids, seed=s)[0] != fit for s in (1, 2, 3))
    assert list(fit) == sorted(fit) and list(calib) == sorted(calib)
    with pytest.raises(ValueError):
        split_fit_calibration(ids + ["ep000"], seed=0)  # duplicate id
    with pytest.raises(ValueError):
        split_fit_calibration(["ep000"], seed=0)


def test_per_chunk_scale_is_the_median_per_chunk():
    rng = np.random.default_rng(9)
    S_fit = rng.gamma(2.0, 1.0, size=(20, N))
    np.testing.assert_array_equal(per_chunk_scale(S_fit), np.median(S_fit, axis=0))
    with pytest.raises(ValueError):
        per_chunk_scale(np.zeros((20, N)))  # a zero scale cannot normalise
    with pytest.raises(ValueError):
        per_chunk_scale(-S_fit)
    with pytest.raises(ValueError):
        per_chunk_scale(S_fit[0])


def _demo_scores(rng, ids):
    S = {i: rng.gamma(2.0, 1.0, size=N) for i in ids}
    ab = {i: rng.random(N) < 0.2 for i in ids}
    return S, ab


def test_calibrate_uses_the_fitting_half_for_m_and_the_calibration_half_for_q():
    rng = np.random.default_rng(10)
    ids = [f"ep{i:03d}" for i in range(40)]
    fit, calib = split_fit_calibration(ids, seed=0)
    S, ab = _demo_scores(rng, ids)
    cal = calibrate(S, ab, fit, calib, 0.1)
    m = per_chunk_scale(np.stack([S[i] for i in fit]))
    np.testing.assert_array_equal(cal.m, m)
    T = np.array([trajectory_score(S[i], m, ab[i]) for i in calib])
    assert cal.q_alpha == conformal_threshold(T, 0.1)
    np.testing.assert_array_equal(cal.T_calib, T)

    # Changing calibration demos leaves m unchanged.
    S2 = dict(S)
    for i in calib:
        S2[i] = S[i] * 3.0
    np.testing.assert_array_equal(calibrate(S2, ab, fit, calib, 0.1).m, cal.m)
    # Changing a fitting demo without moving any per-chunk median leaves q unchanged.
    S3 = dict(S)
    top = max(fit, key=lambda i: S[i][0])
    S3[top] = S[top].copy()
    S3[top][0] *= 10.0  # the largest value of chunk 0 grows: the median does not move
    np.testing.assert_array_equal(calibrate(S3, ab, fit, calib, 0.1).m, cal.m)
    assert calibrate(S3, ab, fit, calib, 0.1).q_alpha == cal.q_alpha
    # Episodes in neither half play no part.
    S4, ab4 = dict(S), dict(ab)
    S4["extra"], ab4["extra"] = np.full(N, 1e3), np.zeros(N, dtype=bool)
    cal4 = calibrate(S4, ab4, fit, calib, 0.1)
    np.testing.assert_array_equal(cal4.m, cal.m)
    np.testing.assert_array_equal(cal4.T_calib, cal.T_calib)
    assert cal4.q_alpha == cal.q_alpha


def test_calibrate_rejects_overlapping_or_missing_ids():
    rng = np.random.default_rng(11)
    ids = [f"ep{i:03d}" for i in range(40)]
    S, ab = _demo_scores(rng, ids)
    fit, calib = ids[:20], ids[20:]
    with pytest.raises(ValueError, match="disjoint"):
        calibrate(S, ab, fit, calib + [fit[0]], 0.1)
    with pytest.raises(KeyError):
        calibrate(S, ab, fit, calib + ["missing"], 0.1)


def test_appearance_floor():
    rng = np.random.default_rng(12)
    dq = rng.normal(0.0, 0.05, size=200)
    eta0, eta = appearance_floor(dq)
    assert eta0 == pytest.approx(np.percentile(np.abs(dq), 95.0))
    assert eta == 2.0 * eta0
    assert appearance_floor(-dq) == (eta0, eta)  # only the size of the change matters
    eta0_100, _ = appearance_floor(np.arange(1.0, 101.0))
    assert eta0_100 == pytest.approx(95.05)  # linear interpolation between order statistics
    with pytest.raises(ValueError):
        appearance_floor(np.array([]))
    with pytest.raises(ValueError):
        appearance_floor(np.array([0.1, math.nan]))


def test_defaults_are_the_proposal_values():
    assert DEFAULTS == RefereeDefaults(s0=2.0, alpha=0.1)  # Step 5.3 and Step 7.4
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULTS.alpha = 0.2
