# D1: which std scales the trust-weighted advantages

Companion to `src/rlinf_modified/algorithms/trust.py` and `tests/test_trust_weighting.py` (WP 1.2, 25 Nov 2026). Equation and proposition numbers refer to the proposal (27 Oct 2026).

Also in the concept book, chapter 05 (`docs/book/chapters/05_trust_weighting.tex`, converted in WP D.2); change both together.

## Setup

Fix one group of $G$ candidates. Weights $w_{i,k}\in(0,1]$. Eq. (20):
$$m_k=\frac{\sum_i w_{i,k}r_{i,k}}{\sum_i w_{i,k}},\qquad \hat r_{i,k}=w_{i,k}r_{i,k}+(1-w_{i,k})\,m_k .$$
Suffix returns $\hat R_{i,k}=\sum_{j\ge k}\gamma^{j-k}\hat r_{i,j}$ and raw returns $R_{i,k}$ (same with $r$). Centred returns $C_{i,k}=\hat R_{i,k}-\frac1G\sum_{i'}\hat R_{i',k}$. "Std" is the unbiased std (as in the code), so $\sum_i C_{i,k}^2=(G-1)\,\mathrm{Std}_i(\hat R_{i,k})^2$.

- **A** (eq. (4), default): $\hat A_{i,k}=C_{i,k}/(\hat s_k+\epsilon)$ with $\hat s_k=\mathrm{Std}_i\hat R_{i,k}$.
- **B** (ablation): $\hat A_{i,k}=C_{i,k}/(s_k+\epsilon)$ with $s_k=\mathrm{Std}_i R_{i,k}$.

One identity is used throughout. By P14 (b), the group mean of $\hat r_{\cdot,k}$ is $m_k$, so
$$\hat r_{i,k}-m_k=w_{i,k}\,(r_{i,k}-m_k).\tag{$*$}$$

## Test 5: Lemma 1 holds after imputation, for A and B

Add $c_j$ to every reward of the group at chunk $j$. Then $m_j\to m_j+c_j$, so $\hat r_{i,j}\to w(r+c_j)+(1-w)(m_j+c_j)=\hat r_{i,j}+c_j$. Every imputed reward moves by the same $c_j$, as do the raw rewards. Every $\hat R_{i,k}$ and every $R_{i,k}$ then moves by the same $\sum_{j\ge k}\gamma^{j-k}c_j$. So $C$, $\hat s_k$ and $s_k$ are unchanged, and so are the advantages under A and under B.

The shift may differ between groups, because everything is computed per group. **Condition:** the done boundaries must be shared within a group (fixed horizon). A member whose episode ended before chunk $j$ would not receive $c_j$. The test uses dones only at the end; whether production dones are always shared within a group is (check).

## Test 6, option A: the total is fixed at $G-1$

$\sum_i \hat A_{i,k}^2=(G-1)\,\hat s_k^2/(\hat s_k+\epsilon)^2=(G-1)\,(1-O(\epsilon/\hat s_k))$, whatever the weights.

Distrust therefore cannot change the total; it only redistributes it. By ($*$), distrusted members' centred rewards shrink toward 0, so the trusted members carry a larger share. If $G_T$ members are trusted and typical, each has $\hat A^2\approx (G-1)/G_T$ instead of $(G-1)/G$: a factor $\sqrt{G/G_T}$, which is 2 for 12 of 16 distrusted.

## Test 6, option B: a fixed scale and a bound at the last chunk

**(i) The scale does not depend on the weights.** $s_k$ is computed from the raw returns, so $\hat A_{i,k}(s_k+\epsilon)=C_{i,k}$ exactly. The weights move the centre and the imputed values, never the scale.

**(ii) At the last chunk, distrust never increases the total.** At $k=N-1$, $C_{i,k}=\hat r_{i,k}-m_k=w_{i,k}(r_{i,k}-m_k)$ by ($*$). Write $\bar r_k$ for the plain mean. Then
$$\sum_i C_{i,k}^2=\sum_i w_i^2(r_i-m)^2\ \le\ \sum_i w_i(r_i-m)^2\ \le\ \sum_i w_i(r_i-\bar r)^2\ \le\ \sum_i (r_i-\bar r)^2=(G-1)s_k^2 .$$
The first and last steps use $w\le1$. The middle step holds because $m$ minimises $\sum_i w_i(r_i-c)^2$ over $c$. Hence $\sum_i\hat A_{i,k}^2\le (G-1)s_k^2/(s_k+\epsilon)^2$, the value at full trust. The same holds at every chunk when $\gamma=0$.

**(iii) At earlier chunks the bound fails.** $C_{i,k}=\sum_{j\ge k}\gamma^{j-k}w_{i,j}(r_{i,j}-m_j)$ (from ($*$), using $\sum_i(\hat r_{i,j}-m_j)=0$). Each chunk's vector shrinks, but cancellation across chunks in the raw returns can be undone.

Example: $G=2$, $r_0=(1,-1)$, $r_1=(-1,1)$, $\gamma=0.95$, $w_1=0.05$ for both members.
- Raw: $C_0=\pm0.05$.
- Imputed: $C_0=\pm0.9525$.
- The total grows about 360 times ($|\hat A|$ goes from 0.71 to 13.5).

## What does not hold: per-member monotonicity

"The trusted members' advantages do not grow when others are distrusted" is false under both policies. Example: $G=16$, rewards eight 0 and eight 10, seven of the zeros distrusted with $w=0.05$. The trusted zero-member's $|\hat A|$ is:

| | Full trust | B | A |
|---|---|---|---|
| trusted zero-member $\lvert\hat A\rvert$ | 0.97 | 1.66 | 3.47 |

Distrust moves $m_k$ toward the trusted majority, so away from a trusted minority member. B keeps the scale, but the centre still moves. The test `test_d1_counterexamples_per_member_growth_and_earlier_chunks` pins this example and the one in (iii).

## Side result: exact neutrality of the advantages holds only under A

With $w_{i,k}=0$, $r_{i,k}$ drops out of $\hat r$ entirely (P14 (c)), so out of $C$ for both policies. Under A it then drops out of the advantages too. Under B it still enters through $s_k$, so changing it rescales the whole group. With $w_{\min}>0$ neither policy is exact.

## Summary

| | A (eq. (4), default) | B (ablation) |
|---|---|---|
| Scale | std of imputed returns, depends on $w$ | std of raw returns, independent of $w$ |
| $\sum_i \hat A^2$ per chunk | $= G-1$ always | $\le$ full-trust value at the last chunk; can grow earlier |
| Effect of heavy distrust | same total update, concentrated on fewer members | smaller total update at the last chunk |
| $w=0$ reward | no effect on the advantages | no effect on $C$; still sets the scale |
| Per member | can grow (e.g. 3.6x above) | can grow (e.g. 1.7x above) |

Interpretation for the optimisation notes (check):
- Under A, the FPO surrogate keeps its overall magnitude whatever the trust. With little trust, the update is driven by a few members, so its variance rises.
- Under B, heavy distrust shrinks the last-chunk advantages, which is more conservative, at the cost of a reward scale that still contains the distrusted rewards.
