"""WP 1.2: trust-weighted rewards and suffix advantages (proposal Step 8.2, eq. (20), P14; D1).

Acceptance (data_free_roadmap.md, WP 1.2), with test 6 for option B replaced by its provable
version (decided 25 Nov, see docs/thesis/notes/d1_scale_policy.md):
1. w = 1: bit-identical to grpo_action_suffix_advantages (both std sources) and equal to the
   cross-rank production formula; weights=None leaves the old path bit-identical.
2-4. P14 (b), (c), (d) (and (a)).
5. Lemma 1 for A and B.
6. A: sum_i A^2 = G - 1. B: the scale does not depend on the weights; at the last chunk the
   advantage energy never grows; the per-member counterexample is pinned.
7. Groups do not interact.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from rlinf_modified.algorithms.advantages import grpo_action_suffix_advantages  # noqa: E402
from rlinf_modified.algorithms.trust import (  # noqa: E402
    _impute,
    _normalise,
    group_members,
    suffix_returns,
    trust_weighted_rewards,
    trust_weighted_suffix_advantages,
)

W_MIN = 0.05
GAMMA = 0.95
SOURCES = ("weighted", "unweighted")


# --- helpers ---------------------------------------------------------------------------------


def _reference_pre_wp12(rewards, loss_mask, dones, *, group_size, gamma):
    """grpo_action_suffix_advantages as of commit 1f954d4 (before WP 1.2), copied verbatim."""
    running = torch.zeros(rewards.shape[1], dtype=rewards.dtype, device=rewards.device)
    suffix_returns = torch.empty_like(rewards)
    for step in reversed(range(rewards.shape[0])):
        continuation = (~dones[step + 1]).to(rewards.dtype)
        running = rewards[step] + float(gamma) * running * continuation
        suffix_returns[step] = running

    num_groups = rewards.shape[1] // group_size
    grouped = suffix_returns.reshape(rewards.shape[0], num_groups, group_size)
    mean = grouped.mean(dim=-1, keepdim=True)
    std = grouped.std(dim=-1, keepdim=True)
    advantages = ((grouped - mean) / (std + 1e-6)).reshape_as(rewards)
    return advantages.float() * loss_mask.to(dtype=torch.float32)


def _batch(seed, *, T=5, n_groups=3, G=8, dtype=torch.float64, random_dones=False):
    """Rewards (negative, as eq. (3)), weights in [W_MIN, 1] with exact 1s and W_MIN, dones,
    loss mask and contiguous group index."""
    g = torch.Generator().manual_seed(seed)
    N = n_groups * G
    rewards = -torch.rand(T, N, generator=g, dtype=torch.float64) * 2.0
    weights = W_MIN + (1.0 - W_MIN) * torch.rand(T, N, generator=g, dtype=torch.float64)
    u = torch.rand(T, N, generator=g)
    weights[u < 0.4] = 1.0
    weights[u > 0.85] = W_MIN
    dones = torch.zeros(T + 1, N, dtype=torch.bool)
    dones[-1] = True
    if random_dones:
        dones[1:-1] = torch.rand(T - 1, N, generator=g) < 0.15
    loss_mask = torch.rand(T, N, generator=g) < 0.9
    group_index = torch.arange(N) // G
    return rewards.to(dtype), weights.to(dtype), dones, loss_mask, group_index


def _numpy_reference(r, w, dones, group_index, gamma, std_source, eps=1e-6):
    """Eq. (20) then eq. (4), written from the proposal with loops in float64 (unmasked)."""
    r, w = np.asarray(r, np.float64), np.asarray(w, np.float64)
    dones, gi = np.asarray(dones), np.asarray(group_index)
    T, N = r.shape
    groups = [np.flatnonzero(gi == b) for b in np.unique(gi)]
    r_hat = r.copy()
    for k in range(T):
        for mem in groups:
            m = (w[k, mem] * r[k, mem]).sum() / w[k, mem].sum()
            r_hat[k, mem] = w[k, mem] * r[k, mem] + (1.0 - w[k, mem]) * m

    def suffix(x):
        out, run = np.zeros_like(x), np.zeros(N)
        for k in reversed(range(T)):
            run = x[k] + gamma * run * (~dones[k + 1])
            out[k] = run
        return out

    R_hat, R_raw = suffix(r_hat), suffix(r)
    A = np.zeros_like(r)
    for mem in groups:
        for k in range(T):
            s = (R_hat if std_source == "weighted" else R_raw)[k, mem].std(ddof=1)
            A[k, mem] = (R_hat[k, mem] - R_hat[k, mem].mean()) / (s + eps)
    return A


def _adv(rewards, weights, dones, group_index, std_source, loss_mask=None):
    if loss_mask is None:
        loss_mask = torch.ones_like(rewards, dtype=torch.bool)
    adv, _ = trust_weighted_suffix_advantages(
        rewards, weights, dones, loss_mask, group_index, gamma=GAMMA, std_source=std_source
    )
    return adv


# --- 1. full trust recovers the existing method bit for bit (P14 a) ---------------------------


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("std_source", SOURCES)
def test_unit_weights_equal_existing_function_bit_for_bit(std_source, dtype):
    for seed in range(5):
        r, _, dones, mask, gi = _batch(seed, dtype=dtype, random_dones=True)
        ones = torch.ones_like(r)
        old = grpo_action_suffix_advantages(r, mask, dones, group_size=8, gamma=GAMMA)
        new, _ = trust_weighted_suffix_advantages(
            r, ones, dones, mask, gi, gamma=GAMMA, std_source=std_source
        )
        via_option = grpo_action_suffix_advantages(
            r, mask, dones, group_size=8, gamma=GAMMA, weights=ones, std_source=std_source
        )
        assert new.dtype == old.dtype == via_option.dtype == torch.float32
        assert torch.equal(new, old)
        assert torch.equal(via_option, old)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_weights_none_keeps_the_old_path_bit_identical(dtype):
    for seed in range(5):
        r, _, dones, mask, _ = _batch(seed, dtype=dtype, random_dones=True)
        expected = _reference_pre_wp12(r, mask, dones, group_size=8, gamma=GAMMA)
        for kwargs in ({}, {"weights": None}, {"weights": None, "std_source": "unweighted"}):
            got = grpo_action_suffix_advantages(r, mask, dones, group_size=8, gamma=GAMMA, **kwargs)
            assert torch.equal(got, expected)


@pytest.mark.parametrize("std_source", SOURCES)
def test_unit_weights_equal_cross_rank_production_formula(std_source):
    cross_rank = pytest.importorskip("rlinf.algorithms.cross_rank_grpo")
    G = 8
    r, _, dones, mask, _ = _batch(7, dtype=torch.float32, random_dones=True)
    N = r.shape[1]
    # Groups spread over the batch as across ranks: a random permutation of the columns, member
    # ids in column order within each group (so both sides sum in the same order).
    perm = torch.randperm(N, generator=torch.Generator().manual_seed(8))
    global_group_id = perm // G
    group_member_id = torch.empty(N, dtype=torch.long)
    for b in range(N // G):
        cols = torch.nonzero(global_group_id == b).flatten()
        group_member_id[cols] = torch.arange(G)
    expected, _ = cross_rank.validate_and_compute_group_suffix_advantages(
        rollout_uid=torch.arange(N),
        global_group_id=global_group_id,
        group_member_id=group_member_id,
        rewards=r,
        dones=dones,
        loss_mask=mask,
        group_size=G,
        gamma=GAMMA,
    )
    got = _adv(r, torch.ones_like(r), dones, global_group_id, std_source, loss_mask=mask)
    assert torch.equal(got, expected)


@pytest.mark.parametrize("std_source", SOURCES)
def test_matches_independent_reference_for_any_weights(std_source):
    for seed in range(5):
        r, w, dones, _, gi = _batch(seed, random_dones=True)
        expected = _numpy_reference(r, w, dones, gi, GAMMA, std_source)
        np.testing.assert_allclose(_adv(r, w, dones, gi, std_source), expected, atol=2e-6)


@pytest.mark.parametrize("std_source", SOURCES)
def test_option_of_the_old_function_equals_the_trust_function(std_source):
    r, w, dones, mask, gi = _batch(9, random_dones=True)
    expected, _ = trust_weighted_suffix_advantages(
        r, w, dones, mask, gi, gamma=GAMMA, std_source=std_source
    )
    got = grpo_action_suffix_advantages(
        r, mask, dones, group_size=8, gamma=GAMMA, weights=w, std_source=std_source
    )
    assert torch.equal(got, expected)


# --- 2-4. neutrality (P14 b, c, d) -----------------------------------------------------------


def test_unit_weights_leave_rewards_unchanged():  # P14 (a)
    r, _, _, _, gi = _batch(0)
    assert torch.equal(trust_weighted_rewards(r, torch.ones_like(r), gi), r)


def test_group_mean_of_imputed_rewards_is_the_trust_weighted_mean():  # P14 (b)
    for seed in range(10):
        r, w, _, _, gi = _batch(seed)
        r_hat = trust_weighted_rewards(r, w, gi, w_min=W_MIN)
        for b in range(int(gi.max()) + 1):
            mem = gi == b
            m = (w[:, mem] * r[:, mem]).sum(1) / w[:, mem].sum(1)
            torch.testing.assert_close(r_hat[:, mem].mean(1), m, rtol=0, atol=1e-12)


def test_zero_weight_reward_does_not_enter_centred_returns():  # P14 (c), test-only w = 0
    r, w, dones, _, gi = _batch(3)
    members = group_members(gi)
    i, k = 5, 2
    w[k, i] = 0.0  # below any w_min: only the private building blocks accept it
    r_changed = r.clone()
    r_changed[k, i] += 100.0

    def centred(rewards):
        R = suffix_returns(_impute(rewards, w, members), dones, GAMMA)
        Rg = R[:, members]
        return Rg - Rg.mean(dim=-1, keepdim=True)

    assert torch.equal(centred(r), centred(r_changed))

    def adv(rewards, std_source):
        r_hat = _impute(rewards, w, members)
        R_hat, R_raw = suffix_returns(r_hat, dones, GAMMA), suffix_returns(rewards, dones, GAMMA)
        return _normalise(R_hat, R_raw, members, std_source, 1e-6)[0]

    # Under A the advantages are unchanged too. Under B the raw reward still sets the scale.
    assert torch.equal(adv(r, "weighted"), adv(r_changed, "weighted"))
    assert not torch.equal(adv(r, "unweighted"), adv(r_changed, "unweighted"))


def test_imputed_rewards_stay_within_the_chunk_range():  # P14 (d)
    for seed in range(20):
        r, w, _, _, gi = _batch(seed)
        r_hat = trust_weighted_rewards(r, w, gi, w_min=W_MIN)
        for b in range(int(gi.max()) + 1):
            mem = gi == b
            lo, hi = r[:, mem].min(1, keepdim=True).values, r[:, mem].max(1, keepdim=True).values
            assert (r_hat[:, mem] >= lo - 1e-15).all() and (r_hat[:, mem] <= hi + 1e-15).all()


# --- 5. Lemma 1 ------------------------------------------------------------------------------


@pytest.mark.parametrize("std_source", SOURCES)
def test_lemma1_shift_per_group_and_chunk_leaves_advantages_unchanged(std_source):
    # Lemma 1 needs the done boundaries shared within a group (fixed horizon): dones only at T.
    for seed in range(5):
        r, w, dones, _, gi = _batch(seed)
        c = torch.randn(
            r.shape[0], int(gi.max()) + 1, generator=torch.Generator().manual_seed(seed)
        )
        shifted = r + 10.0 * c[:, gi]
        a, b = _adv(r, w, dones, gi, std_source), _adv(shifted, w, dones, gi, std_source)
        torch.testing.assert_close(a, b, rtol=0, atol=1e-5)


# --- 6. D1 scale policies --------------------------------------------------------------------


def test_d1_a_squared_advantages_sum_to_g_minus_one_for_any_weights():
    for seed in range(10):
        r, w, dones, _, gi = _batch(seed, random_dones=True)
        a = _adv(r, w, dones, gi, "weighted")
        for b in range(int(gi.max()) + 1):
            mem = gi == b
            torch.testing.assert_close(
                (a[:, mem].double() ** 2).sum(1),
                torch.full((r.shape[0],), 7.0, dtype=torch.float64),
                rtol=1e-4,
                atol=0,
            )


def test_d1_b_scale_does_not_depend_on_the_weights():
    r, w, dones, _, gi = _batch(4, random_dones=True)
    members = group_members(gi)
    R_raw = suffix_returns(r, dones, GAMMA)
    scale = R_raw[:, members].std(dim=-1) + 1e-6  # [T, groups], computed without weights
    for weights in (w, torch.ones_like(w), torch.full_like(w, W_MIN), w.flip(0)):
        R_hat = suffix_returns(trust_weighted_rewards(r, weights, gi, w_min=W_MIN), dones, GAMMA)
        centred = R_hat[:, members] - R_hat[:, members].mean(dim=-1, keepdim=True)
        a = _adv(r, weights, dones, gi, "unweighted")
        torch.testing.assert_close(
            a[:, members].double() * scale[..., None], centred, rtol=1e-6, atol=1e-6
        )


def test_d1_b_last_chunk_advantage_energy_never_grows():
    for seed in range(50):
        r, w, dones, _, gi = _batch(seed)
        a_raw = _adv(r, torch.ones_like(r), dones, gi, "unweighted")[-1].double()
        a_b = _adv(r, w, dones, gi, "unweighted")[-1].double()
        for b in range(int(gi.max()) + 1):
            mem = gi == b
            assert (a_b[mem] ** 2).sum() <= (a_raw[mem] ** 2).sum() * (1 + 1e-6)


def test_d1_counterexamples_per_member_growth_and_earlier_chunks():
    # Pinned so that nobody relies on "trusted advantages do not grow" (not true under A or B).
    r = torch.tensor([[0.0] * 8 + [10.0] * 8], dtype=torch.float64)
    w = torch.ones_like(r)
    w[0, 1:8] = W_MIN  # distrust seven of the eight zeros
    dones = torch.zeros(2, 16, dtype=torch.bool)
    gi = torch.zeros(16, dtype=torch.long)
    a_raw = _adv(r, torch.ones_like(r), dones, gi, "unweighted")[0, 0].abs()
    a_b = _adv(r, w, dones, gi, "unweighted")[0, 0].abs()
    a_a = _adv(r, w, dones, gi, "weighted")[0, 0].abs()
    assert a_raw < a_b < a_a  # 0.97 < 1.66 < 3.47
    # Earlier chunks: through the discounted suffix even B's total energy can grow.
    r2 = torch.tensor([[1.0, -1.0], [-1.0, 1.0]], dtype=torch.float64)
    w2 = torch.tensor([[1.0, 1.0], [W_MIN, W_MIN]], dtype=torch.float64)
    d2 = torch.zeros(3, 2, dtype=torch.bool)
    gi2 = torch.zeros(2, dtype=torch.long)
    e_raw = (_adv(r2, torch.ones_like(r2), d2, gi2, "unweighted")[0] ** 2).sum()
    e_b = (_adv(r2, w2, d2, gi2, "unweighted")[0] ** 2).sum()
    assert e_b > 100 * e_raw


# --- 7. groups do not interact ---------------------------------------------------------------


@pytest.mark.parametrize("std_source", SOURCES)
def test_weights_in_one_group_do_not_change_another_group(std_source):
    r, w, dones, _, gi = _batch(5, random_dones=True)
    w2 = w.clone()
    w2[:, gi == 0] = W_MIN
    a, b = _adv(r, w, dones, gi, std_source), _adv(r, w2, dones, gi, std_source)
    assert torch.equal(a[:, gi != 0], b[:, gi != 0])
    assert not torch.equal(a[:, gi == 0], b[:, gi == 0])


@pytest.mark.parametrize("std_source", SOURCES)
def test_explicit_group_index_is_permutation_equivariant(std_source):
    r, w, dones, _, gi = _batch(6, random_dones=True)
    perm = torch.randperm(r.shape[1], generator=torch.Generator().manual_seed(6))
    a = _adv(r, w, dones, gi, std_source)
    b = _adv(r[:, perm], w[:, perm], dones[:, perm], gi[perm], std_source)
    torch.testing.assert_close(b, a[:, perm], rtol=0, atol=1e-6)


# --- validation and stats --------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    ["zero", "above_one", "nan", "below_w_min", "shape", "bad_w_min", "std_source"],
)
def test_invalid_weights_and_options_are_rejected(case):
    r, w, dones, mask, gi = _batch(0)
    kwargs = {"gamma": GAMMA, "std_source": "weighted", "w_min": W_MIN}
    if case == "zero":
        w[0, 0] = 0.0
        kwargs["w_min"] = None
    elif case == "above_one":
        w[0, 0] = 1.0 + 1e-9
    elif case == "nan":
        w[0, 0] = float("nan")
    elif case == "below_w_min":
        w[0, 0] = W_MIN / 2
    elif case == "shape":
        w = w[:, :-1]
    elif case == "bad_w_min":
        kwargs["w_min"] = 0.0
    elif case == "std_source":
        kwargs["std_source"] = "biased"
    with pytest.raises(ValueError):
        trust_weighted_suffix_advantages(r, w, dones, mask, gi, **kwargs)


@pytest.mark.parametrize("sizes", [[8, 7], [8, 1]])
def test_groups_must_have_equal_size_of_at_least_two(sizes):
    gi = torch.cat([torch.full((n,), b) for b, n in enumerate(sizes)])
    with pytest.raises(ValueError):
        group_members(gi)


def test_std_source_is_validated_on_the_old_path_too():
    r, _, dones, mask, _ = _batch(0)
    with pytest.raises(ValueError):
        grpo_action_suffix_advantages(r, mask, dones, group_size=8, gamma=GAMMA, std_source="x")


def test_stats():
    r, w, dones, mask, gi = _batch(2, random_dones=True)
    adv, stats = trust_weighted_suffix_advantages(
        r, w, dones, mask, gi, gamma=GAMMA, std_source="weighted"
    )
    valid = mask
    assert stats.weight_below_one_share == pytest.approx(float((w[valid] < 1).double().mean()))
    assert stats.weight_mean == pytest.approx(float(w[valid].mean()))
    assert stats.adv_abs_max == pytest.approx(float(adv.abs().max()))
    members = group_members(gi)
    R_hat = suffix_returns(trust_weighted_rewards(r, w, gi), dones, GAMMA)
    R_raw = suffix_returns(r, dones, GAMMA)
    torch.testing.assert_close(
        stats.std_ratio, R_hat[:, members].std(-1) / R_raw[:, members].std(-1)
    )
    _, ones_stats = trust_weighted_suffix_advantages(
        r, torch.ones_like(w), dones, mask, gi, gamma=GAMMA, std_source="weighted"
    )
    assert ones_stats.weight_below_one_share == 0.0 and ones_stats.weight_mean == 1.0
    torch.testing.assert_close(ones_stats.std_ratio, torch.ones(r.shape[0], 3, dtype=r.dtype))
