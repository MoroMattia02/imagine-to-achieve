"""WP 1.4: chunk-0 verdicts and the probe weight (proposal Step 6.3-6.4, eqs. (14)-(15), (19);
Definition 1; Propositions 6, 8, 9, 11).

Acceptance (data_free_roadmap.md, WP 1.4):
1. partition (P11): on a few thousand random inputs every probe gets exactly one label, and
   eta >= eta0 is enforced;
2. the verdict table of Step 6.4, case by case;
3. outside the phases where the twin beats Ctrl-World, the twin is always undecided;
4. sign errors (P9): on simulated common-seed runs, the sign-error rate of tau_hat_W is at most
   Var(d) / (R tau^2);
5. probe_weight lies in [w_min, 1], is 1 when not probed, and is monotone in s_W when there is
   no verdict. The floor at w_min in the no-verdict case is the decision of 26 Nov (eq. (19) has
   no floor there).
Plus: the pooled noise scale of eq. (15), the null action, probe combination, and the candidate
pairs of Step 6.2 (audit only).
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from twin.verdict import (
    FAILURE_LABELS,
    Label,
    candidate_pair_deltas,
    combine_probes,
    common_seed_effect,
    null_action_label,
    pooled_sigma,
    probe_weight,
    ranking_agreement,
    significance,
    twin_decision,
    verdict,
)

C, WR, IG, INV, NV = (
    Label.CONSISTENT,
    Label.WRONG_REACTION,
    Label.IGNORES_ACTION,
    Label.INVENTS_EFFECT,
    Label.NO_VERDICT,
)


def _logistic(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


# --- 1. partition (P11) -----------------------------------------------------------------------


def _random_case(rng: np.random.Generator) -> dict:
    """Random probe inputs, with boundary values (0, +-eta0, +-eta, s_W = s0) mixed in."""
    eta0 = 0.0 if rng.random() < 0.1 else float(rng.uniform(0.01, 0.2))
    eta = eta0 if rng.random() < 0.2 else eta0 * float(rng.uniform(1.0, 3.0)) + 0.01
    K = int(rng.integers(1, 6))
    boundary = rng.choice(np.array([0.0, eta0, -eta0, eta, -eta]), size=K)
    smooth = rng.normal(0.0, 2.0 * eta + 0.05, size=K)
    tau_s = np.where(rng.random(K) < 0.3, boundary, smooth)
    s0 = float(rng.uniform(0.5, 3.0))
    sigma = 0.0 if rng.random() < 0.05 else float(rng.uniform(0.01, 0.2))
    tau_hat = 0.0 if rng.random() < 0.05 else float(rng.normal(0.0, 3.0 * sigma + 0.01))
    if sigma > 0 and rng.random() < 0.05:
        tau_hat = float(s0 * sigma * rng.choice([-1.0, 1.0]))
    return dict(
        tau_s=tau_s,
        eta0=eta0,
        eta=eta,
        phase_ok=bool(rng.random() < 0.8),
        tau_hat=tau_hat,
        sigma=sigma,
        s0=s0,
    )


def _cells(case: dict) -> dict[str, tuple[bool, Label]]:
    """The six cells of the Step 6.4 table, written directly from Definition 1 and eq. (15)."""
    tau_s, phase_ok = case["tau_s"], case["phase_ok"]
    a = np.abs(tau_s)
    one_sign = bool(np.all(tau_s > 0) or np.all(tau_s < 0))
    sure_effect = phase_ok and one_sign and a.min() > case["eta"]
    sure_none = phase_ok and a.max() < case["eta0"]
    tau_hat, sigma = case["tau_hat"], case["sigma"]
    if sigma > 0:
        s_w = abs(tau_hat) / sigma
    else:
        s_w = math.inf if tau_hat != 0 else 0.0
    sig = s_w >= case["s0"]
    same = np.sign(tau_hat) == np.sign(tau_s[0])
    return {
        "effect, significant, same sign": (sure_effect and sig and same, C),
        "effect, significant, opposite sign": (sure_effect and sig and not same, WR),
        "effect, not significant": (sure_effect and not sig, IG),
        "no effect, significant": (sure_none and sig, INV),
        "no effect, not significant": (sure_none and not sig, C),
        "undecided": (not (sure_effect or sure_none), NV),
    }


def _label_of(case: dict) -> Label:
    dec = twin_decision(case["tau_s"], case["eta0"], case["eta"], case["phase_ok"])
    _, sig = significance(case["tau_hat"], case["sigma"], case["s0"])
    return verdict(dec, sig, int(np.sign(case["tau_hat"])))


def test_every_probe_gets_exactly_one_label():
    rng = np.random.default_rng(0)
    hits = dict.fromkeys(_cells(_random_case(rng)), 0)
    for _ in range(4000):
        case = _random_case(rng)
        cells = _cells(case)
        true_cells = [name for name, (holds, _) in cells.items() if holds]
        assert len(true_cells) == 1, (case, true_cells)
        assert _label_of(case) is cells[true_cells[0]][1]
        hits[true_cells[0]] += 1
    assert min(hits.values()) >= 50, hits  # every cell was exercised, boundaries included


def test_eta_below_eta0_is_rejected():
    rng = np.random.default_rng(1)
    for _ in range(200):
        eta0 = float(rng.uniform(0.01, 1.0))
        eta = eta0 * float(rng.uniform(0.0, 0.999))
        with pytest.raises(ValueError, match="eta"):
            twin_decision(rng.normal(size=3), eta0, eta, True)
    with pytest.raises(ValueError):
        twin_decision(np.array([0.1]), -0.01, 0.1, True)  # eta0 >= 0


def test_label_set_is_the_proposal_s_five_labels():
    assert set(Label) == {C, WR, IG, INV, NV}
    assert set(FAILURE_LABELS) == {WR, IG, INV}


# --- 2. the table, case by case ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("tau_s", "eta0", "eta", "expected"),
    [
        ([0.5, 0.6, 0.31], 0.1, 0.3, "effect+"),
        ([-0.5, -0.31], 0.1, 0.3, "effect-"),
        ([0.5, -0.5], 0.1, 0.3, "undecided"),  # the sign depends on theta
        ([0.5, 0.3], 0.1, 0.3, "undecided"),  # min |tau| > eta is strict
        ([0.5, 0.2], 0.1, 0.3, "undecided"),  # between eta0 and eta
        ([0.05, -0.09, 0.0], 0.1, 0.3, "none"),
        ([0.05, 0.1], 0.1, 0.3, "undecided"),  # max |tau| < eta0 is strict
        ([0.2], 0.2, 0.2, "undecided"),  # eta = eta0: neither strict inequality holds
        ([0.0, 0.0], 0.0, 0.0, "undecided"),  # eta0 = 0: "no effect" is never sure
    ],
)
def test_twin_decision_cases(tau_s, eta0, eta, expected):
    assert twin_decision(np.array(tau_s), eta0, eta, True) == expected


@pytest.mark.parametrize(
    ("twin_dec", "significant", "sign", "expected"),
    [
        ("effect+", True, 1, C),
        ("effect+", True, -1, WR),
        ("effect-", True, -1, C),
        ("effect-", True, 1, WR),
        ("effect+", False, 1, IG),
        ("effect+", False, -1, IG),
        ("effect+", False, 0, IG),
        ("effect-", False, 1, IG),
        ("none", True, 1, INV),
        ("none", True, -1, INV),
        ("none", False, 1, C),
        ("none", False, 0, C),
        ("undecided", True, 1, NV),
        ("undecided", True, -1, NV),
        ("undecided", False, 0, NV),
    ],
)
def test_verdict_table(twin_dec, significant, sign, expected):
    assert verdict(twin_dec, significant, sign) is expected


def test_verdict_rejects_inconsistent_inputs():
    with pytest.raises(ValueError):
        verdict("effect+", True, 0)  # significant needs tau_hat != 0 (s0 > 0)
    with pytest.raises(ValueError):
        verdict("maybe", True, 1)
    with pytest.raises(ValueError):
        verdict("none", True, 2)


# --- 3. outside the twin's phases -------------------------------------------------------------


def test_twin_is_undecided_outside_its_phases():
    rng = np.random.default_rng(2)
    for _ in range(500):
        case = _random_case(rng)
        case["phase_ok"] = False
        assert twin_decision(case["tau_s"], case["eta0"], case["eta"], False) == "undecided"
        assert _label_of(case) is NV
    # Also for inputs that are decisive inside the phases.
    assert twin_decision(np.array([1.0, 2.0]), 0.1, 0.2, True) == "effect+"
    assert twin_decision(np.array([1.0, 2.0]), 0.1, 0.2, False) == "undecided"
    assert twin_decision(np.array([0.0, 0.0]), 0.1, 0.2, True) == "none"
    assert twin_decision(np.array([0.0, 0.0]), 0.1, 0.2, False) == "undecided"


# --- 4. Ctrl-World's estimate (P6) and its sign errors (P9) ----------------------------------


def _common_seed_runs(rng, n_sims, R, tau, sd_d, dist):
    """Scores of a and a~ under R shared seeds: a seed effect common to both runs plus
    independent run noise, so d = Q(a) - Q(a~) has mean tau and std sd_d."""
    seed_effect = rng.normal(0.0, 0.3, size=(n_sims, R))
    if dist == "normal":
        e = rng.normal(0.0, sd_d / math.sqrt(2.0), size=(2, n_sims, R))
    else:  # two-point +-1, bounded like the scores (Lemma 5)
        e = rng.choice([-1.0, 1.0], size=(2, n_sims, R)) * sd_d / math.sqrt(2.0)
    q_a = -1.0 + tau + seed_effect + e[0]
    q_alt = -1.0 + seed_effect + e[1]
    return q_a, q_alt


def test_common_seed_effect_is_the_mean_paired_difference():
    rng = np.random.default_rng(3)
    q_a, q_alt = rng.normal(size=5), rng.normal(size=5)
    assert common_seed_effect(q_a, q_alt) == pytest.approx(np.mean(q_a - q_alt), rel=1e-15)
    with pytest.raises(ValueError):
        common_seed_effect(q_a, q_alt[:-1])
    with pytest.raises(ValueError):
        common_seed_effect(np.array([]), np.array([]))


@pytest.mark.parametrize("dist", ["normal", "two_point"])
def test_estimate_is_unbiased_with_variance_var_d_over_R(dist):
    rng = np.random.default_rng(4)
    n_sims, R, tau, sd_d = 20_000, 4, 0.05, 0.1
    q_a, q_alt = _common_seed_runs(rng, n_sims, R, tau, sd_d, dist)
    est = np.array([common_seed_effect(q_a[s], q_alt[s]) for s in range(n_sims)])
    se = math.sqrt(sd_d**2 / R / n_sims)
    assert abs(est.mean() - tau) < 4 * se  # P6: unbiased
    assert est.var(ddof=1) == pytest.approx(sd_d**2 / R, rel=0.05)  # P6: Var(d) / R


@pytest.mark.parametrize("dist", ["normal", "two_point"])
@pytest.mark.parametrize(("ratio", "R"), [(1.0, 8), (0.5, 16), (2.0, 2), (-1.0, 8)])
def test_sign_error_rate_is_below_the_chebyshev_bound(dist, ratio, R):
    rng = np.random.default_rng(5)
    n_sims, sd_d = 20_000, 0.1
    tau = ratio * sd_d
    bound = sd_d**2 / (R * tau**2)  # P9
    assert bound < 1.0  # a bound that says something
    q_a, q_alt = _common_seed_runs(rng, n_sims, R, tau, sd_d, dist)
    est = np.array([common_seed_effect(q_a[s], q_alt[s]) for s in range(n_sims)])
    rate = np.mean(np.sign(est) != np.sign(tau))
    assert rate <= bound


# --- eq. (15): pooled noise scale and significance --------------------------------------------


def test_pooled_sigma_hand_example():
    q = np.array([[1.0, 3.0], [10.0, 10.0], [-2.0, 0.0]])
    # squares about the row means: 1 + 1, 0 + 0, 1 + 1 -> 4, dof n (R - 1) = 3
    assert pooled_sigma(q) == pytest.approx(math.sqrt(4.0 / 3.0), rel=1e-15)


def test_pooled_sigma_removes_each_candidate_s_mean():
    rng = np.random.default_rng(6)
    q = rng.normal(size=(5, 3))
    shifted = q + rng.normal(size=(5, 1)) * 10.0
    assert pooled_sigma(shifted) == pytest.approx(pooled_sigma(q), rel=1e-12)
    expected = math.sqrt(np.mean(np.var(q, axis=1, ddof=1)))
    assert pooled_sigma(q) == pytest.approx(expected, rel=1e-12)


def test_pooled_variance_is_unbiased_with_n_times_R_minus_one_dof():
    rng = np.random.default_rng(7)
    sd = 0.2
    # R = 2 is the case the proposal relies on ("two seeds per action suffice").
    sims = [pooled_sigma(rng.normal(0.0, sd, size=(6, 2))) ** 2 for _ in range(20_000)]
    se = sd**2 * math.sqrt(2.0 / 6.0) / math.sqrt(len(sims))  # chi^2 with 6 dof
    assert abs(np.mean(sims) - sd**2) < 4 * se


def test_pooled_sigma_validation():
    with pytest.raises(ValueError):
        pooled_sigma(np.ones((3, 1)))  # R >= 2
    with pytest.raises(ValueError):
        pooled_sigma(np.ones(4))
    with pytest.raises(ValueError):
        pooled_sigma(np.empty((0, 3)))
    with pytest.raises(ValueError):
        pooled_sigma(np.array([[0.0, np.nan]]))


def test_significance():
    s_w, sig = significance(-0.3, 0.1, 2.0)
    assert s_w == pytest.approx(3.0) and sig
    s_w, sig = significance(0.1, 0.1, 2.0)
    assert s_w == pytest.approx(1.0) and not sig
    assert significance(0.25, 0.125, 2.0) == (2.0, True)  # s_W = s0 is significant (>=)
    assert significance(0.1, 0.0, 2.0) == (math.inf, True)  # noise-free, non-zero response
    assert significance(0.0, 0.0, 2.0) == (0.0, False)  # noise-free, no response
    for bad in [(0.1, -0.1, 2.0), (0.1, 0.1, 0.0), (np.nan, 0.1, 2.0), (0.1, np.inf, 2.0)]:
        with pytest.raises(ValueError):
            significance(*bad)


# --- probe combination and the null action ----------------------------------------------------


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        ([C], C),
        ([NV], NV),
        ([C, NV], C),
        ([NV, NV, NV], NV),
        ([C, IG], IG),
        ([NV, INV, C], INV),
        ([IG, WR], WR),  # several failures: fixed order WR, INV, IG
        ([IG, INV], INV),
        ([IG, INV, WR, C, NV], WR),
    ],
)
def test_combine_probes_cases(labels, expected):
    assert combine_probes(labels) is expected


def test_combine_probes_rule_and_order_independence():
    for n in range(1, 4):
        for labels in itertools.product(list(Label), repeat=n):
            got = combine_probes(list(labels))
            if any(lab in FAILURE_LABELS for lab in labels):
                assert got in FAILURE_LABELS
                assert got is next(f for f in FAILURE_LABELS if f in labels)
            elif C in labels:
                assert got is C
            else:
                assert got is NV
            for perm in itertools.permutations(labels):
                assert combine_probes(list(perm)) is got
    with pytest.raises(ValueError):
        combine_probes([])  # a candidate without probes is "not probed"


def test_null_action_label():
    # P8: the twin is sure of no effect under the null action, so only Ctrl-World's response
    # decides: significant object motion invents an effect.
    assert null_action_label(0.3, 0.1, 2.0) is INV
    assert null_action_label(0.2, 0.1, 2.0) is INV  # s = s0
    assert null_action_label(0.1, 0.1, 2.0) is C
    assert null_action_label(0.0, 0.1, 2.0) is C
    rng = np.random.default_rng(8)
    for _ in range(200):
        score, sigma, s0 = rng.uniform(0, 1), rng.uniform(0.01, 0.5), rng.uniform(0.5, 3)
        _, sig = significance(score, sigma, s0)
        assert null_action_label(score, sigma, s0) is verdict("none", sig, 1)
    with pytest.raises(ValueError):
        null_action_label(-0.1, 0.1, 2.0)  # a magnitude


# --- 5. probe weight, eq. (19) with the floor at w_min ---------------------------------------


def test_probe_weight_cases():
    kw = dict(s0=2.0, alpha_w=1.5, w_min=0.1)
    assert probe_weight(C, None, probed=True, **kw) == 1.0
    for failure in FAILURE_LABELS:
        assert probe_weight(failure, None, probed=True, **kw) == 0.1
    assert probe_weight(None, None, probed=False, **kw) == 1.0  # the paper's behaviour
    assert probe_weight(NV, 2.0, probed=True, **kw) == pytest.approx(0.5)  # sigma(0)
    s = 2.0 * math.exp(1.0 / 1.5)
    assert probe_weight(NV, s, probed=True, **kw) == pytest.approx(_logistic(1.0), rel=1e-12)
    assert probe_weight(NV, 1e-3, probed=True, **kw) == 0.1  # floor: sigma(...) < w_min
    assert probe_weight(NV, 0.0, probed=True, **kw) == 0.1
    assert probe_weight(NV, math.inf, probed=True, **kw) == 1.0


def test_probe_weight_is_in_w_min_to_one():
    rng = np.random.default_rng(9)
    for _ in range(3000):
        w_min = float(rng.uniform(1e-3, 0.999))
        s0, alpha_w = float(rng.uniform(0.5, 4.0)), float(rng.uniform(0.05, 10.0))
        s_w = float(rng.choice([0.0, math.inf, 10.0 ** rng.uniform(-300, 300)]))
        probed = bool(rng.random() < 0.8)
        label = list(Label)[rng.integers(5)] if probed else None
        p = probe_weight(label, s_w, s0, alpha_w, w_min, probed=probed)
        assert w_min <= p <= 1.0
        if not probed:
            assert p == 1.0


@pytest.mark.parametrize(("alpha_w", "w_min"), [(0.5, 0.05), (1.0, 0.3), (3.0, 0.1), (1.0, 0.7)])
def test_no_verdict_weight_is_monotone_in_s_w(alpha_w, w_min):
    s0 = 2.0
    grid = np.concatenate([[0.0], np.logspace(-8, 8, 400), [math.inf]])
    p = np.array([probe_weight(NV, s, s0, alpha_w, w_min, probed=True) for s in grid])
    assert np.all(np.diff(p) >= 0.0)
    # Strictly increasing between the floor and saturation, and equal to eq. (19) there.
    raw = np.array([_logistic(alpha_w * (math.log(s) - math.log(s0))) for s in grid[1:-1]])
    mid = (raw > w_min) & (raw < 1.0 - 1e-9)
    assert mid.sum() > 50
    assert np.all(np.diff(p[1:-1][mid]) > 0.0)
    np.testing.assert_allclose(p[1:-1][mid], raw[mid], rtol=1e-12)
    assert np.all(p[1:-1][raw <= w_min] == w_min)


def test_probe_weight_validation():
    kw = dict(s0=2.0, alpha_w=1.0, w_min=0.1)
    with pytest.raises(ValueError):
        probe_weight(NV, None, probed=True, **kw)  # no verdict needs s_W
    with pytest.raises(ValueError):
        probe_weight(NV, -1.0, probed=True, **kw)
    with pytest.raises(ValueError):
        probe_weight(NV, math.nan, probed=True, **kw)
    with pytest.raises(ValueError):
        probe_weight(None, None, probed=True, **kw)  # a probed candidate has a label
    with pytest.raises(ValueError):
        probe_weight(C, None, probed=False, **kw)  # an unprobed one has none
    for bad in [dict(w_min=0.0), dict(w_min=1.0), dict(s0=0.0), dict(alpha_w=0.0)]:
        with pytest.raises(ValueError):
            probe_weight(C, None, probed=True, **{**kw, **bad})


# --- candidate pairs (Step 6.2; audit only) ---------------------------------------------------


def test_candidate_pair_deltas():
    rng = np.random.default_rng(10)
    q = rng.uniform(-4.0, 0.0, size=6)
    delta = candidate_pair_deltas(q)
    assert delta.shape == (6, 6)
    for i, m in itertools.product(range(6), repeat=2):
        assert delta[i, m] == q[i] - q[m]
    np.testing.assert_array_equal(delta, -delta.T)
    assert np.all(np.diag(delta) == 0.0)
    # Only score differences matter (as in Lemma 1).
    np.testing.assert_allclose(candidate_pair_deltas(q + 1.7), delta, atol=1e-14)
    with pytest.raises(ValueError):
        candidate_pair_deltas(q[:1])
    with pytest.raises(ValueError):
        candidate_pair_deltas(q.reshape(2, 3))


def test_ranking_agreement():
    rng = np.random.default_rng(11)
    G = 8
    q_s = rng.uniform(-4.0, 0.0, size=G)
    d_s = candidate_pair_deltas(q_s)
    mask = ~np.eye(G, dtype=bool)
    assert ranking_agreement(candidate_pair_deltas(2.0 * q_s - 1.0), d_s, mask) == 1.0
    assert ranking_agreement(candidate_pair_deltas(-q_s), d_s, mask) == 0.0
    # Against a direct count over unordered decisive pairs.
    for _ in range(50):
        d_w = candidate_pair_deltas(rng.uniform(-4.0, 0.0, size=G))
        upper = np.triu(rng.random((G, G)) < 0.4, k=1)
        sym = upper | upper.T
        pairs = [(i, m) for i in range(G) for m in range(i + 1, G) if sym[i, m]]
        expected = np.mean([np.sign(d_w[i, m]) == np.sign(d_s[i, m]) for i, m in pairs])
        assert ranking_agreement(d_w, d_s, sym) == pytest.approx(expected)
    assert math.isnan(ranking_agreement(d_s, d_s, np.zeros((G, G), dtype=bool)))


def test_ranking_agreement_validation():
    G = 4
    d = candidate_pair_deltas(np.arange(G, dtype=float))
    mask = ~np.eye(G, dtype=bool)
    with pytest.raises(ValueError):
        ranking_agreement(d, d, np.triu(mask))  # mask must be symmetric
    with pytest.raises(ValueError):
        ranking_agreement(d, d[:3, :3], mask)
    with pytest.raises(ValueError):
        ranking_agreement(d, d, mask.astype(int))
    with pytest.raises(ValueError):
        ranking_agreement(d, np.zeros((G, G)), mask)  # a decisive pair needs Delta_S != 0
