# Twin progress log

Last updated: 27 Nov 2026. Branch `twin`. Milestones refer to `docs/thesis/twin_implementation_plan.md`; work packages (WP) to `docs/thesis/data_free_roadmap.md`. Open items and deviations from the plan are collected in `docs/thesis/open_items_and_deviations.md`.

## Done

**WP D.2 (`wp_docs_system.md`): the notes ported into the book. Done (27 Nov).** Decisions taken before starting (you, 27 Nov): TinyTeX for a local compile; `twin_code_map.tex` stays out of the book; O17 option (a); chapter 03 holds the proposal's Sections 1-14, its Notation is Appendix A, its references close the book.

| Item | Where | Result |
|---|---|---|
| Chapters 01-04 | `docs/book/chapters/01_paper_loop.tex` (from `awyi_optimisation.tex`), `02_rl_to_fpo.tex` (`fpo_from_zero.tex`), `03_method.tex` (`thesis_proposal_final.tex`), `04_twin.tex` (`twin_walkthrough.tex`) | Ported by a script that only cuts and moves text, and asserts that each cut finds its exact text once: body copied; title block and contents removed (subtitle, byline and date kept under the heading); labels prefixed per chapter (`loop:`, `fpo:`, `method:`, `twin:`; seven labels were reused across the notes); `\appendix` dropped inside chapters (the appendices are their last sections) |
| Appendix A and references | `chapters/A_notation.tex`, `bibliography.tex`, `main.tex` | The proposal's Notation (`\section` became `\chapter`) and its 16 references. "The proposal in brief" box is at the start of chapter 03 |
| Numbering | `preamble.tex`, `03_method.tex` | Chapter 03 prints the proposal's section, Step, equation and theorem numbers: 58 of its 60 labels print what the proposal printed (`.aux` compared); the two others are its figures (4.1, 4.2). Every equation label of the four notes keeps its number |
| Preamble | `preamble.tex` | All macros, boxes and theorem styles of the five notes, one definition each. One rename: awyi's `\Lh` (`\hat L^{a}`, 19 uses) → `\Lha`. An `abstract` environment for chapters 01-02; `\sourcenote` |
| Figures | `docs/book/figures/` (13 TikZ files, `README.md`) | One file per TikZ picture, named after its label. The four images: `scripts/make_book_figures.py` now writes to `docs/book/figures/` by default (from `__file__`; run from `docs/`, it wrote there) |
| Chapter 05 | `05_trust_weighting.tex` | O17 (a): a paragraph linking to Step 8 (`\cref{method:sec:trust}`), then `notes/d1_scale_policy.md` in LaTeX. Its "Eq. (20)", "eq. (4)", "P14" are links that print those numbers. The Markdown note stays, with a line pointing to the chapter |
| Chapter 06 | `06_decisions.tex` | The 15 decisions marked Approved in `open_items_and_deviations.md` (10 before D.2, 5 in D.2), with a pointer to that file for the rest |
| Code map | deleted with `import/` | Not in the book (your decision). Each of its sections has a page in `docs/code/`; 265 of the 268 file and identifier names it mentions are there. The other three are its commit hash, a LaTeX artefact, and an abbreviated path that `files.md` writes out in full |
| TeX and matplotlib | `/data/moro/tinytex` (not in the repo); `.venv` | TinyTeX v2026.11 (TeX Live 2026, pdfTeX 1.40.29, latexmk 4.88), packages added with `tlmgr` from CTAN (`tlmgr update --self` first). matplotlib 3.11.2 (as CI), dry run first: only new packages. `CLAUDE.md` has the `PATH` line |
| Compile | `latexmk -pdf main.tex` | **82 pages, no error, no undefined reference or citation, no duplicate destination.** The D.1 title page made a duplicate `page.i` anchor; its page anchor is now off. `make -C docs/book` was not run (a scratch-copy run was declined); its grouped target needs GNU make ≥ 4.3 (here 4.3) (check) |
| Tests (27 Nov) | `tests/test_docs.py` | Written first: **8 failed, 16 passed** on the D.1 skeleton (3 of the new tests hold trivially there). Now docs **24 passed**; twin subset **188 passed**; trust subset **46 passed**; `make_code_deps.py --check` up to date; `mkdocs build --strict` no warning |

