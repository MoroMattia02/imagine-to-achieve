# Data-free roadmap: what to build before the lab data arrives
 
Written 25 Nov 2026 against branch `twin`, commit `f4f669e` (17 Nov). The code was read here, not run. Anything not verified by running it is marked **(check)**. Durations are estimates.
 
**Reference: the official plan is the final proposal, `thesis_proposal_final.pdf` (27 Oct 2026).** This roadmap only orders and details its work; where they differ, the proposal wins (§0.1 lists the deliberate deviations). Lemma, proposition and assumption numbers below are those of the compiled PDF:
- L1 only within-group differences matter; L2 zero advantage, zero push; L5 everything is bounded;
- P3 the fit is well posed; P4 properties of $\tilde D$; P6 identification by intervention; P7 small probes exist; P8 the null verdict needs no physics; P9 sign errors; P10 soundness of decisive verdicts; P11 labels are a partition; P12 controlled false alarms; P13 detection; P14 trust weighting is safe and neutral;
- M1 model adequacy, M2 coverage, M3 controller fidelity, M4 exact restore, M5 representation validity, M6 support, M7 exchangeability.
Companions: `thesis_context.md` (short version of the proposal), `twin_implementation_plan.md` (milestones T0-T8, decisions D1-D4), `twin_detailed_guide.md` (theory per component), `progress.md` (what is done).
 
---
 
## 0. How to use this file with Claude Code
 
- **One work package (WP) per session.** Every WP below has a goal, files, acceptance tests and a ready prompt. Do not hand Claude Code more than one WP at a time.
- **Order:** Phase 1 first (§2). Its WPs are small, need no GPU and no data, and every later phase uses them. Within each later phase, the WPs are mostly independent.
- **Rules already in `CLAUDE.md` still apply:** write the test first; mark unverified statements with (check); small commits on `twin`; no push; no new dependencies without asking; no cluster jobs.
- **After each WP:** Claude Code updates `docs/thesis/progress.md` (Done / Decisions / Open problems / Exact next step). You review the diff and the test output, then push.
- Add one line to `CLAUDE.md` under *Goal*: "Data-free roadmap and the current WP: `docs/thesis/data_free_roadmap.md`."
Generic prompt frame (fill in the WP id):
 
> Read `CLAUDE.md`, `docs/thesis/progress.md` and the section for WP **X.Y** in `docs/thesis/data_free_roadmap.md`, plus the guide or proposal sections it cites. Implement only WP X.Y. Start with the tests listed under *Acceptance*, show me that they fail, then implement until they pass. Run the full twin test subset (`python -m pytest tests/test_twin_*.py -q`) and paste the output. Then update `progress.md` and make one commit. Do not touch other WPs, vendored files or dependencies. If something in the WP is wrong or ambiguous, stop and ask.
 
### 0.1 Check against the proposal (done 25 Nov)
 
**Deliberate deviations (keep them, and mention them in the thesis):**
- **Robot model.** The proposal says UR5e from MuJoCo Menagerie, "adapted if the lab robot is the older UR5". The code uses the original UR5, generated from the DH constants in `eef_pose_adapter.py`, because those produced Ctrl-World's conditioning states. This is the adaptation the proposal allows for.
- **D1 scale policy.** The proposal's eq. (4) divides by the std of the trust-weighted returns (option A). Option B (unweighted std) is an extra ablation from the implementation plan, not part of the proposal.
- **WP 2.1, toy sandbox.** Not in the proposal. It is a cheap check of Step 8 and the E3 arms. Treat it as optional and timebox it (≤ 2 days); it must not delay proposal work.
**Proposal content that the first version of this roadmap had missed, now added:**
- the four-task initialiser (Step 2.0 and validation (iii), G1): WP 3.2;
- probe directions chosen with the twin, the table-collision part of $\mathcal A_{\text{feas}}$, and logging when no probe exists (Step 6.2): WP 2.2;
- candidate pairs $\Delta^M_{im}$ (Step 6.2, E1): WP 1.4;
- threshold rules $\eta_0$, $\eta=2\eta_0$, $s_0=2$, $m_k$ and the 20/20 split (Steps 5.3, 7.3): WP 1.5;
- the soft grounded term (Step 8.1 ablation): WP 1.5;
- controller *gains* as well as delay (Step 3, M3): WP 3.4;
- the silhouette fallback comparison (Step 4 remark): WP 4.3;
- arms T0, TG and S (E3): WP 5.1;
- Step 9 diagnostics and the E1/E2 analysis (Mann-Kendall, lagged cross-correlation): new WP 5.3;
- E4 robot protocol and scripts: Phase 7.
**Schedule against the proposal's work plan (§13).**
- *15 Oct - 4 Nov* (reduced cluster run with full logging; data check): **not met.** The data is missing, so neither the run nor the data check can be done.
- *5 Nov - 2 Dec* (general twin, initialiser, rendering, V-JEPA comparison, Ctrl-World save/restore; checkpoint "G1 initialiser validated on four tasks"): the code can be done by 2 Dec; the four-task validation cannot happen without the first frames.
- So the slip is not caused by the code. Tell Sichao with a concrete proposal: the code ready by about 6 Dec, validation within a week of the data arriving.
- To stay as close as possible to this block, WP 4.1 (save/restore) and WP 4.2 (V-JEPA) are scheduled straight after Phase 1, not after Phase 3 (§1).
### 0.2 Traceability: proposal → work packages
 
