# Open items and deviations from the plan

Snapshot of 26 Nov 2026, branch `twin` at `94f789f`, after Phase 1 (WP 1.1-1.5). First version: 25 Nov at `6855217`, after WP 1.3. It covers T1, T2 (synthetic part) and WP 1.1-1.5 of the data-free roadmap, and was re-checked against the repo on 26 Nov (§4). `progress.md` stays the running log; this file collects in one place:
- what is still open;
- where the implementation departs from, or had to interpret, the plan.

"The plan" means, in order of precedence:
- the proposal (`thesis_proposal_final.pdf`, 27 Oct 2026);
- the roadmap (`data_free_roadmap.md`);
- the implementation plan (`twin_implementation_plan.md`);
- the guide (`twin_detailed_guide.md`).

Tags: **[you]** needs your action or decision; **[check]** not verified by running it; **[later WP]** resolved in the WP named. Item numbers are stable: a resolved item keeps its number and moves to §1.4.

---

## 1. Open items

### 1.1 Your action or decision

| # | Item | Why it matters | Blocks |
|---|---|---|---|
| O1 | **What `observation.state` holds in `close_desktop_lerobot_joint_3cam`: joints or an EEF pose** [you]. The repo evidence conflicts (`progress.md`, open problems). One-minute check: `meta/info.json`, features `observation.state` and `action`. | If it holds joints, production seeds Ctrl-World with joint angles read as an EEF pose (the saturation bug noted at `world_model_ctrl_world_env.py:2214`). It also decides how the twin gets `q0` and `T_WB`. | T2 demo check (V14), the twin's start state |
| O2 | **Lab requests, not sent yet** [you]: UR5 vs UR5e, the 0.18 m TCP and the joint limits (±2π assumed); camera intrinsics and extrinsics; laptop dimensions; gripper geometry; which episodes Ctrl-World was fine-tuned on. | Critical path for T3-T5 and Step 5. | WP 2.3, Phase 3, Phase 6 |
| O4 | **WP 1.1 on Windows** [you, check]: `python -m pytest tests/test_twin_*.py -q` should now give 188 passed (after WP 1.5). Then the viewer by hand: `python scripts/twin_view.py`, `--demo-chunk`, `--replay <file>`; also `python -m mujoco.viewer --mjcf=src/twin/assets/ur5.xml`. | The asset tests and the viewer were verified on Linux only. | nothing |
| O5 | **Corrections to the plan documents** [you]. These documents are yours, so I did not edit them; see §3. | Avoids re-implementing a wrong statement later. | nothing |
| O6 | **Pre-existing lint findings, all present before Phase 1** [you]: fix them in one separate commit, or leave them? Phase 1's new files are clean.<br>`ruff check`:<br>- `src/twin/robot.py`: lines 16 and 52 too long, `zip` without `strict=` at line 147;<br>- `src/twin/repo_import.py:17` too long;<br>- `tests/test_twin_fk.py:145` too long;<br>- `src/rlinf_modified/algorithms/fpo.py:24` import order.<br>`ruff format --check`: `advantages.py` (a trailing blank line), `fpo.py` (one expression), `repo_import.py`, `robot.py` and `transforms.py` (a blank line after the module docstring).<br>About 57 more `ruff check` findings are in the original `src/rlinf_modified/` code (`analysis.py` 23, `config.py` 20, `engine/real.py` 6, others 1-3). | Cosmetic. Fixing `advantages.py` touches the old path's file, though not its code. | nothing |
| O7 | **The proposal PDF is not tracked**: `*.pdf` is gitignored [you]. Use `git add -f docs/thesis/thesis_proposal_final.pdf` if it should be in git. | Equation numbers in docstrings refer to it. | nothing |
| O8 | **s_W of a candidate with several probes** [you, WP 2.2]. Each probe j has its own s_W,j = \|τ̂_j\|/σ_W, but eq. (19) uses one s_W per candidate. `probe_weight` takes one scalar (decided 26 Nov). Default to evaluate in WP 2.2: the s_W of the direction where the twin predicts the largest effect. If the directions are not labelled, fall back to the max over probes. | Sets the no-verdict weight whenever J > 1 | WP 2.2 |
| O9 | **How κ_max is set** [you, before Step 5]. Step 7.3 uses it ("the twin abstains if κ > κ_max"), but Step 5 gives no rule for it. `divergence_chunk` takes it as an input. A natural rule is a quantile of κ on the fitting half (see O10). | Decides how often the twin abstains, so the detection power | Step 5 calibration |
| O10 | **Fix the abstention rule without the calibration half** [you, confirm]. κ_max and the phase map (Step 5.2) decide which chunks enter T (eq. (17)). If either is tuned on the calibration demonstrations, their scores are no longer exchangeable with a test rollout's, and P12's guarantee is lost. The proposal does not say which demonstrations Step 5.2 uses. Proposal: fit both on the fitting half. | Validity of the false-alarm bound (P12) | Step 5 calibration |
| O11 | **V-JEPA 2 dependency and weights** [you, WP 4.2]. `transformers` or the official repo, plus the weights. CLAUDE.md and the roadmap say ask first. | WP 4.2 cannot start without it | WP 4.2 |
| O12 | **SAM 3 access request** [you, now]. The roadmap (WP 4.3) says to check whether the weights need a Hugging Face access request, and to start it now if so. | Waiting time | WP 4.3, WP 3.3, WP 5.3 |
| O13 | **Tell Sichao about the schedule** [you]. The roadmap (§0.1, §1) suggests: the code ready by about 6 Dec, validation within a week of the data arriving; calibration and arm A shift by about a week per week of data delay. | The proposal's 3-16 Dec and 17 Dec blocks need the data | planning |
| O14 | **13 config tests fail locally** [you]. Their configs point at placeholder cluster paths (`/path/to/rlinf_release`). This was already so before Phase 1. A new failure in the full suite can hide among them. Option: skip those tests when the path does not exist; this edits existing tests. | A full suite that passes locally makes new failures visible | nothing |

