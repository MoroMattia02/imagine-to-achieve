# imagine-to-achieve: scene digital twin (master thesis)

## Goal
Build a MuJoCo digital twin (UR5, gripper, laptop, three cameras) driven by the same
actions as Ctrl-World, used as a referee of Ctrl-World's imagined feedback during RL
post-training. Short thesis summary: `docs/thesis/thesis_context.md`. Code map and
milestones T0 to T8: `docs/thesis/twin_implementation_plan.md`. Theory, reasons and
tests per component: `docs/thesis/twin_detailed_guide.md`. Read the relevant section
before starting a milestone. Work on one milestone at a time.
Data-free roadmap and the current WP: `docs/thesis/data_free_roadmap.md`.

## Layout
- `third_party/rlinf_runtime/` vendored RLinf runtime (production training loop).
  Ask before editing it; prefer the plugin pattern of `stage15_plugin/`.
- `src/rlinf_modified/` Hydra overrides, synthetic engine, advantage code.
- `src/twin/` (new): the twin package; one section per module in `docs/code/files.md`.
- `twin_plugin/` (new): sitecustomize + hook, enabled by env var RLINF_TWIN_MODE.
- `tests/` flat `test_*.py` files; twin tests go in `tests/test_twin_*.py`.
- `docs/thesis/` thesis documents (this task's plan files). `docs/` also has the repo's own files.
- `docs/code/` code docs (MkDocs, `mkdocs.yml`; `deps.md` partly generated); `docs/book/` the
  concept book (LaTeX). Plan: `docs/thesis/wp_docs_system.md`. CI builds both
  (`.github/workflows/docs.yml`). Step and equation numbers in docstrings refer to the proposal.

## Conventions (do not change silently)
- `T_AB` maps frame B coordinates into frame A; `T_AC = T_AB @ T_BC`.
- Repo EEF state: [x, y, z, rx, ry, rz, gripper], rotation = axis-angle. Keep rotation
  matrices internally, convert only at the boundary, compare rotations by geodesic angle.
- Actions: 10-D [pos_delta(3), rot6d_delta(6), gripper_abs(1)], body-frame chaining
  T_{i+1} = T_i * dT. The close config uses translation and rotation gain 1.0.
- Import the repo's conversion functions by file path (`eef_pose_adapter.py`); never
  re-implement rot6d.
- Robot constants are the original UR5 (see `eef_pose_adapter.py`), not UR5e, until the lab says otherwise.

## Rules
- Mark anything not verified by running it as "(check)". Never say a test passes
  unless you ran it and saw the output.
- Every milestone has acceptance criteria in the plan; write the test first.
- Never run or submit cluster jobs (sbatch, scancel); write the script and tell me.
- Do not add dependencies or install packages without asking. `mujoco` will be needed.
- Small commits per milestone on branch `twin`. Do not push; I push.
- No data, weights, credentials or `.env` files in git.

## Commands
- Environment: Python 3.11 only (pyproject: `>=3.11,<3.12`). Local setup (check on Windows):
  `python -m venv .venv`, activate it, `pip install -e ".[dev]"`.
- Tests: `python -m pytest tests/ -q` (pytest config is in pyproject; `src` is on the path).
- Synthetic engine run: `python -m rlinf_modified.train --config configs/synthetic.yaml`.
- MuJoCo rendering: default GL backend on Windows; `MUJOCO_GL=egl` only on Linux with a GPU.
- Heavy dependencies (ray, real-run extras, SAM 3, V-JEPA) are not needed for milestones T0 to T3 and T8.
- Docs (`pip install -e ".[docs]"`): `python scripts/make_code_deps.py` after changing an import;
  `python -m pytest tests/test_docs.py -q`; `mkdocs build --strict`. Book: `make -C docs/book`
  (needs latexmk; figures first with `python scripts/make_book_figures.py docs/book/figures`).

## Definition of done (every WP)
A WP is finished only when: (1) docstrings of changed public functions are updated; (2) the
affected `docs/code/` pages are updated and `python scripts/make_code_deps.py` has been run;
(3) if the method or a decision changed, the matching book chapter and
`open_items_and_deviations.md` are updated; (4) `progress.md` is updated; (5) `mkdocs build --strict`
and `tests/test_docs.py` pass.