| Proposal item | WP | Needs data? |
|---|---|---|
| Step 1 general twin | done (T1, T2) + 2.3 | dimensions, gripper (lab) |
| Step 2 initialiser (2.0-2.4, validation i-iii) | 3.1, 3.2, 4.3 | first frames of 4 tasks |
| Step 3 same actions, controller, rendering, rest check | done (T2) + 2.3, 3.1, 3.4 | demos for lag and gains |
| Step 4 V-JEPA change features, $\tilde D$, scores $Q^M$ (P4, L5) | 1.3, 4.2 | no (real clips for 5.4) |
| Step 5 calibration (5.1-5.4) | 1.5 (rules), 3.4 (method), 4.2 (5.4) | yes, demos |
| Step 6 probes, null action, verdicts (P6-P11) | 1.4, 2.2, 4.1 | no, except $\mathcal A_{\text{demo}}$ statistics |
| Step 7 grounded divergence, conformal (P12, P13) | 1.3, 1.5 | calibration scores from demos |
| Step 8 trust weights, imputation (P14) | 1.2, 5.1 | no |
| Step 9 diagnostics | 5.3 | no for the code |
| E0 referee validation | 3.2, 4.1, 4.2, Phase 6 | yes |
| E1, E2 audit and dynamics | 5.2, 5.3 | arm A run |
| E3 arms A, T, T0, TG, S | 5.1 | cluster runs |
| E4 robot demonstrations | Phase 7 | robot (from 25 Jan) |
 
---
 
## 1. Overview
 
| Phase | WPs | Needs | Roadmap item | Unblocks |
|---|---|---|---|---|
| **1 Foundations (do first)** | 1.1 housekeeping + viewer, 1.2 trust-weighted advantages, 1.3 comparison distance, 1.4 chunk-0 verdicts, 1.5 conformal divergence | CPU | items 1, 3, 7 (partial) | everything in-loop; your FPO maths study |
| **2 Mechanisms** | 2.1 toy exploitation sandbox, 2.2 probe generator + null action, 2.3 laptop scene with placeholder geometry (T3) | CPU | items 2, 4, 7 | RQ3 design choices; Step 6 probes; all twin physics |
| **3 Twin on synthetic ground truth** | 3.1 cameras + masks (T4), 3.2 initialiser fit (T5 logic), 3.3 extrinsics from robot silhouettes, 3.4 physics identifiability and controller lag | CPU | twin completion | T5, Step 5.1 the day data arrives |
| **4 GPU-side tools** | 4.1 Ctrl-World save/restore + probe re-run (M4), 4.2 V-JEPA 2 encoder + representation check, 4.3 SAM 3 smoke test | lab GPU, checkpoints | items 3, 6, 7 | Step 4, Step 6, E0 |
| **5 Integration and analysis** | 5.1 `twin_plugin` with arm modes, 5.2 Phase-A rollout dump, 5.3 Step 9 diagnostics and E1/E2 analysis | CPU tests; cluster later | item 5 | arm A with a full audit log (E1, E2); arms of E3 |
| **6 When data arrives** | checklist, not WPs | dataset, lab answers | n/a | T2 demo check, T5, T6, Step 5 |
| **7 Robot preparation** | protocol and scripts for E4 | nothing until the dry run | n/a | E4 (dry run by 24 Jan, per the proposal) |
 
**Suggested calendar (estimate), ordered to follow the proposal's 5 Nov - 2 Dec block first:**
 
