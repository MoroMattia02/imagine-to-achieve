# Open items and deviations from the plan

Snapshot of 25 Nov 2026, branch `twin` at commit `6855217` (after WP 1.3). It covers T1, T2 (synthetic part) and WP 1.1-1.3 of the data-free roadmap. `progress.md` stays the running log; this file collects in one place:
- what is still open;
- where the implementation departs from, or had to interpret, the plan.

"The plan" means, in order of precedence:
- the proposal (`thesis_proposal_final.pdf`, 27 Oct 2026);
- the roadmap (`data_free_roadmap.md`);
- the implementation plan (`twin_implementation_plan.md`);
- the guide (`twin_detailed_guide.md`).

Tags: **[you]** needs your action or decision; **[check]** not verified by running it; **[later WP]** resolved in the WP named.

---

## 1. Open items

### 1.1 Your action or decision

| # | Item | Why it matters | Blocks |
|---|---|---|---|
| O1 | **What `observation.state` holds in `close_desktop_lerobot_joint_3cam`: joints or an EEF pose** [you]. The repo evidence conflicts (`progress.md`, open problems). One-minute check: `meta/info.json`, features `observation.state` and `action`. | If it holds joints, production seeds Ctrl-World with joint angles read as an EEF pose (the saturation bug noted at `world_model_ctrl_world_env.py:2214`). It also decides how the twin gets `q0` and `T_WB`. | T2 demo check, the twin's start state |
| O2 | **Lab requests, not sent yet** [you]: UR5 vs UR5e, the 0.18 m TCP and the joint limits (±2π assumed); camera intrinsics and extrinsics; laptop dimensions; gripper geometry; which episodes Ctrl-World was fine-tuned on. | Critical path for T3-T5 and Step 5. | WP 2.3, Phase 3, Phase 6 |
| O3 | **Clip w = p·g at w_min?** [you, WP 1.5]. The roadmap marks this "ask". The proposal only requires w ∈ [0, 1] with w_min > 0 (eq. (18)), so the product can reach w_min². WP 1.2 deliberately does not enforce a floor, so either answer fits. | Fixes the weight floor seen by the advantages. | WP 1.5 |
| O4 | **WP 1.1 on Windows** [you, check]: `python -m pytest tests/test_twin_*.py -q` should now give 86 passed. Then the viewer by hand: `python scripts/twin_view.py`, `--demo-chunk`, `--replay <file>`; also `python -m mujoco.viewer --mjcf=src/twin/assets/ur5.xml`. | The asset tests and the viewer were verified on Linux only. | nothing |
| O5 | **Corrections to the plan documents** [you]. These documents are yours, so I did not edit them; see §3. | Avoids re-implementing a wrong statement later. | nothing |
| O6 | **Pre-existing ruff findings**: two long lines and a `zip` without `strict=` in `src/twin/robot.py`; a missing blank line after two module docstrings; import order in `src/rlinf_modified/algorithms/fpo.py`; a trailing blank line in `advantages.py` [you]. All were present before Phase 1. Fix them in one separate commit, or leave them? | Cosmetic. Fixing the `advantages.py` one touches the old path's file, though not its code. | nothing |
| O7 | **The proposal PDF is not tracked**: `*.pdf` is gitignored [you]. Use `git add -f docs/thesis/thesis_proposal_final.pdf` if it should be in git. | Equation numbers in docstrings refer to it. | nothing |

### 1.2 To verify later

| # | Item | When |
|---|---|---|
| V1 | **Done boundaries are shared within a group in production** (fixed horizon) [check]. Lemma 1 after imputation, and therefore the invariance of the trust-weighted advantages to a common reward shift, needs this. | WP 5.1 |
| V2 | **Which suffix-advantage function production uses for the close config** [check]. There are three: `grpo_action_suffix_advantages` (`src/rlinf_modified`), the cross-rank `validate_and_compute_group_suffix_advantages` (`cross_rank_grpo.py:801`), and `compute_grpo_action_suffix_advantages` (`third_party/rlinf_runtime/rlinf/algorithms/advantages.py:139`, with success anchoring and dynamic gammas). The roadmap does not mention the third. WP 1.2 matches the first two bit for bit at w = 1; the third was not compared. | WP 5.1 |
| V3 | **Gripper clip range** = q01/q99 of the policy action statistics (`action_stats_path`, not in the repo). Needed for exact gripper parity in T2. | when the stats are available |
| V4 | **`T_WB`** (robot base in the world frame) is unknown; the base sits at the origin for now. | from demos or the lab |
| V5 | **Joint speed limit 180°/s and the action plausibility limits** (5 cm, 0.35 rad per 1/15 s step) are guesses [check]. | from the demo action statistics |
| V6 | **mujoco aarch64 wheel and EGL on the GH200 nodes** [check]. | before any cluster run with the twin |
| V7 | **Render time 0.09-0.10 ms/frame is a lower bound** (7 untextured geoms, one view, RTX 4070). Re-time it with the laptop, textures and three views. | WP 2.3 / WP 3.1 |
| V8 | **Cost of κ**: K²/2 distances per candidate and chunk. Measure it once K and the feature size are fixed [check]. | WP 4.2 |
| V9 | **Link masses, radii and meshes are placeholders**; real UR5 meshes are needed for silhouette fitting [check]. | WP 3.3 |
| V10 | **The full test suite fails on Windows**: 10 failures and 5 collection errors, all present before T1 (Linux-only calls, missing `rlinf`/`omegaconf`/`scipy`); not twin-related. | no action planned |