### 1.2 To verify later

| # | Item | When |
|---|---|---|
| V1 | **Done boundaries are shared within a group in production** (fixed horizon) [check]. Lemma 1 after imputation, and therefore the invariance of the trust-weighted advantages to a common reward shift, needs this. | WP 5.1 |
| V2 | **Which suffix-advantage function production uses** [check in a resolved run config]. By reading (26 Nov): `ctrl_world_close_laptop_grpo_cosmos_native_unipc_large.yaml` sets `adv_type: grpo_action_suffix` (line 54) and `cross_rank_group.enabled: true` (lines 83-84). The actor then calls the cross-rank `validate_and_compute_group_suffix_advantages` (`fsdp_actor_worker.py:1915-1917` → `cross_rank_grpo.py:801`), which WP 1.2 matches bit for bit at w = 1. The third function, `compute_grpo_action_suffix_advantages` (`third_party/rlinf_runtime/rlinf/algorithms/advantages.py:139`, with success anchoring and dynamic gammas), is the registry path used when cross-rank grouping is off; it was not compared. The overrides in `src/rlinf_modified/engine/real.py` set cross-rank fields but not `enabled`. | WP 5.1 |
| V3 | **Gripper clip range** = q01/q99 of the policy action statistics. The configs point `action_stats_path` at a placeholder path; the file is not in the repo. Needed for exact gripper parity in T2. | when the stats are available |
| V4 | **`T_WB`** (robot base in the world frame) is unknown; the base sits at the origin for now. | from demos or the lab |
| V5 | **Joint speed limit 180°/s and the action plausibility limits** (5 cm, 0.35 rad per 1/15 s step) are guesses [check]. | from the demo action statistics |
| V6 | **mujoco aarch64 wheel and EGL on the GH200 nodes** [check]. | before any cluster run with the twin |
| V7 | **Render time 0.09-0.10 ms/frame is a lower bound** (7 untextured geoms, one view, RTX 4070). Re-time it with the laptop, textures and three views. | WP 2.3 / WP 3.1 |
| V8 | **Cost of κ**: K²/2 distances per candidate and chunk. Measure it once K and the feature size are fixed [check]. | WP 4.2 |
| V9 | **Link masses, radii and meshes are placeholders**; real UR5 meshes are needed for silhouette fitting [check]. | WP 3.3 |
| V10 | **The full test suite fails on Windows**: 10 failures and 5 collection errors, all present before T1 (Linux-only calls, missing `rlinf`/`omegaconf`/`scipy`); not twin-related. On Linux: 13 failures, see O14. | no action planned |
| V11 | **Which runs enter σ_W, eq. (15)** [check]. The proposal pools "over the n probed candidates, each repeated with R seeds"; whether the probes' runs are pooled as well as the policy action's is not said. `pooled_sigma` takes whatever rows it is given. | WP 2.2 / WP 4.1 |
| V12 | **False significance of s_W ≥ s0 at R = 2** [check at the real ρ]. s_W divides by the per-seed std of Q, not by the std of τ̂. Simulated under a zero effect (Gaussian, n = 8, s0 = 2, 20,000 runs): 7.9 % with independent runs, 2.1 % at seed correlation ρ = 0.5, 0.03 % at ρ = 0.9; with R = 4: 0.97 %, 0.07 %, 0 %. The proposal's "two seeds suffice" needs a high ρ. | WP 4.1 (measure ρ) |
| V13 | **The rule that makes a candidate pair decisive** for the ranking agreement (E1) is not in the proposal; `ranking_agreement` takes the mask as input. For example, Definition 1 applied to Δ_S over Θ. | WP 5.3 |
| V14 | **T2 demo check**, the part of T2 that needs data. Convert the recorded actions of the 8 held-out episodes with `actions_to_eef_targets`, run `ActionsToJoints`, compare with the recorded `observation.state` of the following frames, and report the error distribution. Settle O1 first. | Phase 6, item 2 |
| V15 | **Record the 20/20 split that is used.** `split_fit_calibration` uses `numpy.random.default_rng(seed)`, and numpy does not promise the same stream across versions; the ids of each half must be stored with the calibration. | Step 5 |
| V16 | **`per_chunk_scale` includes chunks where a fitting demonstration abstains** [check against Step 7.3's intent]. The proposal does not exclude them. | Step 5 |
| V17 | **The soft term's `scale` has no value yet** (Step 8.1 ablation parameter). | before the ablation |

### 1.3 Test gaps before the data arrives (review of 26 Nov)

The maths and kinematics are well covered. Branch coverage of `src/twin` is 94 % (26 Nov, twin subset):
- 89-100 % for most modules (`verdict.py` 97 %, `conformal.py` 90 %);
- 85 % for `session.py` and 79 % for `repo_import.py`;
- 0 % for the `init_fit.py` stub.

Most of the lines not covered are error branches. The gaps are where the data and the modules meet.

| # | Gap | Why | When |
|---|---|---|---|
| G1 | **One end-to-end test with a fake encoder**, from rendered frames through change features, D̃, S and κ, verdicts and p, k* and g, and w, to the trust-weighted advantages. Expected: the twin against itself gives S = 0 and w ≡ 1, so the advantages are bit-identical to the unweighted path. A twin perturbed at chunk 2 gives k* = 2, with the weights on the right (member, chunk). | Each piece is tested alone; nothing tests the wiring (indices, shapes, which weight goes with which reward). All the pieces exist now. | after WP 2.2, before WP 5.1 |
| G2 | **A data checker and round-trip checks for the day the data arrives**, tested now on a synthetic episode in the expected LeRobot layout. The checker covers shapes, units, ranges, camera keys and fps. The round trips: recorded actions → twin → recorded states (V14); FK(state) → recorded EEF pose; a rendered overlay on the real frame. `scripts/validate_push_t_demo_chain.py` does a similar chain for Push-T. | The tests make their own inputs in the format the code expects, so a wrong assumption about the data (O1, units, quaternion order, gripper scale, RGB/BGR, 15 vs 30 fps) would sit in both | before Phase 6 |
| G3 | **No code and no WP owns the chunk → window mapping T_k.** `d_tilde` and `grounded_scores` take `window_index` from the caller; WP 4.2 defines windows and stride. | Off-by-one errors between frames and windows | WP 4.2 |
| G4 | **float32 features at the real feature size** in the compare tests (now float64, d = 32). | Real encoder outputs | now (cheap); real check in WP 4.2 |

### 1.4 Resolved since the first version (25 Nov)

| # | Item | Resolution |
|---|---|---|
| O3 | Clip w = p·g at w_min? (the roadmap's "ask", WP 1.5) | **No clip, as eq. (18)** (you, 26 Nov): w ∈ [w_min², 1] |
| — | WP 1.4: eq. (19)'s no-verdict weight has no floor, while the roadmap assumes p ≥ w_min | **Floor**: p = max(w_min, σ(α_w(log s_W − log s0))) (you, 26 Nov) |
| — | WP 1.4: one s_W per candidate | **Scalar argument now**, rule for J probes in WP 2.2 (you, 26 Nov; O8) |
| — | WP 1.5: form of the soft grounded term | **Logistic around q_α on the running max** (you, 26 Nov) |
| — | WP 1.2: roadmap acceptance 6, D1-B | **Provable version** (you, 25 Nov) |
| V2 (partly) | Which advantage function production uses | Narrowed by reading (26 Nov): the cross-rank one. Still open in §1.2 until confirmed in a resolved run config. |

---

## 2. Deviations and decisions, per milestone and WP

Each entry gives what the plan says, what was done, and why. **Approved** marks a decision you explicitly took or confirmed. **Review** marks a choice I made that you have not explicitly confirmed.

### T1 and T2 (before Phase 1)

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| UR5e from MuJoCo Menagerie (proposal) | Original UR5, generated from the DH constants in `eef_pose_adapter.py` | Those constants produced Ctrl-World's conditioning states; the proposal allows adapting to the older UR5. Already listed in roadmap §0.1. | Approved (roadmap §0.1) |
| Guide §3: Jacobian from MuJoCo `mj_jacSite` | Geometric Jacobian in numpy | Identical to `mj_jacSite` (tested to 1e-12); keeps T2 runnable without mujoco | Review |
| Plan and guide: damped least squares with warm start | DLS **plus** closed-form IK (8 branches) | The closed form picks the start branch when only an EEF pose is known, and defines the branch labels used to flag branch flips | Review |
| Guide §3: λ ≈ 0.01-0.05 (tuned on the demos), stop at a pose error of 1e-4 | Damping by the smallest singular value: none above σ = 0.05, rising to λ = 0.05 at a singularity. Scaled by min(1, \|e\|/0.01); λ² floor 1e-10. Tolerance 1e-6 (m and rad). | A damping that does not fade near the solution stalled above the tolerance near the elbow singularity. 1e-6 leaves a wide margin to the T2 acceptance (1 mm / 0.1°). | Review |
| Not specified | The twin carries the EEF state open loop, exactly like Ctrl-World, not FK of its own joints | Both models follow the same commanded path; IK problems show as flags, not as drift | Review |
| Guide §1: 15→30 Hz resampling "linear in state space, including the axis-angle channels" | Quaternion slerp for rotation (the repo function `resample_eef_state_sequence_by_fps`, called as is) | That is what production does; the guide is wrong (see §3) | Approved (repo behaviour) |
| Not specified | Action conversion in float32 | Production `_convert_via_analytic_ur5_rot6d` casts to float32; this gives bit-exact parity | Approved (repo behaviour) |
| Plan item 9, guide §1: main = `d435_rgb`, wrist = `d405_0_rgb` | main = `d405_0_rgb`, wrist = `d435_rgb`, side = `d405_1_rgb` | `camera_layout.py:136` (`CLOSE_DESKTOP_DROID_LAYOUT`) and the production config comment; the plan and guide are wrong (see §3) | Approved (17 Nov) |
| Not specified | Joint speed limit 180°/s on all joints; step plausibility limits of 5 cm and 0.35 rad | Placeholders until demo statistics or lab values exist (V5) | Review |
| Not specified | mujoco as an optional extra, pinned at 4.0.1 | Keeps the cluster environment unchanged until the aarch64 wheel is checked (V6) | Review |

### WP 1.1 Housekeeping, T0 render, viewer

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| Write α = ±π/2 rotations with exact `sqrt(0.5)`, then regenerate `ur5.xml` | Done. The regenerated file is **byte-identical** to the committed one | The Windows libm had returned the value equal to `sqrt(0.5)`; glibc's correctly rounded `sin(float(π)/4)` is one ulp lower. A new test fakes a 1-ulp-off libm, so the property is checked on any single machine. | As planned |
| `MUJOCO_GL=egl` on Linux (CLAUDE.md); proposed rule: only when no `DISPLAY` | `tests/conftest.py` sets EGL on **every** Linux run, unless `MUJOCO_GL` is already set | This machine has `DISPLAY=:1` even over SSH, so the proposed rule would never have fired here | Review (changed after your OK) |
| T0 render test with "a fixed camera" | The camera is added in the test with `MjSpec`; the committed `ur5.xml` stays pure kinematics | Real cameras come with T4 (WP 3.1) | Review |
| Not specified | Render tests **skip** when no OpenGL context exists; the probe is a bare `mujoco.Renderer`, so twin bugs still fail | Machines without EGL (e.g. CI) | Review |
| Not specified | `TwinRenderer.render` does not call `mj_forward` and returns a new array each call | Rendering never changes the simulation state | Review |
| Time 100 frames | The timing is a `__main__` block in `tests/test_twin_render.py` | Same scene as the tests, no extra script | Review |
| Viewer: `--model ur5`, `--replay`, `--demo-chunk` | Also `--chunks N` and `--loop`. Replay files are `.json` (`{"q": [...], "fps": 30}`) or `.npz` (`q`, optional `fps`). Without options it shows a static arm at a working pose. The demo chunk is a closed 2 cm circle per chunk through `TwinSession`. | The roadmap does not define the file format or the demo motion | Review |
| Viewer: no automated test (interactive) | Headless tests of `--help` (with `DISPLAY` removed), the file loader and its validation, the demo chunk (feasible, smooth, closed) and the option wiring | Everything except the window can be tested headless | Review |

### WP 1.2 Trust-weighted advantages

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| Acceptance 6, D1-B: "the trusted members' advantages do not grow when other members are distrusted" | Replaced: (i) B's scale does not depend on the weights; (ii) at the last chunk, Σᵢ Â_B² never exceeds its full-trust value; (iii) the counterexample to the original claim is pinned in a test | The original claim is false under both A and B: 0.97 → 1.66 under B, 3.47 under A. Even B's total can grow at earlier chunks (≈360× in a two-chunk example). Derivation in `notes/d1_scale_policy.md`. | **Approved (25 Nov)** |
| Weights validated in [w_min, 1] | Validated in (0, 1]; in [w_min, 1] only when `w_min` is passed (a new optional argument) | w > 0 is what makes m_k defined. Enforcing w_min here would have decided O3 in advance. O3 was resolved on 26 Nov as no clip, so w ∈ [w_min², 1] arrives here. | Review |
| Signature without `w_min`; `std_source` without a default | `w_min: float \| None = None`; `std_source="weighted"` (option A, the proposal's eq. (4)) | See above; A is the proposal's method | Review |
| Explicit `group_index` | All groups must have the **same size ≥ 2** | As in both existing functions (fixed `group_size`). It is also what makes the w = 1 parity bit-exact (same memory layout as the old reshape). | Review |
| Not specified | Every member enters m_k, the mean and the std, whatever its loss mask; the mask multiplies the output only; output is float32 times the mask | Same convention as the existing functions | Review |
| Test-only path that bypasses the w_min check | No bypass flag: the tests call the private building blocks `_impute` and `_normalise` with w = 0 | The public API stays strict | Review |
| Stats: share of w < 1, mean w, per-group std ratio, max \|A\| | Returned as a frozen dataclass `TrustStats`. Weight statistics cover loss-mask-valid entries only. The std ratio is a `[T, groups]` tensor, NaN where the raw std is 0. | Typed and loggable | Review |
| Test 1: "equal to the formula" of the cross-rank function | Bit-for-bit equality (float32, groups scattered over the batch, member ids in column order) | It holds exactly, so the test is stricter | As planned (stricter) |
| Not in the plan | Extra tests: an independent numpy implementation of eqs. (20) and (4); `weights=None` against a verbatim copy of the pre-WP function; permutation equivariance of the group index; the option in `advantages.py` against the trust function for any weights | Each guards a property the roadmap tests could miss (found while planning the sensitivity check) | Review |
| Finding, not a deviation | With w = 0 a reward drops out of the advantages **only under A**. Under B it still sets the scale s_k. | Exact neutrality of the advantages (P14 (c) carried to the advantages) is a property of A; this favours the default | For your D1 notes |

### WP 1.3 Change features and D̃

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| Proposal: φₜ averaged over cameras, then eq. (11). Roadmap: `change_features` asserts unit-norm inputs. | Pipeline: `change_features` **per view** (unit norm asserted), then `average_views`, then `d_tilde` | Eq. (11) is linear, so both orders give the same c (tested). D̃ ≤ 4 still holds after averaging (tested). | Review |
| Acceptance: "a constant offset b on φₜ and φ_ref gives D̃ = 0" | Tested on unit features that stay unit under one constant offset: a slice φ·u = β of the sphere with b = −2βu (a reflection) | A generic offset breaks unit norm, so the real pipeline would reject it | Review |
| `window_index` (form not specified) | Distinct integer positions only; boolean masks are rejected | A short boolean mask would silently be read as indices | Review |
| `average_views` keyed by physical camera name | Any non-empty subset of `PHYSICAL_CAMERAS` is accepted (not necessarily all three); role names like `main` are rejected; views are summed in a fixed order | Allows single-view ablations; the result does not depend on dict order | Review |
| `grounded_scores -> (S, κ)` | As specified. The per-sample distances d(ϑ) are not returned. It loops over the K samples, calling the same distance as `d_tilde`. | S equals the minimum of `d_tilde` exactly. Cost to be measured (V8). | Review |
| Proposal eq. (13), scores Q = −D̃; Lemma 5 | No function for Q. Lemma 5 is noted in the module docstring, as a consequence of D̃ ≤ 4. | Not in the WP 1.3 file list. WP 1.4 and 1.5 also take scores as inputs, so Q is first computed where features become scores. | [later WP] 2.2 / 4.2 |
| Not specified | numpy, float64 internally; unit-norm tolerance 1e-5 | float32 encoder outputs are normalised to about 1e-7 | Review |

### WP 1.4 Chunk-0 verdicts

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| Proposal eq. (19), no verdict: p = σ(α_w(log s_W − log s0)), no floor. Roadmap test 5: p ∈ [w_min, 1]. | p = max(w_min, σ(α_w(log s_W − log s0))) | The roadmap and the proposal disagreed. A candidate without a verdict should never weigh less than a proven failure. The floor also keeps w > 0, which eq. (20) and `trust.py` need. Equal to eq. (19) wherever σ(·) ≥ w_min. | **Approved (26 Nov)** |
| `probe_weight(label, s_w, …)`: one s_W per candidate | Kept as one scalar; the rule for J probes is open (O8) | The proposal defines s_W per probe only | **Approved (26 Nov)** |
| `combine_probes`: "any failure, then any consistent, then no verdict" | As specified. When several different failures occur, the reported one follows a fixed order: wrong reaction, invents an effect, ignores the action. | Not specified. The order makes the result independent of probe order. All failures get w_min, so it affects only the E1 tables. | Review |
| Not in the roadmap's file list | `common_seed_effect(q_a[R], q_alt[R])`: the common-seed estimate of P6 | The P9 sign-error test (acceptance 4) then exercises package code | Review |
| Acceptance 4: simulated d ∼ N(τ, σ²) | Simulated as two common-seed runs (a shared seed effect plus independent noise), with Gaussian and two-point noise, through `common_seed_effect`. Also tested: unbiasedness and variance Var(d)/R (P6). | Exercises the paired structure of P6, not only the mean of a normal sample | Review |
| Acceptance 1: every input gets exactly one label | The six table cells are written independently from Definition 1 and the table. On 4000 random inputs with boundary values mixed in (τ = 0, ±η0, ±η; s_W = s0; σ = 0), exactly one cell holds and it equals the returned label. Every cell is hit at least 50 times. | A function that returns an Enum always gives one label; the meaningful check is that its label is the only cell that holds | As planned (stricter) |
| Not specified | σ_W = 0 is allowed: s_W = ∞ for τ̂ ≠ 0, 0 for τ̂ = 0. s0 > 0 is required. | The limits of \|τ̂\|/σ, without a division by zero | Review |
| Not specified | Strict input checks. `verdict` rejects "significant with sign 0". `probe_weight` needs a label exactly when the candidate is probed. `phase_ok`, `probed` and `w_significant` must be bools. η0 ≥ 0. | Wiring errors fail loudly instead of giving a plausible weight | Review |
| `null_action_label(score, σ, s0)` | No phase argument: the twin is "sure of no effect" by P8, whatever the phase map. Assumes η0 > 0. The label never enters the weights. | P8; the roadmap signature has no phase | Review |
| `ranking_agreement(Δ_W, Δ_S, mask)` | Each unordered pair i < m counts once. The mask must be symmetric and boolean. A decisive pair with Δ_S = 0 is rejected. NaN when no pair is decisive. The decisive rule is left to the audit (V13). | Δ is antisymmetric, so (i, m) and (m, i) carry the same information | Review |

### WP 1.5 Conformal threshold and divergence chunk

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| Acceptance 4: w = p·g ∈ [w_min², 1]; "ask whether to clip" | Not clipped. `combined_weights` follows eq. (18): w_0 = p_0·g_0, w_k = g_k for k ≥ 1. w reaches w_min² only at chunk 0, when the probes failed and k* = 0. | As eq. (18). Two independent failures multiply, and w > 0 keeps m_k defined. | **Approved (26 Nov)** |
| `grounded_weights(k_star, N, w_min, *, soft, S, m, scale)`: with `soft=True`, "g decays with S/m" | g_k = w_min + (1 − w_min)·σ((q_α − R_k)/scale), with R_k the running max of S_j/m_j over the non-abstaining chunks j ≤ k (g_k = 1 while there is none). Extra arguments `q_alpha` and `abstain`. A `k_star` that disagrees with these inputs is rejected. | Tends to the hard step as scale → 0, and keeps "from k* on, distrusted". The hard and soft arms agree on which candidates diverged. | **Approved (26 Nov)** |
| `conformal_threshold`: the ⌈(n+1)(1−α)⌉-th smallest | Rank computed in exact rationals, with α read as the decimal it prints as; also exposed as `conformal_rank` | Floats give ⌈10·(1 − 0.7)⌉ = 4 instead of 3 (tested) | Review |
| Not specified | A rollout on which the twin abstains at every chunk has T = −inf and is never flagged. −inf is accepted among calibration scores. | The same rule for calibration and test keeps the scores exchangeable. Many such demonstrations would lower q_α. | Review |
| Not in the roadmap's file list | `abstains` (one abstention rule for both halves and for test rollouts), `calibrate` → `Calibration(m, q_alpha, T_calib)`, `combined_weights`, frozen `RefereeDefaults`/`DEFAULTS` | Acceptance 5 needs a function that sees the ids; acceptance 4 needs w = p·g as code | Review |
| `split_fit_calibration(ids, seed)`: 20/20 | The ids are sorted, then permuted with the seed. With an odd count the calibration half gets the extra one. Halves are returned sorted. | The split depends only on the set of ids and the seed; record it (V15) | Review |
| `per_chunk_scale(S_fit)`: the median calibration score on the fitting half | Median over all fitting demonstrations per chunk, abstaining chunks included; a zero median raises | The proposal does not exclude them (V16) | Review |
| `appearance_floor`: 95th percentile, η = 2η0 | numpy's default (linear) percentile | Not specified | Review |
| Acceptance 1: coverage on 20,000 sets of 20 scores | As specified, plus: the exact split-conformal rate (n+1−k)/(n+1) within 4 standard errors, for three (n, α) settings; coverage of the whole pipeline (m on a fitting set, q on a calibration set); "flagged iff T > q_α" (P12) | Stricter | As planned (stricter) |
| Chunk indexing not specified | 0-based chunks k = 0..N−1; `k* = None` stands for the proposal's ∞ | | Review |

---

## 3. Errors found in the plan documents (to correct there)

| Document | Statement | Correction | Found in |
|---|---|---|---|
| `data_free_roadmap.md`, WP 1.2 acceptance 6 | "D1-B: the trusted members' advantages do not grow when other members are distrusted" | False under A and B. Replace with: B's scale is weight-independent, and B's last-chunk advantage energy never grows. See `notes/d1_scale_policy.md`. | WP 1.2 |
| `data_free_roadmap.md`, WP 1.2 | Mentions two advantage functions | A third, `compute_grpo_action_suffix_advantages` (vendored RLinf), exists; it is the path used when cross-rank grouping is off (V2) | Phase 1, Step 0 |
| Proposal, proof of P4 (b) | "‖cₜ‖ ≤ ‖φₜ‖ + ‖φ_ref‖ = 2" | After averaging over cameras ‖φₜ‖ ≤ 1, so "≤ 2"; the bound D̃ ≤ 4 is unchanged | WP 1.3 |
| Proposal eq. (19), no-verdict case | σ(α_w(log s_W − log s0)), with no floor | max(w_min, σ(α_w(log s_W − log s0))), as decided on 26 Nov. Step 8.2's "since w_min > 0, Σᵢ w > 0" relies on it. | WP 1.4 |
| Proposal Step 8.1 | "A soft grounded term (decaying with S_{i,k}/m_k instead of a step) is an ablation" | State the form: g_k = w_min + (1 − w_min)·σ((q_α − R_k)/scale), R_k the running max of S_j/m_j over non-abstaining j ≤ k (decided 26 Nov) | WP 1.5 |
| Proposal Steps 5 and 7.3 | κ_max is used but never calibrated, and Step 5.2 does not say which demonstrations fit the phase map | Add the rule for κ_max, and fit κ_max and the phase map on the fitting half (O9, O10) | WP 1.5 |
| `twin_implementation_plan.md` item 9; guide §1 (table of symbols) | main = `d435_rgb`, wrist = `d405_0_rgb`, extra = `d405_1_rgb` | main = `d405_0_rgb`, wrist = `d435_rgb`, side = `d405_1_rgb` | 17 Nov |
| `twin_detailed_guide.md` §1 (line 59) | Resampling 15→30 Hz is "linear in state space, including the axis-angle channels" | The repo function interpolates xyz and gripper linearly and rotation by quaternion slerp | T2 |
| `twin_detailed_guide.md` §2 (line 77) | Twist angles marked "(check against the repo function)" | Confirmed (π/2, 0, 0, π/2, −π/2, 0) from the repo function | T1 |

---

## 4. How this file was checked (26 Nov)

Re-read or re-run against the repo at `94f789f`:
- **File and line references:**
  - `world_model_ctrl_world_env.py:2214` (the joint-angle comment), `cross_rank_grpo.py:801`, `rlinf/algorithms/advantages.py:139`, `camera_layout.py:136`;
  - the roadmap's WP 4.1 and 5.1 references: `get_state` 3444, `load_state` 3508, `_infer_next_chunk_frames` 2747, `_infer_next_chunk_rewards` 2381, `env_worker.py:1404`, `fsdp_actor_worker.py:1716`.

  All are correct.
- **Quoted plan statements:** roadmap WP 1.2 acceptance 6 (line 133); plan item 9; guide lines 49, 59, 77 and 112; `.gitignore` line 9 (`*.pdf`).
- **Code constants:** IK damping and tolerances (`ik.py:197-209`), joint speed and step limits, `trust_weighted_suffix_advantages` defaults, the repo resampling (slerp, in `resample_eef_state_sequence_by_fps`).
- **Lint:** `ruff check` and `ruff format --check`, for O6.
- **Tests, 26 Nov:**
  - twin subset 188 passed;
  - `test_trust_weighting.py` + `test_algorithms_contracts_rewards.py` 46 passed;
  - full suite earlier the same day 237 passed, 13 failed (O14), before WP 1.4 and 1.5 added 102 tests.

Corrections made in this pass:
- O6 now lists the exact findings (the earlier list was incomplete);
- the DLS damping row now describes the singular-value damping;
- V2 narrowed by reading the production config and the actor;
- the O4 count updated;
- the camera row now quotes the plan in full;
- new items: O9-O14, V14-V17, G1-G4, and the §1.4 table.