| Dates | Work |
|---|---|
| 25-28 Nov | Phase 1 (≈ 1 WP per half day to day), in parallel with the end of your optimisation study |
| 29 Nov - 3 Dec | WP 4.1 Ctrl-World save/restore and WP 4.2 V-JEPA (both in the proposal's current block; GPU, no lab data); WP 2.2 probes |
| 4-10 Dec | WP 2.3 scene (T3), Phase 3 (cameras, initialiser with four-task config, identifiability), WP 4.3 SAM 3 |
| 11-18 Dec | Phase 5; WP 2.1 toy sandbox only if time is left (optional, ≤ 2 days) |
| from the data | Phase 6 takes priority over everything unfinished |
| early-mid Jan | Phase 7 robot protocol and scripts, ready for the dry run in 14-24 Jan |
 
The proposal schedules calibration for 3-16 Dec and arm A (with the audit) from 17 Dec. Both need the data. Each week of delay in the data shifts them by about a week, while the code above keeps progressing. Raise this with Sichao now.
 
---
 
## 2. Phase 1: foundations (implement first)
 
### WP 1.1 Housekeeping, T0 render, viewer script (≈ half a day)
 
**Goal.** A clean test baseline on both machines, the T0 render test, and a way to look at the twin.
 
**Tasks.**
1. Fix the Linux/Windows 1-ulp mismatch in `ur5_mjcf_xml()` (`src/twin/robot.py`): write `alpha = ±π/2` rotations with exact `sqrt(0.5)` instead of `math.sin(pi/4)`. Regenerate `src/twin/assets/ur5.xml`. Both asset tests must pass on Linux and Windows.
2. T0 as described in `progress.md` ("T0 steps"): `tests/test_twin_render.py` first. Implement `TwinRenderer.render` in `src/twin/render.py`: off-screen `mujoco.Renderer`, 192x320, named camera. Time 100 frames and record ms/frame in `progress.md`.
3. `scripts/twin_view.py`, interactive viewer (see §8):
   - `--model ur5` opens the arm in `mujoco.viewer.launch_passive`;
   - `--replay <npz or json of q(t)>` plays a joint trajectory;
   - `--demo-chunk` builds a smooth synthetic action chunk, converts it with `ActionsToJoints` and plays the result.
   No new dependency: the viewer ships with the `mujoco` package (check for 4.0.1).
**Acceptance.** All existing twin tests pass on Linux. `test_twin_render.py` checks shape (192, 320, 3), that the frame is not one colour, and that two renders of the same state are identical. The viewer script runs on the Windows laptop (it is interactive, so there is no automated test; run it by hand).
 
**Prompt.** Generic frame, WP 1.1. Add: "The viewer script is for my Windows laptop; the lab PC is reached over SSH and has no display."
 
---
 
### WP 1.2 Trust-weighted advantages (Step 8, milestone T8, decision D1) (≈ 1 day)
 
**Goal.** The FPO-side change of the thesis as a pure, tested function, with both scale policies of D1.
 
**Background in one paragraph.** At chunk $k$ of group $b$, rewards $r_{i,k}$ get weights $w_{i,k}\in[w_{\min},1]$. The trust-weighted mean is $m_k=\sum_i w_{i,k} r_{i,k} / \sum_i w_{i,k}$ and the imputed reward is $\hat r_{i,k}=w_{i,k} r_{i,k}+(1-w_{i,k}) m_k$. Suffix returns and group normalisation are then computed on $\hat r$. D1 decides which std divides the centred returns:
- **A:** the std of the imputed returns, as in the proposal. The sum of squared advantages per group and chunk stays $G-1$. Distrusting many rewards therefore *enlarges* the advantages of the trusted ones (12 of 16 distrusted at the last chunk gives about 2x).
- **B:** the std of the unweighted returns. Distrusted rewards are removed without rescaling the rest.
**Files.**
- New `src/rlinf_modified/algorithms/trust.py`:
  - `trust_weighted_rewards(rewards[T,N], weights[T,N], group_index[N]) -> rewards_hat[T,N]`
  - `trust_weighted_suffix_advantages(rewards, weights, dones, loss_mask, group_index, *, gamma, std_source: Literal["weighted","unweighted"], epsilon=1e-6) -> (advantages, stats)`. The stats include the share of weights below 1, the mean weight, the per-group std ratio (weighted / unweighted) and the max |advantage|.
  - Validation: weights finite and in $[w_{\min},1]$ with $w_{\min}>0$ (so $\sum_i w>0$); shapes as in `grpo_action_suffix_advantages`.
- `src/rlinf_modified/algorithms/advantages.py`: optional `weights=None, std_source="weighted"`. With `weights=None` the old code path must be untouched.
- Do **not** edit `cross_rank_grpo.py`. The production wrapper comes in WP 5.1. Write the group logic so it can take explicit `group_index` (production groups span ranks and are identified by `global_group_id` and `group_member_id`).
**Acceptance (tests in `tests/test_trust_weighting.py`).**
1. $w\equiv 1$: output equals `grpo_action_suffix_advantages` bit for bit, for both `std_source` values. Also equal to the formula in `validate_and_compute_group_suffix_advantages` (call it with synthetic metadata; skip if `rlinf` does not import).
2. Neutrality, part (b): $\frac1G\sum_i \hat r_{i,k} = m_k$ (to 1e-6).
3. Neutrality, part (c): with $w_{i,k}=0$ (test-only path that bypasses the $w_{\min}$ check), the centred contribution of $r_{i,k}$ is exactly zero. Equivalently, changing that $r_{i,k}$ leaves all centred returns unchanged.
4. Neutrality, part (d): $\min_j r_{j,k} \le \hat r_{i,k} \le \max_j r_{j,k}$.
5. Lemma 1 (only within-group differences matter): adding $c_k$ to all rewards of a chunk leaves advantages unchanged, for A and B.
6. D1-A: $\sum_i \hat A_{i,k}^2 = G-1$ per group and chunk (up to epsilon effects), whatever the weights. D1-B: the trusted members' advantages do not grow when other members are distrusted.
7. Mixed groups: weights in one group do not change another group's advantages.
**Prompt.** Generic frame, WP 1.2. Add: "Also write a short note `docs/thesis/notes/d1_scale_policy.md` deriving tests 5 and 6 in a few lines; I will use it in my optimisation notes."
 
---
 
### WP 1.3 Change features and the distance $\tilde D$ (Step 4, maths only) (≈ half a day)
 
**Goal.** The comparison, written on feature arrays, independent of which encoder produces them.
 
**Files.** New `src/twin/compare.py`:
- `change_features(phi[Tw,d], phi_ref[d]) -> c[Tw,d]`. The inputs must be unit-normalised; assert it.
- `d_tilde(c_x[Tw,d], c_y[Tw,d], window_index) -> float`, the average distance over the windows of chunk $k$.
- `grounded_scores(c_w[Tw,d], c_s[K,Tw,d], window_index) -> (S, kappa)` with $S=\min_\vartheta d$ and $\kappa=\max_{\vartheta,\vartheta'}$ (Step 7.2).
- `average_views(per_view: dict[str, array]) -> array`. Same preprocessing for every view; keyed by physical camera name (`d405_0_rgb`, `d435_rgb`, `d405_1_rgb`).
**Acceptance (`tests/test_twin_compare.py`, random unit vectors).** Pseudometric (symmetry, triangle inequality, $\tilde D(X,X)=0$); $\tilde D\le 4$; a constant offset $b$ on $\phi_t$ and $\phi_{\text{ref}}$ gives $\tilde D=0$; $S\le d(\vartheta)$ for all $\vartheta$; $\kappa=0$ when all twin samples coincide.
 
---
 
### WP 1.4 Chunk-0 verdict logic (Step 6.3-6.4) (≈ 1 day)
 
**Goal.** Everything that turns probe scores into a label and a weight $p_{i,0}$.
 
**Files.** New `src/twin/verdict.py`:
- `class Label(Enum)`: CONSISTENT, WRONG_REACTION, IGNORES_ACTION, INVENTS_EFFECT, NO_VERDICT.
- `twin_decision(tau_s[K], eta0, eta, phase_ok) -> {"effect+","effect-","none","undecided"}`.
- `pooled_sigma(q_w[n,R]) -> float` with $n(R-1)$ degrees of freedom; `significance(tau_hat, sigma, s0) -> (s_w, bool)`.
- `verdict(twin_dec, w_significant, sign_tau_w) -> Label` (the proposal's table).
- `combine_probes(labels) -> Label` (any failure, then any consistent, then no verdict).
- `probe_weight(label, s_w, s0, alpha_w, w_min, probed: bool) -> float` (the $p_{i,0}$ cases).
- `null_action_label(object_motion_score, sigma, s0) -> Label`.
- `candidate_pair_deltas(q[G]) -> Delta[G,G]` and `ranking_agreement(Delta_W, Delta_S, decisive_mask) -> float`: the candidate pairs $\Delta^M_{im}=Q^M(V^C_i,a_i)-Q^M(V^C_m,a_m)$ of Step 6.2. They are used in the audit (E1, ranking agreement on decisive pairs), never for a per-action verdict.
**Acceptance (`tests/test_twin_verdict.py`).**
1. Partition: for a few thousand random inputs, every input gets exactly one label, and $\eta\ge\eta_0$ is enforced.
2. The table, case by case, against hand-written expectations.
3. Outside phases where the twin beats Ctrl-World, the twin is always undecided.
4. Sign errors: on simulated $d\sim\mathcal N(\tau,\sigma^2)$, the empirical sign-error rate of $\hat\tau^W$ is at most $\sigma^2/(R\tau^2)$ (Chebyshev bound).
5. `probe_weight`: in $[w_{\min},1]$; equals 1 when not probed (the paper's behaviour); monotone in $s^W$ in the no-verdict case.
---
 
### WP 1.5 Conformal threshold and divergence chunk (Step 7) (≈ half a day)
 
*Split conformal* (already in the proposal): the threshold is an order statistic of calibration scores, which bounds the false-alarm rate whenever the new score is exchangeable with them.
 
**Files.** New `src/twin/conformal.py`:
- `conformal_threshold(T_scores[n], alpha) -> float`: the $\lceil(n+1)(1-\alpha)\rceil$-th smallest. Raise if $n$ is too small; for $\alpha=0.1$ that means $n<9$.
- `trajectory_score(S[N], m[N], abstain[N]) -> float`: $\max_k S_k/m_k$ over the chunks that do not abstain.
- `divergence_chunk(S[N], m[N], kappa[N], kappa_max, phase_ok[N], q_alpha) -> int | None`.
- `grounded_weights(k_star, N, w_min, *, soft=False, S=None, m=None, scale=None) -> g[N]`. With `soft=True`, $g$ decays with $S_{i,k}/m_k$ instead of stepping down (the Step 8.1 ablation).
- Calibration rules as functions, so the numbers in Step 5 cannot drift:
  - `split_fit_calibration(episode_ids, seed) -> (fit_ids, calib_ids)`, the 20/20 split of the 40 demonstrations (Step 5);
  - `per_chunk_scale(S_fit[n,N]) -> m[N]`, the median calibration score per chunk, computed on the **fitting** half (Step 7.3);
  - `appearance_floor(delta_q_s_appearance) -> (eta0, eta)`, with $\eta_0$ the 95th percentile of $|\Delta Q^S|$ under appearance-only changes and $\eta=2\eta_0$ (Step 5.3);
  - default $s_0=2$ (Step 5.3) and $\alpha=0.1$ (Step 7.4), as config values.
**Acceptance (`tests/test_twin_conformal.py`).**
1. Coverage: over 20,000 simulated calibration sets of 20 continuous exchangeable scores, the flag rate on a fresh score is $\le\alpha$ and $\ge \alpha - 1/(n+1)$ (tolerance from the binomial standard error).
2. Abstaining chunks never flag.
3. `grounded_weights` equals 1 before $k^\*$ and $w_{\min}$ from $k^\*$ on.
4. The combined weight $w=p\cdot g$ stays in $[w_{\min}^2,1]$. The proposal only requires $w\in[0,1]$ with $w_{\min}>0$ (eq. 18), so the product is allowed. Note in `progress.md` that it can go below $w_{\min}$, and ask whether to clip.
5. `per_chunk_scale` uses only the fitting half; the threshold $q_\alpha$ only the calibration half (a test with disjoint ids).
---
 
## 3. Phase 2: mechanisms
 
### WP 2.1 Toy exploitation sandbox (optional, not in the proposal; CPU, ≤ 2 days)
 
**Goal.** A cheap model of "policy trained against a wrong world model", to test trust weighting and its design choices before any GPU run. It is the empirical counterpart of your maths study.
 
**Design.**
- **Environment:** a 2-D point, $N=5$ chunks, $s_{k+1}=s_k+a_k$, start $s_0$ fixed per group. True reward $r^\*_k=-\lVert s_{k+1}-s^\star\rVert^2$, plus a goal term at the last chunk.
- **World model:** identical, except in a trap region $\mathcal R$. There it "invents" progress: the predicted state jumps toward the goal by a factor $\beta$. This is an optimistic error the policy can exploit.
- **Policy:** Gaussian with learnable mean network or linear map and log-std. Groups of $G=16$, PPO-clip update. The ratio $\rho$ is the exact likelihood ratio here, where FPO uses its flow-matching surrogate. That difference is stated in the README; the advantage path is the real one from WP 1.2.
- **Referee:** simulated grounded divergence. When the WM state leaves the true state by more than $\delta$ at chunk $k$, the referee flags with probability TPR, and it raises false flags with probability FPR elsewhere. *(New terms: TPR, the true-positive rate, is the share of real divergences it detects; FPR, the false-positive rate, is the share of correct chunks it wrongly flags.)* Distrust then propagates from $k^\*$ on, as in Step 7.
- **Arms:** A ($w\equiv1$), T (referee), S (T's weights shuffled within the batch), O (oracle: TPR=1, FPR=0). D1-A and D1-B are a factor on T and O.
- **Sweeps:** $w_{\min}\in\{0,0.1,0.3\}$; TPR, FPR on a grid; $\beta$; 5 seeds each.
**Files.** `analysis/toy_exploitation/{env.py, run.py, plot.py, README.md}`. It imports `trust_weighted_suffix_advantages` from WP 1.2. Output goes to `metrics.jsonl` and figures. For plotting, use matplotlib only if it is already installed; otherwise ask.
 
**Acceptance.**
1. Arm A shows exploitation: the imagined return keeps rising while the true return peaks and then falls, or the share of rollouts ending in $\mathcal R$ grows over updates.
2. Arm O removes the gap.
3. Arm S behaves like A, not like T.
4. One figure per sweep: true return at the end vs FPR at fixed TPR, for D1-A vs D1-B.
**Caveat to write in the README.** The toy reproduces the gap between imagined and true return. The paper's decline is in *model-space* success (a classifier on generated videos), so the toy does not by itself explain that decline.
 
---
 
### WP 2.2 Probe generator and null action (Step 6.2) (≈ 1 day)
 
**Goal.** Executable probes $\tilde a=a+\varepsilon Bc$ and the null action, using T2 for feasibility.
 
**Subtleties to handle (check each in the code).**
- **Translation frame.** The 10-D action is chained with a configurable `translation_frame` (`_convert_via_analytic_ur5_rot6d` passes `self.adapter_translation_frame`; the close config is body-frame per `CLAUDE.md`, check). A displacement pattern defined on the EEF path in frame W must be mapped back into per-step deltas: $\Delta p^{\text{body}}_t = R_t^\top\big((p_{t+1}+\delta_{t+1})-(p_t+\delta_t)\big)$ with the unchanged rotation path $R_t$. Do not invert rot6d by hand; rotations are unchanged by the probe.
- **Units and normalisation.** Check whether `chunk_step` receives raw or normalised actions, and the units of `pos_delta` (m?). Read it in the code and record it in `progress.md`.
- **Absolute gripper.** The null action repeats the *current* absolute gripper value; it does not set 0.
**Files.** New `src/twin/probes.py`:
- `smooth_basis(H=32, n_basis=3) -> B[H, n_basis]`: low-order cosine bumps with zero displacement at $t=0$, scaled so that the max displacement is 1. *(New notation: $B$ maps a small coefficient vector $c$ to a displacement path over the 32 steps.)*
- `make_probe(actions[32,10], eef_state0, B, c[3*n_basis], eps_m) -> actions_tilde`;
- `null_action(eef_state0, gripper_now) -> actions[32,10]`;
- `probe_feasible(actions_tilde, a2j, q0, scene=None) -> (bool, reasons)`, wrapping the `ActionsToJoints` flags (reachable, within limits). Once WP 2.3 exists, pass `scene` to add the third condition of $\mathcal A_{\text{feas}}$ in Step 6.2: **no table collision**.
- `in_demo_range(actions_tilde, stats) -> bool`, a placeholder that takes per-channel q01/q99 once the demo action statistics exist (check).
- `select_directions(a, twin_effect_fn, candidates) -> (c_effect, c_none)`. Step 6.2 chooses two directions with the twin: one where it predicts a large effect, one where it predicts none. With `twin_effect_fn` as a stub until WP 2.3, test the selection logic on a fake effect function.
- When $a$ is on the boundary of, or outside, $\mathcal A_{\text{feas}}\cap\mathcal A_{\text{demo}}$, no probe is generated and a reason code is returned for logging (Step 6.2: "this is itself logged").
**Acceptance (`tests/test_twin_probes.py`).**
1. Round trip: converting $\tilde a$ with the repo function gives the original EEF path plus $\varepsilon B c$ in W (≤ 1e-6 m), with an unchanged rotation path and gripper.
2. The max displacement equals $\varepsilon$.
3. The null action converts to a constant EEF state.
4. $\varepsilon\to0$ gives $\tilde a\to a$.
5. A probe pushing the TCP outside reach is reported infeasible.
6. Proposition 7 (small probes exist): for an action well inside the feasible set, a probe is feasible for every unit $c$ once $\varepsilon$ is small enough. Test it with a decreasing sequence of $\varepsilon$.
7. `select_directions` picks the largest- and smallest-effect directions of the fake effect function; an out-of-range action returns no probe and a reason code.
---
 
### WP 2.3 Laptop scene with placeholder geometry (T3) (≈ 2-3 days)
 
**Goal.** `LaptopScene` fully working with the placeholder `LaptopGeometry` and `PhysicsParams`. When the lab measurements arrive, only a config changes.
 
**Tasks.**
- **`mjcf_xml()`:** table (static), laptop base (free joint), lid (hinge with `frictionloss`, `damping`, `armature`, `range`), and the UR5 from `ur5_mjcf_xml()` with position actuators on the six joints.
- **Gripper as a parameterised stand-in:**
  - `mode="fixed_closed"`: rigid closed fingers, if the demos push the lid with closed fingers (lab request 4);
  - `mode="parallel"`: two slide-joint fingers driven through `GripperModel.opening`.
  Arm link geoms stay visual-only; only the fingers and the flange collide.
- **Robot placement:** robot base at `T_WB` (identity for now), laptop at a plausible reachable pose in front of it.
- **Simulation:** `reset`, `step_chunk` and `get_state` as specified in the `scene.py` docstring. 16 substeps per 30 Hz frame; return `ChunkRollout`.
- **`ParamPrior`:** a sampler for $p(\psi)$ with the ranges of guide section 4. It includes a rejection test: discard samples where the lid would not hold still at the observed angle.
- **`scripts/twin_scripted_close.py`:** a scripted closing motion, rendered to PNG frames with WP 1.1's renderer. A video file needs `imageio`; ask before adding it. It can also be played in `twin_view.py`.
**Acceptance (from the `scene.py` docstring, plus one).**
1. The scripted close shuts the lid.
2. The null action leaves all bodies still: under 1e-6 m after 5 s (the null-verdict proposition).
3. Deterministic.
4. Stable for 200 prior draws (no NaN, penetration under 2 mm).
5. Halving the timestep changes the final lid angle by less than 0.5°.
6. Added: the rejection test agrees with simulation. A sample that fails the analytic hold condition makes the lid move in the null test; one that passes does not.
**Prompt.** Generic frame, WP 2.3. Add: "All numbers are placeholders; keep every dimension in `LaptopGeometry`, `PhysicsParams` or `GripperModel`, never hard-coded in the XML."
 
---
 
## 4. Phase 3: complete the twin on synthetic ground truth
 
**Idea.** Each fitting step of the twin can be tested on data the twin generates itself with *known* answers. Render the twin at a known scene state, camera pose and physics, then check that the fitting code recovers them. This is a *sim-to-sim recovery test* (new term). It does not prove the fit works on real images, but it shows the code is correct and how much information each view carries. When the real data arrives, only the input changes.
 
### WP 3.1 Cameras, segmentation masks, texture hook (T4 without lab data) (≈ 1-2 days)
 
- **`src/twin/cameras.py`:** pinhole cameras from $(K_v, T_v)$ into MJCF cameras (`fovy` from $f_y$ and the image height; principal-point offsets need care, check how MuJoCo handles them). Placeholder intrinsics for D405/D435 scaled to 192x320 (check). Projection of 3D points, with a test that the TCP projects where it renders.
- **`render.py`:** `render_masks()` using MuJoCo's segmentation rendering *(new: a render mode that returns, per pixel, the id of the geom it shows instead of a colour)*, grouped into robot, base and lid.
- **Texture:** a stub `project_first_frame_texture(image, masks, cameras)` with the interface only; it is used when real frames exist.
- **Acceptance:** masks partition the rendered pixels; the projected TCP falls inside the robot mask; the mask IoU between two nearly equal states is close to 1 and drops as the lid angle changes.
### WP 3.2 Initialiser fit on rendered masks (T5 logic) (≈ 2 days)
 
- **Task config first (Step 2.0).** The proposal makes the initialiser general: only Step 2.0 changes between tasks, and G1 validates it on the first frames of **all four tasks** (laptop, duck, Push-T, cups). So build `src/twin/task_config.py` with a `TaskConfig` holding:
  - the text prompts per object part (laptop: "laptop", "laptop screen");
  - a function that builds the object MJCF from primitives (later possibly a SAM 3D mesh);
  - the unknown state variables with their ranges and grid steps (laptop: $x=(p_x,p_y,\varphi,\vartheta)$).
  Write the laptop config now. For the other three, write placeholder configs (object as a box or cylinder with a free planar pose) so the code path is exercised. Their real geometry comes with the first frames (check which object models the paper used).
- **`init_fit.py`:**
  - `fit_scene(obs_masks: dict[view, mask], q0, cameras, geometry, grid) -> EpisodeFit`: the loss of eq. (fit) with IoU, an optional depth term (off), and penetration;
  - grid search, then local refinement;
  - the near-optimal set $\hat{\mathcal X}_\nu$;
  - a quality gate $\mathcal L_{\max}$;
  - the physical check (settle and reject);
  - cache I/O (`scene_cache/episode_XXX.json`).
- **Tests on synthetic ground truth:**
  1. Perfect masks recover $x$ within 1 cm and 2° (estimate; set the final tolerances after the first run).
  2. Masks corrupted by erosion/dilation of 1-3 px and random blobs: report the degradation curve.
  3. Leave-one-view-out IoU is implemented and reported.
  4. Ambiguity: a single view with the lid seen edge-on gives a near-optimal set wider than with three views.
  5. Generality: `fit_scene` runs unchanged with each of the four task configs on their synthetic renders (only the `TaskConfig` differs).
  6. Proposition 3: the near-optimal set is never empty, and a frame with loss above $\mathcal L_{\max}$ is flagged and excluded.
- **Output:** a short table in `progress.md` with the error per view combination. It tells you in advance how much each camera matters.
### WP 3.3 Camera extrinsics from robot silhouettes (≈ 1-2 days)
 
- Fit $T_v$ (6 parameters per camera) by maximising the IoU between rendered robot masks at known joint angles and observed robot masks, over $M$ frames with different poses. Initialise from a coarse grid or a rough guess.
- **Test:** render the arm from a known camera at 10-20 joint configurations, perturb $T_v$, recover it. Report the error vs the number of frames and vs mask noise.
- **Note:** real use needs realistic UR5 visual meshes (the capsules are too crude). Find the ROS-Industrial `universal_robot` UR5 meshes and check their licence; download them yourself, since the sandbox cannot. Record this in `progress.md`.
### WP 3.4 Physics identifiability and controller lag (Step 5.1 on synthetic data) (≈ 2 days)
 
- **Sensitivity:** for the scripted close, compute finite-difference derivatives of the lid-angle trajectory with respect to each component of $\psi$. The proposal's $\psi$ (Step 1) is hinge friction and damping, gripper-lid friction and laptop-table friction. `PhysicsParams` also has lid mass and COM, which are extras: include them, but keep the proposal's four as the main set. This is a *sensitivity matrix* (new: rows are time steps, columns parameters; entry = how much the lid angle at that time moves per unit change of that parameter). Parameters with near-zero columns, or columns nearly parallel to each other, cannot be pinned down from demos. The prior then stays wide there and the twin will abstain more.
- **Recovery:** generate "observed" trajectories at a known $\psi$ and fit $\psi$ back by grid or random search, first on the state (lid angle), later on the change features (Phase 4). State-level recovery is an upper bound on what video can give.
- **Controller model (Step 3, M3):** the proposal fits both *delay and gains* from commanded vs measured poses. Simulate commanded vs measured joints with a known lag of 0-2 frames and known actuator gains, and recover both.
- **Output:** a table of identifiable and non-identifiable parameters. It is a method-chapter result and tells you which lab questions matter most (e.g. whether to ask for the hinge torque).
---
 
## 5. Phase 4: GPU-side tools (lab PC, checkpoints)
 
### WP 4.1 Ctrl-World save/restore and probe re-run (assumption M4) (≈ 1-2 days)
 
- **`scripts/ctrl_world_restore_check.py`:**
  - build the env as the close config does;
  - reset (with the dataset if present; otherwise a stand-in observation, check whether reset accepts one);
  - `chunk_step(a)`, then `get_state()` (line 3444), then `chunk_step(x)` giving V1;
  - `load_state()` (line 3508), then `chunk_step(x)` giving V2;
  - assert V1 == V2 bitwise; with a different `_common_noise_call_index` the output must differ.
- **`probe_rollout(env, actions, seed_index)`:** the frames-only path (`_infer_next_chunk_frames`, line 2747, without `_infer_next_chunk_rewards`, line 2381). The env must be restored afterwards.
- **If bitwise equality fails:** set the deterministic flags, then measure the residual variance. This is the proposal's fallback (include it in $\sigma^W$).
- **Constraints:** everything under `/data/moro` on the lab PC; check that the checkpoint fits the GPU memory there.
### WP 4.2 V-JEPA 2 encoder and a first representation check (≈ 1-2 days)
 
- **`src/twin/features.py`:** `VJEPAEncoder(windows, stride, resolution)` returning the pooled, unit-normalised window features $\phi_t$ and $\phi_{\text{ref}}$ (a still clip of frame 0). Feed it into WP 1.3.
- **First check on twin renders only:** lid angle changed by 10° vs lighting/texture changes. $\tilde D$ must react more to the lid than to appearance (a first version of Step 5.4).
- **Optional real-video smoke test:** film your own laptop being closed by hand with a phone, three angles if possible. It is not thesis data, only a check that the change features see a lid closing in real video.
- New dependency (weights, maybe `transformers` or the official repo): ask first.
### WP 4.3 SAM 3 smoke test (≈ half a day, but start the access request now)
 
- Install under `/data/moro`. Check whether the weights need a Hugging Face access request, and request it now if so (check).
- Run with the prompts "laptop" and "laptop screen" on photos of your own laptop at several lid angles. Save overlays; time per image.
- **Output:** an adapter `sam3_masks(image, prompts) -> dict[name, mask]` with the same mask format as WP 3.1, so WP 3.2 can switch from rendered to SAM 3 masks without changes.
- **Silhouette fallback (Step 4 remark).** If the representation check fails (M5), the comparison becomes SAM 3 masks of the *generated* frames against the twin's rendered masks. Add `silhouette_change_distance(masks_x[T], masks_y[T])` to `compare.py`, with the same "change since frame 0" structure as $\tilde D$ (e.g. per-frame IoU change). Also try SAM 3 once on a generated Ctrl-World frame, if one is at hand, to see whether it segments generated images at all.
---
 
## 6. Phase 5: integration
 
### WP 5.1 `twin_plugin` with arm modes (≈ 2 days)
 
- **`twin_plugin/sitecustomize.py`:** follows `stage15_plugin/`, gated by `RLINF_TWIN_MODE` ∈ {`off`, `log`, `weight`}. In `weight` mode a second variable `RLINF_TWIN_ARM` selects the E3 arm:
  - `T`: $w=p\cdot g$;
  - `T0`: $g\equiv1$ (chunk-0 verdicts only);
  - `TG`: $p\equiv1$ (grounded only);
  - `S`: T's weights randomly permuted within each batch, with a logged seed.
  Arm A is `log` mode (all checks computed, $w\equiv1$), as E1 requires.
  - Env worker: attach a per-chunk `trust_weight` field next to the rewards (around `_select_training_rewards`, `env_worker.py:1404`). In `log` mode it is computed but forced to 1.
  - Actor: gather the weights with the same all-gather as the rewards (`_compute_cross_rank_grpo_advantages`, `fsdp_actor_worker.py:1716`; check how rewards travel), and replace the call to `validate_and_compute_group_suffix_advantages` with a wrapper around WP 1.2.
- **Acceptance (unit tests, no cluster):**
  - with `log` mode, the patched advantage function equals the original bit for bit on synthetic cross-rank batches;
  - with `off`, nothing is patched;
  - `T0` and `TG` give the expected factor equal to 1;
  - `S` preserves the multiset of weights in each batch and changes their assignment. The cluster smoke run (`close_smoke_2n4g.yaml`) is written as a script for you to submit once the data is there.
### WP 5.2 Phase-A rollout dump (≈ 1 day)
 
- **What to dump, per rollout:**
  - episode id, group id and member id, update index;
  - the 5 action chunks;
  - per-chunk rewards (trajectory and terminal parts) and Ctrl-World's chunk videos (uint8, compressed, per physical camera);
  - the success-classifier output.
- **Why now:** E1 and E2 are computed offline on arm A's rollouts. If the dump is missing when arm A runs, arm A has to be repeated.
- **Storage:** estimate the size per update before enabling it. `tests/test_storage_quota_guard.py` shows the repo already guards quotas; reuse that guard. Make it subsampleable (every $n$-th update, a fraction of groups).
- **Acceptance:** round-trip test (dump, load, identical arrays); size estimate written in `progress.md`.
### WP 5.3 Step 9 diagnostics and the E1/E2 analysis (≈ 2 days)
 
Offline code in `analysis/twin_audit/`, run on the WP 5.2 dumps. Develop and test it on synthetic logs, for example the toy sandbox's or hand-made ones with a known trend.
 
- **Arm-following check (Step 9):** $e^{\text{arm}}=1-\mathrm{IoU}$(arm mask in $V^W$, twin robot rendered at the commanded pose), in free space only. Robot masks of generated frames come from SAM 3 (WP 4.3); rendered ones from WP 3.1.
- **Physically inconsistent imagined successes (Step 9):** success-classifier output from the dump, combined with the twin's lid angle above the closing threshold for every $\vartheta\in\Theta$. Analysis only, never in the training signal.
- **Re-synchronised residual:** optional; last priority.
- **E1 tables:** verdict rates per type, phase and starting scene; ranking agreement on decisive candidate pairs (WP 1.4); null-action hallucination rate per group; distribution of $k^\*$; abstention rate per chunk.
- **E2 statistics:** a Mann-Kendall trend test of failure and divergence rates over updates, and a lagged cross-correlation between the failure rate and model-space success across updates and seeds. *(New: Mann-Kendall is a rank-based test for a monotone trend in a time series, with no assumption about its distribution; a lagged cross-correlation measures whether one series tends to move some updates before the other.)*
- **Acceptance:** on synthetic logs with a planted increasing trend and a planted 2-update lead, the tests detect both; on trend-free logs, the rejection rate at the 5 % level is about 5 %.
---
 
## 7. Phase 6: the day the data arrives (checklist)
 
1. Settle the `observation.state` question (joints or EEF) with the one-liner in `progress.md`.
2. T2 demo check: convert the recorded actions of the 8 held-out episodes and compare with the recorded states.
3. Replace placeholder geometry, gripper mode and camera intrinsics with the lab values; re-run all twin tests.
4. Extrinsics (WP 3.3) on real robot masks (SAM 3 with the prompt "robot arm", or rendered-robot fit).
5. T5 on the 40 first frames with SAM 3 masks; overlay images checked by eye; hand-label about 10 frames.
6. T6 demo replay in twin and Ctrl-World; phase map; Step 5 calibration (fit $p(\psi)$, thresholds, representation check on real clips).
7. G1 generality: the initialiser on real first frames of duck, Push-T and cups, with their real `TaskConfig`.
8. The cluster smoke run with the plugin in `log` mode, then arm A with the dump (WP 5.2) enabled.
## 7b. Phase 7: robot preparation for E4 (January)
 
Not urgent now. The proposal requires everything to be dry-run before robot access, in the 14-24 Jan block.
- A written protocol for lab members: placement sheet (the same placements for both policies, randomised order), reset procedure, success criterion and timing as in the paper.
- Scripts: policy evaluation with automatic video and log recording; execution of about 20 (action, probe) pairs from identical starts at chunk 0; 5 repeats of one action for the noise floor.
- Post-hoc replay of every real trial in Ctrl-World and the twin. This is the T6 harness with policy actions; it gives the false-alarm rate under M7.
---
 
## 8. Answers to the side questions
 
**MuJoCo viewer: yes, and it costs nothing.** It ships with the `mujoco` package you already installed (`python -m mujoco.viewer --mjcf=src/twin/assets/ur5.xml` opens the arm; check the flag syntax for 4.0.1). It is worth it for two reasons:
- seeing T2's joint trajectories catches frame and sign errors that numbers hide;
- in T3, contact problems (fingers passing through the lid, the lid jittering) are much easier to see than to infer from logs.
Run it on your Windows laptop. The lab PC over SSH has no display, so use off-screen rendering there. The arm currently looks like capsules, which is fine for now. Realistic meshes are only needed for silhouette fitting (WP 3.3).
 
**Should you finish the twin without the videos?** Mostly yes, with one correction on what the data is for. In the proposal:
- the **laptop model** is two boxes and a hinge from ruler measurements (lab request 3), not a SAM-3 mesh (SAM 3D is only an option for other tasks' objects);
- **SAM 3** gives the *masks* of the real first frame for the fit;
- the **videos and demos** give $p(\psi)$, the controller lag, the camera extrinsics (if no calibration exists), the phase map and the thresholds.
So what needs data is *numbers*, not *code*. Phase 3 is exactly "complete the twin without the videos": every fitting procedure exists and is tested on known synthetic answers, so the day data arrives you swap inputs, not write code. Two cautions:
- Do Phase 1 first. It is cheaper, it is on the critical path for the in-loop method, and your maths study needs WP 1.2.
- Do not tune physics values by hand without data. Tune the *code* and the *tests*. Placeholder values will be replaced, so time spent making them "look right" is lost.
 