---

## 2. Deviations and decisions, per milestone and WP

Each entry gives what the plan says, what was done, and why. **Approved** marks a decision you explicitly took or confirmed. **Review** marks a choice I made that you have not explicitly confirmed.

### T1 and T2 (before Phase 1)

| Plan says | Done instead | Why | Status |
|---|---|---|---|
| UR5e from MuJoCo Menagerie (proposal) | Original UR5, generated from the DH constants in `eef_pose_adapter.py` | Those constants produced Ctrl-World's conditioning states; the proposal allows adapting to the older UR5. Already listed in roadmap §0.1. | Approved (roadmap §0.1) |
| Guide: Jacobian from MuJoCo `mj_jacSite` | Geometric Jacobian in numpy | Identical to `mj_jacSite` (tested to 1e-12); keeps T2 runnable without mujoco | Review |
| Plan and guide: damped least squares with warm start | DLS **plus** closed-form IK (8 branches) | The closed form picks the start branch when only an EEF pose is known, and defines the branch labels used to flag branch flips | Review |
| Guide §3: fixed λ ≈ 0.01-0.05, stop at a pose error of 1e-4 | λ scaled by the pose error (at most 0.05, floor 1e-10); tolerance 1e-6 | A fixed λ stalled above the tolerance near the elbow singularity. 1e-6 leaves a wide margin to the T2 acceptance (1 mm / 0.1°). | Review |
| Not specified | The twin carries the EEF state open loop, exactly like Ctrl-World, not FK of its own joints | Both models follow the same commanded path; IK problems show as flags, not as drift | Review |
| Guide: 15→30 Hz resampling of rotation by linear axis-angle | Quaternion slerp (the repo function, called as is) | That is what production does; the guide is wrong (see §3) | Approved (repo behaviour) |
| Not specified | Action conversion in float32 | Production `_convert_via_analytic_ur5_rot6d` casts to float32; this gives bit-exact parity | Approved (repo behaviour) |
| Plan/guide: main camera = `d435_rgb` | main = `d405_0_rgb`, wrist = `d435_rgb`, side = `d405_1_rgb` | `camera_layout.py:136` and the production config comment; the plan and guide are wrong (see §3) | Approved (17 Nov) |
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
| Weights validated in [w_min, 1] | Validated in (0, 1]; in [w_min, 1] only when `w_min` is passed (a new optional argument) | w > 0 is what makes m_k defined. Enforcing w_min here would decide O3 (the p·g floor) in advance. | Review |
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
| Proposal eq. (13), scores Q = −D̃; Lemma 5 | No function for Q. Lemma 5 is noted in the module docstring, as a consequence of D̃ ≤ 4. | Not in the WP 1.3 file list; Q is needed from WP 1.4 on | [later WP] 1.4 |
| Not specified | numpy, float64 internally; unit-norm tolerance 1e-5 | float32 encoder outputs are normalised to about 1e-7 | Review |

---

## 3. Errors found in the plan documents (to correct there)

| Document | Statement | Correction | Found in |
|---|---|---|---|
| `data_free_roadmap.md`, WP 1.2 acceptance 6 | "D1-B: the trusted members' advantages do not grow when other members are distrusted" | False under A and B. Replace with: B's scale is weight-independent, and B's last-chunk advantage energy never grows. See `notes/d1_scale_policy.md`. | WP 1.2 |
| `data_free_roadmap.md`, WP 1.2 | Mentions two advantage functions | A third, `compute_grpo_action_suffix_advantages` (vendored RLinf), exists; see V2 | Phase 1, Step 0 |
| Proposal, proof of P4 (b) | "‖cₜ‖ ≤ ‖φₜ‖ + ‖φ_ref‖ = 2" | After averaging over cameras ‖φₜ‖ ≤ 1, so "≤ 2"; the bound D̃ ≤ 4 is unchanged | WP 1.3 |
| `twin_implementation_plan.md` item 9; guide §1 | main camera = `d435_rgb` | main = `d405_0_rgb`, wrist = `d435_rgb`, side = `d405_1_rgb` | 17 Nov |
| `twin_detailed_guide.md` (T2 resampling) | Rotation resampled 15→30 Hz by linear axis-angle | The repo uses quaternion slerp | T2 |
| `twin_detailed_guide.md` | Twist angles marked "(check)" | Confirmed (π/2, 0, 0, π/2, −π/2, 0) from the repo function | T1 |