Remaining warnings of the book (all cosmetic; none is an error or an undefined reference):
- 6 × hyperref "Token not allowed in a PDF string": chapter 02, two section titles with math. The same 6 are in `fpo_from_zero.pdf`.
- 1 × hyperref "The anchor of a bookmark and its parent's must not be the same": chapter 03, the unnumbered "Overview" of Section 6. The same one is in the proposal.
- 3 × "`h' float specifier changed to `ht'": figures placed `[h]` in the notes. The originals had 7.
- Chapter 04: 1 overfull box (3.9 pt, a long `\code` name) and 5 underfull boxes. The same lines and the same values are in `twin_walkthrough.pdf`.
- Chapter 01: 3 underfull boxes (badness 4967, 1478, 1325), new. Palatino replaces Latin Modern in chapters 01-02, so lines break differently.
- Chapter 03: 1 underfull box (badness 1137), the M7 paragraph. In the proposal that line was 0.8 pt too wide; the book's `\emergencystretch` loosens it instead.
- New warnings of my own (an overfull source note, two underfull lines in chapter 06's table) were fixed.

Page-by-page check against the originals (each compiled once from a scratch copy; text by `pdftotext`, words of two or more letters, matched in order against the chapter, then against the book's unmatched words for moved floats; all 17 figures also compared by eye, side by side):

| Original | Pages | Words | In order | Moved | Not found | What "not found" is |
|---|---|---|---|---|---|---|
| `awyi_optimisation` | 13 | 4015 | 3730 | 101 | 184 | the contents (pages 1-2, 140); math tokens that Palatino and Latin Modern extract differently (`la`, `laold`, `zbik`) |
| `fpo_from_zero` | 24 | 7876 | 7432 | 117 | 327 | the contents (253); math tokens (`zj`, `ra`, `vs`); two pieces of figure text read in another order |
| `thesis_proposal_final` | 21 | 8433 | 8187 | 8 | 238 | the contents (pages 1-3); the title (now the book's title page); "KTH Supervisor Sichao Liu" (left out on purpose); two math tokens |
| `twin_walkthrough` | 17 | 5544 | 5030 | 316 | 198 | the contents (160); TikZ node labels that `pdftotext` reads in another order (the figures are identical by eye) |

No sentence of body text is missing: every unmatched run outside the contents pages is math, figure text, or the title block. All 13 TikZ figures and the 4 images are present and identical apart from their numbers ("Figure 5.8" instead of "Figure 8") and the font.

Sensitivity check (each break reverted; 10 breaks, all caught, each by its own test): a label defined twice (also caught by the references test); a reference without a label; a citation without a `\bibitem`; a figure file not input; a TikZ picture back in a chapter; the old `figs/` image path; a macro defined in a chapter; a skeleton heading left; Step 8 repeated in chapter 05; chapter 03 numbered with the chapter prefix. Restored: 24 passed.

**WP D.1 (`wp_docs_system.md`): docs system skeleton, code docs, dependency-graph generator, CI. Done (26 Nov), except the first CI run, which needs your push and the GitHub setup (O15).**

| Item | Where | Result |
|---|---|---|
| `docs` extra: `mkdocs==1.6.1`, `mkdocs-material==9.8.2`, `mkdocstrings[python]==1.0.8` | `pyproject.toml`; installed into `/data/moro/imagine-to-achieve/.venv` | dry run first: only new packages, nothing installed changed |
| MkDocs site: Material, Mermaid through `pymdownx.superfences`, mkdocstrings with `paths: [src]`, nav in the WP's order, strict link, anchor and nav validation | `mkdocs.yml`; `docs/code/` (7 pages and 15 API pages) | `mkdocs build --strict`: **0 warnings**, 1.0 s. Builds with imports of torch, mujoco, numpy, twin, rlinf_modified and rlinf blocked: **no attempt** recorded. The API pages show every public docstring of `twin.ik` (13), `twin.actions` (10), `twin.compare` (5) and `trust` (6) (and `verdict`, `conformal`) |
| `docstring_style` | `mkdocs.yml` | **google**: built with google, numpy, sphinx, auto and none (0 warnings each); only google renders the four `Args:`/`Returns:` docstrings as tables, and prose renders as with no parsing. Two docstrings render badly under every style (O16) |
| Code docs ported from `twin_code_map.tex`, updated to the current commit | `index.md`, `layout.md`, `deps.md`, `files.md`, `flows.md`, `types.md`, `testing.md` | compare, verdict, conformal added everywhere. The integration sequence (from the walkthrough) is a `sequenceDiagram`, with line numbers re-checked: only the env worker range changed. Call trees are `flowchart TD/LR`, the folder tree a code block |
| Generator | `scripts/make_code_deps.py` (stdlib, `ast`) | Mermaid graph and name table between the markers of `deps.md`; lazy edges dotted, torch, mujoco and `eef_pose_adapter.py` (by path) dashed; deterministic (a rerun writes nothing); `--check`. The generated name table equals the code map's hand-made one, plus `compare → cameras` |
| Drift tests | `tests/test_docs.py` (13, stdlib only) | **failing first: 11 failed, 1 passed** (the link-regex self-test) before any docs existed; now **13 passed** in 0.08 s |
| Book skeleton | `docs/book/main.tex`, `preamble.tex`, `chapters/00-06`, `figures/README.md`, `Makefile` | not compiled: no TeX on this machine (`latexmk: command not found`, no `pdflatex`). Braces and environments balance; the chapter structure is tested (V18) |
| CI | `.github/workflows/docs.yml` | YAML parsed; the install step run locally prints the expected pins. Not run (V18, V19) |
| Definition of done | `CLAUDE.md` | added verbatim, with the docs commands |
| Tests (26 Nov) | | docs **13 passed**; twin subset **188 passed**; `PYTHONPATH=third_party/rlinf_runtime`, `test_trust_weighting.py` + `test_algorithms_contracts_rewards.py`: **46 passed** |
| Zoomable diagrams (your request, after D.1) | `docs/code/javascripts/diagram-zoom.js`, `docs/code/stylesheets/diagram-zoom.css`, `mkdocs.yml` | Zoom buttons, Ctrl/Cmd + wheel at the pointer, drag to pan, double-click to reset, full screen (shrinks a diagram taller than the screen). Headless Firefox 160 driven through Marionette on the built site: **21 checks passed** (all 10 diagrams of `flows` and `deps` wrapped; the point under the pointer stays fixed; plain wheel still scrolls the page; Esc leaves full screen and resets; dark mode). Not tested: the toolbar showing only on hover, because headless Firefox reports `(hover: none)` and shows it always (check on a desktop). A new docs test checks that the two files exist: docs **14 passed** |

Acceptance "changing an import without rerunning the generator fails". One added import in `compare.py` (`from twin.transforms import skew`) gave `test_deps_block_equals_a_fresh_run` FAILED (1 failed, 12 passed), and `make_code_deps.py --check` exited 1. After `git checkout` the file equals HEAD and the tests give 13 passed.

Sensitivity check (each break reverted; 10 breaks, all caught):
- `test_docs.py`, eight breaks, each caught by its own test:
  - a `files.md` heading renamed;
  - a reference page emptied;
  - a link broken;
  - a nav entry removed;
  - chapter 04 dropped from `main.tex`;
  - the generator counting lazy imports as eager (3 tests);
  - a new undocumented module (5 tests);
  - a lazy import cycle `robot → ik` (2 tests).
- `mkdocs build --strict`: a broken anchor and a page missing from the nav each abort the build.

**WP 1.5: conformal threshold and divergence chunk (Step 7.3-7.4, eq. (17), P12; eq. (18) and the Step 8.1 soft ablation; calibration rules of Steps 5, 5.3, 7.3). Done (26 Nov). Phase 1 is complete.**

| Item | Where | Result |
|---|---|---|
| Rank and threshold: `conformal_rank` (⌈(n+1)(1−α)⌉, 1-based, in exact rationals), `conformal_threshold` (raises for n < (1−α)/α, i.e. n < 9 at α = 0.1) | `src/twin/conformal.py` (numpy, math, fractions) | Coverage, 20,000 seeded calibration sets each. The flag rate on a fresh score is 0.0933 at n = 20, α = 0.1, against the exact 2/21 = 0.0952 and the lower limit 0.0524. It is 0.0959 at n = 9 (exact 0.1) and 0.1983 at n = 49, α = 0.2 (exact 0.2). |
| Abstention and divergence: `abstains` (κ > κ_max, or outside the phases), `trajectory_score` (eq. (17); −inf if every chunk abstains), `divergence_chunk` (first non-abstaining chunk with S/m > q_α; None = ∞) | | End-to-end coverage of the whole pipeline (m on a fitting set, q on a calibration set, a fresh rollout): at most α. "Flagged iff T > q_α" (P12) holds on 2000 random rollouts, and k* is the first flag. Abstaining chunks never flag. |
| Weights: `grounded_weights` (hard step; soft = logistic around q_α on the running max), `combined_weights` (eq. (18): w_0 = p_0·g_0, w_k = g_k; no clip) | | Hard g is 1 before k* and w_min from k* on. Soft g stays in [w_min, 1], never increases with k, matches the formula, and tends to the hard step as scale → 0. w ∈ [w_min², 1], with w_min² reached. |
| Calibration: `split_fit_calibration`, `per_chunk_scale` (median per chunk, fitting half), `calibrate` → `Calibration(m, q_alpha, T_calib)`, `appearance_floor` (η0 = 95th percentile of \|ΔQ_S\|, η = 2η0), `RefereeDefaults(s0=2.0, alpha=0.1)` | | m comes only from the fitting ids and q_α only from the calibration ids. Changing calibration demos leaves m unchanged. Changing a fitting demo without moving a median leaves q unchanged. Ids outside both halves are ignored. Overlapping halves are rejected. |
| Tests | `tests/test_twin_conformal.py` (36 with parametrisation) | **36 passed** in 1.9 s; twin subset **188 passed**; `test_trust_weighting.py` + `test_algorithms_contracts_rewards.py` **46 passed** (26 Nov) |

Sensitivity check (each break reverted; 28 breaks, all caught):
- Order statistic: rank with n instead of n + 1, the rank used 0-based, rank in floats (caught only by the case n = 9, α = 0.7, where 1 − 0.7 = 0.30000000000000004 makes the ceiling 4 instead of 3; that case was added for this), the too-few check removed.
- Eq. (17), abstention, divergence: abstaining chunks entering T, T as a mean, T not normalised by m, κ ≥ κ_max abstaining, the phase map ignored, the last flagged chunk instead of the first, a flag at S/m = q.
- Eq. (18):
  - the hard step one chunk late, or only chunk k* distrusted;
  - soft: per chunk without the running max, abstaining chunks counted, k* consistency unchecked, the logistic's sign flipped;
  - p_0 applied to every chunk, w clipped.
- Calibration: mean instead of median, m or q from both halves, overlapping halves accepted, a split that depends on input order or ignores the seed, the appearance floor without abs, η = η0, default α = 0.05.

**WP 1.4: chunk-0 verdict logic (Step 6.3-6.4: Definition 1, eqs. (14)-(15), the verdict table, eq. (19) at chunk 0; P6, P8, P9, P11). Done (26 Nov).**

| Item | Where | Result |
|---|---|---|
| `Label` (the five labels), `twin_decision` (Definition 1; η ≥ η0 ≥ 0 enforced; undecided outside the twin's phases), `common_seed_effect` (P6), `pooled_sigma` (eq. (15), n(R−1) dof), `significance` (s_W ≥ s0), `verdict` (table of Step 6.4), `combine_probes`, `null_action_label` (P8), `probe_weight` (eq. (19), the no-verdict case floored at w_min), `candidate_pair_deltas` and `ranking_agreement` (Step 6.2, audit only) | `src/twin/verdict.py` (numpy and math) | Partition (P11): 4000 random inputs with boundary values mixed in. In every case exactly one of the six table cells holds, and it is the returned label; every cell is hit at least 50 times. The table, case by case. Undecided outside the phases. Sign-error rate ≤ Var(d)/(Rτ²) in 8 settings (Gaussian and two-point noise, 20,000 simulations each). τ̂ unbiased with variance Var(d)/R. Pooled σ² unbiased at R = 2. p ∈ [w_min, 1] on 3000 random inputs, 1 when not probed, monotone in s_W, and equal to eq. (19) above the floor. |
| Tests | `tests/test_twin_verdict.py` (66 with parametrisation) | **66 passed** in 1.4 s; twin subset **152 passed** (26 Nov) |

Sensitivity check (each break reverted; 21 breaks, all caught):
- Definition 1: non-strict "no effect", η ≥ η0 not enforced, the sign allowed to differ across ϑ, the phase map ignored.
- The table: "no effect" row swapped, sign comparison reversed, effect without a significant response labelled no verdict.
- Eq. (15) and P6: strict s_W > s0, σ = 0 with τ̂ = 0 giving s_W = ∞, the estimate from the first seed only (6 of the 8 sign-error settings fail), n·R dof, a global mean instead of per-candidate means.
- Combination: consistent checked before failures, first failing probe instead of the fixed order, the null action ignoring Ctrl-World.
- Eq. (19): no floor (the literal formula), weight decreasing in s_W, an unprobed candidate weighted w_min.
- Candidate pairs: Δ transposed, the decisive mask ignored, asymmetric masks accepted.

One test line was found vacuous and removed. It claimed that reordering the seeds of one action changes τ̂, but mean(a − b) = mean(a) − mean(b). The seed pairing acts only through Var(d).

**WP 1.3: change features and the distance D-tilde (Step 4, eqs. (11)-(12), P4; Step 7.2, eq. (16)). Done (25 Nov).**

| Item | Where | Result |
|---|---|---|
| `change_features` (eq. (11), unit norm checked per view), `average_views` (keyed by physical camera name, fixed summation order), `d_tilde` (eq. (12)), `grounded_scores` (S = min over twin samples of eq. (16), kappa = max pairwise D-tilde) | `src/twin/compare.py` (numpy, no encoder) | pseudometric (300 random triples + a collinear triple where the triangle inequality is tight), D-tilde <= 4 and 4 attained, P4 (c) on unit features under a constant offset, S = min_theta d(theta), kappa = max pair and 0 for coincident samples, windows outside the chunk ignored, view averaging commutes with eq. (11) |
| Tests | `tests/test_twin_compare.py` (17) | **17 passed** in 0.16 s; twin subset **86 passed** (25 Nov) |

Sensitivity check (each break reverted; 10 breaks, all caught after two test fixes): squared norm in eq. (12) (pseudometric, bound, formula), all windows instead of the chunk's (formula, locality), sum instead of mean (bound, formula), no reference subtraction (P4 (c), bound, commutation), no unit-norm check, S as max, kappa against the first sample only, unknown camera names accepted, duplicate windows accepted, boolean masks accepted. Two gaps found and closed: the random pseudometric test alone did not catch the squared norm (random 32-D vectors are nearly orthogonal; a collinear triple now does), and the boolean-mask case was rejected by the duplicate check rather than by its own check (now a 2-entry mask, which has no duplicates).

**WP 1.2: trust-weighted advantages (Step 8.2, eq. (20) into eq. (4), P14; T8; D1). Done (25 Nov).**

| Item | Where | Result |
|---|---|---|
| Eq. (20) imputation with an explicit group index; suffix returns; D1 scale `"weighted"` (A, default) or `"unweighted"` (B); `TrustStats` (share of w < 1, mean w, std ratio per group and chunk, max \|A\|) | `src/rlinf_modified/algorithms/trust.py` | w = 1: **bit-identical** to `grpo_action_suffix_advantages` (float32 and float64, random dones and masks) and to the cross-rank production formula `validate_and_compute_group_suffix_advantages` (float32, groups scattered over the batch); any w: equal to an independent numpy implementation of eqs. (20) and (4) within 2e-6 |
| Optional `weights=None, std_source="weighted"` | `src/rlinf_modified/algorithms/advantages.py` | `weights=None` equals a verbatim copy of the pre-WP function bit for bit; no old line changed |
| D1 derivations (tests 5 and 6, counterexamples) | `docs/thesis/notes/d1_scale_policy.md` | |
| Tests | `tests/test_trust_weighting.py` (37) | **37 passed**; `test_algorithms_contracts_rewards.py` **9 passed**; twin subset **69 passed** (25 Nov) |

Acceptance covered: (1) w = 1 parity, (2-4) P14 (a), (b), (c) with a test-only w = 0 through the private building blocks, (d); (5) Lemma 1 with shifts per group and chunk, A and B; (6) A: sum of squared advantages = G - 1 for any weights; B (provable version, decided 25 Nov): the scale is independent of the weights, and the last-chunk advantage energy never grows; the per-member counterexample is pinned; (7) other groups bit-identical, and permutation equivariance of the group index.

Sensitivity check (each break reverted; 12 breaks, all caught): plain group mean instead of m_k (P14 (b), (c), reference), down-weighting without imputation (P14, Lemma 1, D1-B), biased std for A (G - 1 identity, parity), eps inside a square root (parity), B using the imputed std (scale test), groups assumed contiguous (cross-rank parity, permutation), masked members left out of m_k (parity), no done cut (parity), zero weights accepted (validation), std ratio inverted (stats), `std_source` dropped by the `advantages.py` option (option test), old path changed to a biased std (frozen-copy test). The last two checks were added during the sensitivity planning, because with w = 1 the two scales coincide and could not reveal a dropped argument.

**WP 1.1: housekeeping, T0 render, viewer script. Done on Linux (25 Nov); the Windows items are (check).**

| Item | Where | Result |
|---|---|---|
| 1-ulp MJCF mismatch fixed: `Rx(0)`, `Rx(+-pi/2)` written exactly as `(1,0,0,0)`, `(sqrt(0.5), +-sqrt(0.5), 0, 0)` | `_rx_quat` in `src/twin/robot.py` | regenerated `ur5.xml` is **byte-identical** to the committed (Windows) file, so both asset tests now pass on Linux |
| T0: off-screen render from a named MJCF camera, 192x320 | `TwinRenderer.render` / `close` / context manager in `src/twin/render.py` | shape, uint8, not one colour, arm in view (3.9 % of pixels), identical for two renders, changes with `q`, unknown camera = `KeyError` |
| Render time (EGL, RTX 4070, i7-14700) | `MUJOCO_GL=egl python tests/test_twin_render.py` | **0.09-0.10 ms/frame** (3 runs, 100 frames, after one warm-up; `update_scene` + render + read-back). Lower bound: 7 untextured geoms (base + 6 capsules), one view |
| EGL default for pytest on Linux | `tests/conftest.py` | `MUJOCO_GL=egl` unless already set; Windows/macOS untouched |
| Viewer | `scripts/twin_view.py` (`--model ur5`, `--replay q.json/.npz`, `--demo-chunk [--chunks N]`, `--loop`) | headless parts tested; the window itself is (check) on the Windows laptop |
| Tests | `test_twin_render.py` (4), `test_twin_view_script.py` (9), `test_twin_mujoco_fk.py` (+3) | twin subset: **69 passed** (Linux, 25 Nov), was 51 passed + 2 failed |

Sensitivity check (each break reverted afterwards): a libm `sin/cos` for the -pi/2 twist (5 asset tests fail), swapped height/width (shape test), a reused output buffer (identity and state tests), a scene built only once (state test), no camera-name check (unknown-camera test), no finite check on replay files, a demo chunk that does not close (closed-loop test), `fps` of `.npz` files ignored (option wiring test). Not caught, by design: a top-level `import mujoco.viewer` (importing it needs no display, so `--help` still works headless). With `conftest.py` disabled and neither `DISPLAY` nor `MUJOCO_GL` set, the render tests skip with "no OpenGL context" (listed by `-ra`), they do not fail.

**T1: UR5 kinematics. Done, all acceptance criteria met.**

| Item | Where | Result |
|---|---|---|
| numpy standard-DH forward kinematics | `src/twin/robot.py` (`fk`) | equals the repo FK |
| Rotation helpers (axis-angle to matrix, geodesic angle, `make_T`) | `src/twin/transforms.py` | unit-tested |
| Load the repo's `eef_pose_adapter.py` by file path | `src/twin/repo_import.py` | used by the generator, reused in T2 |
| Reference table: 1000 random joint vectors in ±2π, seed 0, repo FK in float64 | `scripts/make_twin_fk_reference.py` writes `tests/fixtures/twin_fk_reference_ur5.json` | 261 KiB, metadata records source hash and commit |
| MuJoCo UR5 model generated from the DH constants | `ur5_mjcf_xml()` in `robot.py`; `scripts/make_twin_ur5_mjcf.py` writes `src/twin/assets/ur5.xml` | compiles in mujoco 4.0.1 |
| Tests | `tests/test_twin_fk.py` (11), `tests/test_twin_mujoco_fk.py` (7) | 18 passed |

Measured parity over the 1000 reference vectors (acceptance: < 1e-5 m and < 1e-5 rad):

| Comparison | Position max | Rotation max |
|---|---|---|
| numpy FK vs repo FK | 3.4e-16 m | 8.2e-14 rad |
| MuJoCo `tcp` site vs repo FK | 7.2e-16 m | 8.2e-14 rad |

The tests were checked for sensitivity: a flipped wrist-3 twist (0.53 m error) and a TCP 1 mm short (1.0e-3 m) fail parity; a missing `angle="radian"` fails the joint-range test.

Other: mujoco 4.0.1 installed in the local `.venv`; added to `pyproject.toml` as the optional extra `twin`. Branch `twin` pushed to the fork (`origin`), not to `upstream`.

**T2 synthetic part: done. Demo part (real `observation.state` check) still open, needs the dataset.**

| Item | Where | Result |
|---|---|---|
| Geometric Jacobian at the TCP, closed-form IK (8 branches), damped least squares with warm start, path tracking with feasibility flags | `src/twin/ik.py` | Jacobian equals finite differences and MuJoCo `mj_jacSite` (1e-12) |
| 10-D action checks (shape, non-finite, degenerate rot6d = hard errors; large steps, non-orthonormal rot6d, gripper range = warnings) | `src/twin/actions.py` (`check_actions`) | unit-tested |
| Action chunk to EEF targets, through the repo functions in float32 | `actions_to_eef_targets` | **bit-exact** with production `CtrlWorldEnv._convert_via_analytic_ur5_rot6d` (called on a stand-in `self`) |
| Chunk to 64 joint targets at 30 Hz, frame W to B via `T_WB` | `ActionsToJoints` | FK(IK) within 1e-6 m / 1e-6 rad over 5 chunks, also with an offset `T_WB` |
| `so3_log`, `invert_T` | `src/twin/transforms.py` | log map checked up to pi - 1e-9 |
| Skeleton for T3-T7 | `scene.py`, `cameras.py`, `render.py`, `init_fit.py`, `session.py` | interfaces + `NotImplementedError`; `TwinSession` runs in kinematics-only mode |
| Tests | `tests/test_twin_ik.py` (14), `test_twin_actions.py` (13), `test_twin_action_to_joints.py` (4), `test_twin_skeleton.py` (4) | 35 passed (Linux, 17 Nov) |

Acceptance (1 mm / 0.1 deg): met by a wide margin; the solver tolerance is 1e-6. The tests were checked for sensitivity: world-frame translation, world-frame rotation, a missing gripper clip, the wrong next state, `T_WB` instead of its inverse, a flipped Jacobian sign and constant damping each make at least one test fail.

## Decisions and why

- **The DH constants are read from the repo function, not from a UR datasheet.** That function produced Ctrl-World's conditioning states, so the twin must reproduce it. Reading it also confirms the twist angles (π/2, 0, 0, π/2, −π/2, 0), which the guide had left as "(check)".
- **Reference table in float64.** In float32 the repo function is off by up to 5.9e-5 rad (4 of 1000 samples above 1e-5), which is over the T1 tolerance.
- **Fixture is JSON.** `.npz` is gitignored and `scripts/verify_no_weights.py` rejects it. JSON float repr round-trips float64 exactly.
- **Guard on small quaternion components (5e-5).** The repo's matrix-to-quaternion step clamps at eps = 1e-8. This alters a component only when it is below 5e-5, and then costs up to about 1e-4 rad. The generator refuses a table that hits this case; the seed-0 minimum is 9.25e-5.
- **Geodesic angle via `atan2(sin, cos)`, not `arccos`.** `arccos` has a floor around 1e-8 near 0 and loses accuracy near π.
- **A staleness test regenerates the table from the live repo function** (needs torch, skipped without it). It fails if `eef_pose_adapter.py` changes.
- **MJCF body frames sit on their own joint axes.** Each hinge is +z at its body origin, and `qpos = q` with no offsets. This avoids the DH-vs-MuJoCo joint-axis pitfall from the guide.
- **MJCF is generated, never hand-edited.** A test checks that the committed `ur5.xml` equals the generator output.
- **`compiler angle="radian"` is explicit.** MJCF defaults to degrees, which would silently make the ±2π ranges ±0.11 rad.
- **Geoms are visual-only capsules with nominal UR5 masses.** They have no contact; contact is decided in T3, and the masses and radii are placeholders (check).
- **mujoco is an optional extra, pinned at 4.0.1.** This keeps the cluster environment unchanged until the aarch64 wheel is checked.

- **IK in numpy, not `mj_jacSite`.** The guide suggested MuJoCo's Jacobian; the numpy geometric Jacobian is identical (tested) and keeps T2 runnable without mujoco.
- **Closed-form IK as well as DLS.** DLS tracks paths (stays on the seed branch); the closed form picks the initial branch when only an EEF pose is known, and defines the branch label used to flag branch flips.
- **Damping scaled by the pose error.** Fixed damping near the elbow singularity (sin q3 = 0.06) stalled above the 1e-6 tolerance; the damping now fades as the error goes to zero.
- **The twin carries the EEF state open loop like Ctrl-World** (`next_state` of the adapter), not FK of its own joints, so both follow the same commanded path and IK problems show as flags, not drift.
- **Production conversion runs in float32** (`_convert_via_analytic_ur5_rot6d` disables autocast and casts to float32). This settles the float32 open problem: the twin uses float32 too, so it matches bit for bit.
- **Resampling 15 to 30 Hz uses quaternion slerp for rotation**, not linear axis-angle as the guide said. The twin calls the repo function, so this needs no code, only a guide correction.
- **Joint speed limit 180 deg/s on all joints** (UR5 CB3 value, check). Action step plausibility limits (5 cm, 0.35 rad per 1/15 s step) are guesses until the demo action statistics are read (check).

- **Camera naming resolved by reading (17 Nov): main = `d405_0_rgb`, wrist = `d435_rgb`, side/extra = `d405_1_rgb`.** Source: `CLOSE_DESKTOP_DROID_LAYOUT` / `CLOSE_DESKTOP_VERTICAL_LAYOUT` in `third_party/cosmos_framework/data/vfm/action/camera_layout.py:136`, consistent with the production config comment (main = D405_0, wrist = D435, extra = D405_1). The plan (`twin_implementation_plan.md`, item 9) and guide (section 1) say main = `d435_rgb`; that is wrong and should be corrected there. The terminal-goal reward remaps names again (`ctrl_world_source_mapping`), so the twin still keys views by physical camera name.

- **WP 1.1: exact `sqrt(0.5)` for the quarter-turn twists, not a tolerance in the test.** The intended rotation is exactly pi/2. glibc's `sin(float(pi)/4)` is correctly rounded (`...475`); the Windows libm returned `...476`, which happens to equal `sqrt(0.5)`. IEEE `sqrt` is correctly rounded everywhere, so the generator output is now the same on every platform. A test fakes a libm that is off by 1 ulp in either direction and checks that the MJCF is unchanged, so the property is tested on any single machine.
- **WP 1.1: the render tests add their camera with `MjSpec`**, so the committed `ur5.xml` (pure kinematics) stays unchanged. The real cameras come with T4 (WP 3.1).
- **WP 1.1: `TwinRenderer.render` does not call `mj_forward`.** The caller keeps `data` up to date, and rendering never changes the simulation state. It returns a new array each call.
- **WP 1.1: `tests/conftest.py` sets `MUJOCO_GL=egl` on every Linux run, not only when `DISPLAY` is unset.** This machine has `DISPLAY=:1` even over SSH, so a "headless only" rule would not have triggered here. An explicit `MUJOCO_GL` still wins.
- **WP 1.1: the render tests skip, rather than fail, when no OpenGL context can be created.** The check is a bare `mujoco.Renderer`, separate from `TwinRenderer`, so a bug in the twin code still fails. The skip reason is printed by `-ra`; on this machine the tests run (no skip).
- **WP 1.1: the timing is a `__main__` block in the test file**, so the recorded number comes from the same scene as the tests, without a separate script.

- **WP 1.2: roadmap acceptance 6 for option B replaced (decided with you, 25 Nov).** "Trusted members' advantages do not grow when others are distrusted" is false under A and B (counterexample: 0.97 -> 1.66 under B, 3.47 under A). Tested instead: B's scale does not depend on the weights, and at the last chunk sum_i A_B^2 cannot exceed its full-trust value; the counterexample is pinned. Derivation in `notes/d1_scale_policy.md`.
- **WP 1.2: weights are validated in (0, 1], or in [w_min, 1] when `w_min` is passed.** Strictly positive weights are what make m_k defined (eq. (20)). The floor itself belongs where the weights are built (WP 1.4, 1.5), so WP 1.5's open question (clip p*g at w_min or not) stays open instead of being decided here.
- **WP 1.2: all groups must have the same size >= 2**, as in both existing functions (fixed `group_size`). This lets the code gather groups into a `[T, groups, G]` tensor laid out exactly like the old reshape, which is what makes the w = 1 parity bit-exact.
- **WP 1.2: all members enter m_k, the mean and the std, whatever their loss mask**, as in the existing functions; the mask multiplies the output only. Dtype: computed in the input dtype, returned as float32 times the mask, as before.
- **WP 1.2: the private `_impute` and `_normalise` are the test-only path for w = 0.** The public functions reject w = 0; tests import the building blocks instead of a bypass flag.
- **WP 1.2: under B, a distrusted reward still sets the scale.** With w = 0 it leaves the centred returns (P14 (c)) and, under A, the advantages unchanged; under B it still changes them through s_k. Exact neutrality of the advantages is a property of A only (tested, and in the note).

- **WP 1.3: change features are formed per view, then averaged.** The proposal averages the unit-normalised features over cameras before eq. (11); the roadmap asserts unit norm in `change_features`. Both hold in the order per-view `change_features` -> `average_views` -> `d_tilde`, because eq. (11) is linear (tested). The P4 (b) bound still holds after averaging: an average of vectors of norm <= 2 has norm <= 2 (tested).
- **WP 1.3: the P4 (c) test uses offsets that keep the features unit-normalised.** A generic offset b would be rejected by the unit-norm check. Unit features stay unit under a constant b exactly when they lie in a slice phi . u = beta of the sphere and b = -2 beta u (a reflection); the test builds such features.
- **WP 1.3: `window_index` takes distinct integer positions only** (the windows T_k of chunk k within the video measured from frame 0, as eq. (16) needs). Boolean masks are rejected, since a short mask would silently be read as indices.
- **WP 1.3: `grounded_scores` loops over the K twin samples (K^2/2 pairs for kappa)**, calling the same distance as `d_tilde`, so S equals the minimum of `d_tilde` exactly. Cost at production size is (check) once K and the feature size are known (WP 4.2).

- **WP 1.4: the no-verdict probe weight is floored at w_min (decided with you, 26 Nov).** Eq. (19) gives σ(α_w(log s_W − log s0)), which goes to 0 as s_W → 0. The roadmap (WP 1.4 test 5, WP 1.5 test 4) and Step 8.2 ("since w_min > 0, Σ w > 0") assume p ≥ w_min, and `trust.py` rejects w = 0. `probe_weight` returns max(w_min, σ(...)): a candidate without a verdict never weighs less than a proven failure. Equal to eq. (19) wherever σ(...) ≥ w_min.
- **WP 1.4: `probe_weight` takes one scalar s_W (decided with you, 26 Nov).** The proposal defines s_W per probe, but eq. (19) uses one per candidate. How to choose it from J probes is open until WP 2.2 (see open problems).
- **WP 1.4: when a candidate's probes fail in different ways, `combine_probes` reports them in a fixed order:** wrong reaction, then invents an effect, then ignores the action. The result does not depend on the order of the probes. Every failure gets w_min, so this only affects the E1 tables.
- **WP 1.4: `common_seed_effect(q_a[R], q_alt[R])` was added (P6)**, which is not in the roadmap's list. The P9 sign-error test then runs package code on simulated common-seed runs (a shared seed effect plus independent noise), not only numpy.
- **WP 1.4: σ_W = 0 is allowed.** s_W = ∞ for τ̂ ≠ 0 and 0 for τ̂ = 0, the limits of |τ̂|/σ. s0 > 0 is required, so a significant response always has a sign; `verdict` rejects "significant with sign 0".
- **WP 1.4: strict wiring checks.**
  - `probe_weight` needs a label exactly when the candidate is probed.
  - `phase_ok`, `probed` and `w_significant` must be bools.
  - η0 ≥ 0.

  A wiring error then fails loudly instead of producing a plausible weight.
- **WP 1.4: `null_action_label` has no phase argument.** By P8 the twin's state does not move under the null action, so the twin is sure of no effect whatever the phase map; this needs η0 > 0. The label is reported for RQ1 and never enters the weights.
- **WP 1.4: ranking agreement conventions.**
  - Each unordered pair i < m counts once.
  - The decisive mask must be symmetric and boolean.
  - A decisive pair with Δ_S = 0 is rejected.
  - NaN when no pair is decisive.

  The rule that makes a pair decisive is left to the audit (WP 5.3).

- **WP 1.5: w = p·g is not clipped at w_min (decided with you, 26 Nov; the roadmap's "ask").** As in eq. (18), w ∈ [w_min², 1]. It goes below w_min only at chunk 0, when the probes failed and the rollout diverged at chunk 0. It is always > 0, so m_k of eq. (20) is defined.
- **WP 1.5: soft grounded term = logistic around q_α on the running max (decided with you, 26 Nov).** g_k = w_min + (1 − w_min)·σ((q_α − R_k)/scale), where R_k is the running max of S_j/m_j over the non-abstaining chunks j ≤ k, and g_k = 1 while there is none. It keeps "from k* on, distrusted" and tends to the hard step as scale → 0. It needs `q_alpha` and `abstain` in addition to the roadmap's `S, m, scale`. A `k_star` that disagrees with those inputs is rejected, so the hard and soft arms agree on which candidates diverged.
- **WP 1.5: the conformal rank is computed in exact rationals,** with α read as the decimal it prints as (0.1 is 1/10). Plain floats give ⌈10·(1 − 0.7)⌉ = 4 instead of 3.
- **WP 1.5: a rollout on which the twin abstains at every chunk has T = −inf and is never flagged.** The same rule applies to calibration demonstrations, so −inf is accepted in `conformal_threshold` (it keeps T exchangeable). Many such demonstrations would lower q_α.
- **WP 1.5: added beyond the roadmap's list**, so that each rule exists once:
  - `abstains`: the same abstention rule for calibration and test;
  - `conformal_rank`;
  - `calibrate`/`Calibration`: acceptance 5 needs a function that sees the ids;
  - `combined_weights`: acceptance 4 needs w = p·g as code;
  - `RefereeDefaults`/`DEFAULTS`: frozen, s0 = 2, α = 0.1.
- **WP 1.5: split rule.** The ids are sorted, then permuted with `numpy.random.default_rng(seed)`; with an odd count the calibration half gets the extra one; each half is returned sorted. numpy does not promise the same stream across versions, so the split that was used must be recorded with the calibration.
- **WP 1.5: `per_chunk_scale` takes the median over all fitting demonstrations per chunk**, including chunks where a demonstration abstains, since the proposal does not exclude them (check against Step 7.3's intent). A zero median raises.
- **WP 1.5: chunks are 0-based (k = 0..N−1); `k* = None` stands for ∞.** `appearance_floor` uses numpy's default (linear) percentile.

- **WP D.1: the site is built from `docs/code/` only** (`docs_dir`), not from `docs/`, which also holds the thesis notes, the `.tex` sources and a run output. Repo files outside `docs/code/` are named as code paths, not linked, because MkDocs cannot serve them. `book.pdf` is linked with raw HTML, since it exists only on the deployed site.
- **WP D.1: CI does not install the project.** Its dependencies include torch, and the docs need none of it. The pins come from `pyproject.toml` (docs extra, pytest, numpy); matplotlib is pinned in the workflow (O18). A build in CI therefore also proves that the API pages need neither torch nor MuJoCo.
- **WP D.1: the generator documents `src/twin/*.py` without `__init__.py`**, and it also writes a table of the imported names, so that the graph's edges can be read without opening the code.
- **WP D.1: source docstrings were not edited.** The two rendering defects found (O16) are listed with their one-line fixes.
- **WP D.1: the chapter skeletons carry their sources' section headings**, so that the PDF shows the structure and D.2 sees where each body goes. The macro clashes D.2 must resolve are listed in `open_items_and_deviations.md` (§2, WP D.1).

## In progress

Nothing half-done. Phase 1 (WP 1.1 to WP 1.5) and WP D.1 are closed; the WP 1.1 Windows checks are listed under open problems. D.1's first CI run (book PDF, deployment) waits for your push and the GitHub setup (O15).

## Open problems

- **Which representation is `observation.state` in `close_desktop_lerobot_joint_3cam`? (check, important; the repo cannot settle it, 17 Nov).** Two close-desktop dataset formats exist in the code with the same 7-D layout: EEF `[x, y, z, rotvec(3), gripper]` (`UR5EEFLeRobotDataset`) and joints `[q0..q5, gripper]` (`UR5JointLeRobotDataset`, both in `third_party/cosmos_framework/data/vfm/action/datasets/`). Evidence read:
  - For EEF: the resolved production config has `joint_action_adapter: none`, so `initial_image_state_representation: auto` resolves to `eef` and the first-frame `observation.state` seeds Ctrl-World raw as an EEF pose. The production policy (`ur5_eef_rel10d`, close_desktop) was trained by `UR5EEFLeRobotDataset`, which says the source `observation.state` is an absolute EEF pose and anchors the 10-D actions on it; the Ctrl-World stats are `..._eef_state_3cam`. The Push-T demo-chain script treats `observation.state` as EEF too (a different dataset).
  - For joints: the dataset name; the comment at `world_model_ctrl_world_env.py:2214` ("This dataset's observation.state is raw joint angles"); the older pi05 config reads the same path as joints through FK; production still sets `initial_joint_state_path` to the same path.
  - Which dataset root the policy was trained on is not recorded in the repo, and the dataset is not on this machine.
  - If it holds joints, production seeds Ctrl-World with joint angles as an EEF pose (the saturation bug described in the 2214 comment). It also decides how the twin gets `q0` and `T_WB`: from joints, `T_WB` follows from FK; from EEF only, `q0` comes from `initial_configuration`.
  - One-minute check where the data lives: `python -c "import json;f=json.load(open('<dataset>/meta/info.json'))['features'];print(f['observation.state'],f['action'])"` (LeRobot usually stores per-channel `names`). Without names: joints look like `-1.57, -1.9, ...`; an EEF pose has xyz within about +-1 m and a 3-value rotvec of norm <= pi.
- **WP 1.1 on Windows (check).** Run `python -m pytest tests/test_twin_*.py -q` (expect 188 passed after WP 1.5; the asset tests should pass since the file is unchanged) and the viewer by hand: `python scripts/twin_view.py`, `--demo-chunk`, `--replay <file>`. MuJoCo's own viewer also works: `python -m mujoco.viewer --mjcf=src/twin/assets/ur5.xml` (flag read from `--help` in 4.0.1; the window was not opened here).
- **Roadmap references checked on 25 Nov (Phase 1 Step 0), not fixed:**
  - the proposal PDF is now at `docs/thesis/thesis_proposal_final.pdf` (local only: `*.pdf` is gitignored). WP 1.2 citations (eq. (4), eqs. (18)-(20), Lemmas 1-2, P14, Step 8.3) were checked against it;
  - `grpo_action_suffix_advantages` takes `(rewards, loss_mask, dones, *, group_size, gamma)`, with contiguous groups, ε = 1e-6 hard-coded, and a float32 cast before the mask. The cross-rank `validate_and_compute_group_suffix_advantages` (`cross_rank_grpo.py:801`) keeps the input dtype and gathers groups with `index_select`. WP 1.2 verified that both agree bit for bit with the trust-weighted function at w = 1 (float32; member ids in column order within each group);
  - **Lemma 1 after imputation needs the done boundaries shared within a group** (fixed horizon). Whether production dones always are is (check, WP 5.1);
  - a third suffix-advantage function, `compute_grpo_action_suffix_advantages` (`third_party/rlinf_runtime/rlinf/algorithms/advantages.py:139`, success anchoring and dynamic gammas), is not mentioned in the roadmap; which one production uses for the close config matters for WP 5.1 (check).
- **Pre-existing ruff findings in `src/twin/robot.py`** (two lines over 100 characters, `zip` without `strict=`) and a missing blank line after two module docstrings; present at `f4f669e`, not touched in WP 1.1.
- **Gripper clip range** = q01/q99 of the policy action statistics (`action_stats_path`, not in the repo). Needed for exact parity on the gripper channel.

- **Lab requests (critical path), not sent yet.** These are:
  - UR5 vs UR5e, the 0.18 m TCP and the real joint limits (±2π assumed).
  - Camera intrinsics and extrinsics.
  - Laptop dimensions.
  - Gripper geometry.
  - Which episodes Ctrl-World was fine-tuned on.
- **`T_WB` is unknown.** The robot base currently sits at the world origin; it is estimated from demos (T2/section 8) or given by the lab.
- **float32 in production: verified by reading** (see decisions). The repo FK reference stays float64; the action conversion is float32 on both sides.
- **mujoco aarch64 wheel on the GH200 nodes (check).**
- **The full test suite does not run on Windows.** There are 10 failures and 5 collection errors, all already present before T1: Linux-only calls (`os.getuid`, `fcntl`, `resource`) and missing `rlinf`/`omegaconf`/`scipy`. They are not related to the twin.
- **Link masses, radii and meshes are placeholders.** UR5 meshes (ROS-Industrial `universal_robot`, check) are needed later for silhouette-based camera fitting (T4).

- **Proposal wording, P4 (b) proof:** it writes ||phi_t|| = 1, but after averaging over cameras ||phi_t|| <= 1. The bound D-tilde <= 4 is unaffected; change "= 2" to "<= 2" in the thesis.

- **s_W of a candidate with several probes (open until WP 2.2, decided 26 Nov).** Default to evaluate in WP 2.2: the s_W of the direction where the twin predicts the largest effect. If the directions are not labelled, fall back to the max over probes.
- **Which runs enter σ_W, eq. (15) (check, WP 2.2 / 4.1).** The proposal pools "over the n probed candidates of the group, each repeated with R seeds". It is not said whether the probes' runs are pooled as well as the policy action's. `pooled_sigma` takes whatever rows it is given.
- **s_W is not a t-statistic.** σ_W is the per-seed std of Q, while the std of τ̂ is sqrt(Var(d)/R). Simulated false-significance rate under a zero effect (Gaussian, n = 8 candidates, σ_W estimated, s0 = 2; 20,000 runs per setting, 26 Nov):

  | R | ρ = 0 | ρ = 0.5 | ρ = 0.9 |
  |---|---|---|---|
  | 2 | 7.9 % | 2.1 % | 0.03 % |
  | 4 | 0.97 % | 0.07 % | 0 % |

  ρ is the correlation of Q(a) and Q(ã) under one seed. The proposal's "two seeds per action suffice" holds when ρ is high. Measure ρ in WP 4.1 (check).
- **The rule that makes a candidate pair decisive** for the ranking agreement is not in the proposal. Decide it in WP 5.3, e.g. Definition 1 applied to Δ_S over Θ.
- **Proposal wording, eq. (19):** write the no-verdict case as max(w_min, σ(α_w(log s_W − log s0))), as decided on 26 Nov. Step 8.2's "since w_min > 0, Σ w > 0" relies on this.

- **κ_max has no calibration rule in the proposal** (Step 7.3 uses it; Step 5 does not fix it). `divergence_chunk` takes it as an input.
- **The abstention rule must be fixed without the calibration half.** κ_max and the phase map (Step 5.2) decide which chunks enter T (eq. (17)). If either is tuned on the calibration demonstrations, the calibration scores are no longer exchangeable with a test rollout's, and P12's guarantee is lost. The proposal does not say which demonstrations Step 5.2 uses. Fitting both on the fitting half keeps P12 (check with you).
- **The soft term's `scale` has no value yet**; it is an ablation parameter (Step 8.1).

- **WP D.1, before your push (O15):** enable Actions on the fork; set Pages → Source: GitHub Actions; use a token with *Workflows: Read and write*; and, if `twin` is not the default branch, allow it in the `github-pages` environment (check).
- **WP D.1, not verified here:** the book compile and `make_book_figures.py` (no TeX, no matplotlib on this machine; V18), and the Mermaid drawings and the deployment (V19). All first happen in CI.
- **WP D.1, two docstrings render badly** (`verdict.verdict`'s table, the `Returns:` of `trust_weighted_suffix_advantages`; O16), and **Step 8 would appear in chapters 03 and 05** (O17, decide before D.2).
- **The trust subset needs `PYTHONPATH=third_party/rlinf_runtime`:** `test_algorithms_contracts_rewards.py` imports `rlinf.rewards` (O14).

## Exact next step

**Push `twin` and look at the first CI run** (O15, V18): the book is built there with another TeX Live image. Then **D.3** (`wp_docs_system.md`, Claude in chat): the editorial pass over the book, including chapter 00.

Then, per the roadmap calendar (29 Nov - 3 Dec): **WP 4.1, then WP 4.2, then WP 2.2.**
- **WP 4.1, Ctrl-World save/restore and probe re-run (M4):** `scripts/ctrl_world_restore_check.py` builds the env as the close config does, then:
  - runs `chunk_step(a)`, `get_state()`, `chunk_step(x)` → V1, then `load_state()`, `chunk_step(x)` → V2, and asserts V1 == V2 bitwise;
  - checks that a different `_common_noise_call_index` changes the output;
  - adds `probe_rollout(env, actions, seed_index)` on the frames-only path.

  It needs the Ctrl-World checkpoint and a GPU, everything under `/data/moro`. First check whether the checkpoint is on this machine and fits in GPU memory. The line numbers the roadmap quotes are (check). The seed correlation ρ for V12 can be measured here.
- **WP 4.2, V-JEPA 2 encoder:** `src/twin/features.py` (`VJEPAEncoder`) feeding WP 1.3, and a first representation check on twin renders. It needs a new dependency and weights: **ask first**.
- **WP 2.2, probe generator and null action (CPU):** `src/twin/probes.py` with tests first in `tests/test_twin_probes.py`. Decide the s_W rule for J probes there (O8).

Still pending once the dataset is available: the **T2 demo check** (convert the recorded actions of the 8 held-out episodes with `actions_to_eef_targets`, run `ActionsToJoints`, compare with the recorded `observation.state` of the following frames, report the error distribution). Settle the `observation.state` question first.
