# Repository layout

The repo is large (the vendored training runtime alone has hundreds of files). The tree shows only
what the twin and the trust weighting touch. Markers: ● implemented, ◐ skeleton (some parts work,
see [Files](files.md)).

```text
imagine-to-achieve/
├── src/
│   ├── twin/                         the scene twin (package)
│   │   ├── transforms.py        ●    rotations and 4x4 poses
│   │   ├── robot.py             ●    UR5 DH table, FK, MJCF generator
│   │   ├── repo_import.py       ●    loads the repo's eef_pose_adapter.py by path
│   │   ├── ik.py                ●    Jacobian, closed-form IK, DLS, path tracking
│   │   ├── actions.py           ●    action checks, actions -> EEF targets -> joints
│   │   ├── render.py            ●    off-screen rendering (masks: skeleton)
│   │   ├── cameras.py           ◐    intrinsics, camera records, projection
│   │   ├── scene.py             ◐    laptop, physics parameters, scene (T3)
│   │   ├── init_fit.py          ◐    per-episode fit and cache (T5)
│   │   ├── session.py           ◐    per-environment twin session (kinematics only works)
│   │   ├── compare.py           ●    change features, D-tilde, S and kappa (WP 1.3)
│   │   ├── verdict.py           ●    chunk-0 verdicts and the probe weight (WP 1.4)
│   │   ├── conformal.py         ●    conformal threshold, divergence chunk, g, calibration (WP 1.5)
│   │   └── assets/ur5.xml            generated MJCF, committed
│   └── rlinf_modified/algorithms/
│       ├── trust.py             ●    trust-weighted rewards and advantages (WP 1.2)
│       └── advantages.py        ●    synthetic-engine advantages, optional weights
├── scripts/
│   ├── make_twin_ur5_mjcf.py         writes src/twin/assets/ur5.xml
│   ├── make_twin_fk_reference.py     writes the FK test fixture
│   ├── twin_view.py                  interactive MuJoCo viewer
│   ├── make_code_deps.py             writes the generated part of docs/code/deps.md
│   └── make_book_figures.py          regenerates four figures of the book (fpo_from_zero)
├── tests/
│   ├── conftest.py                   sets MUJOCO_GL=egl on Linux
│   ├── test_twin_*.py                11 files, 188 tests
│   ├── test_trust_weighting.py       37 tests
│   ├── test_docs.py                  drift tests for these pages and the book skeleton
│   └── fixtures/twin_fk_reference_ur5.json
├── third_party/rlinf_runtime/rlinf/  vendored runtime: read, never edited
│   ├── envs/world_model/eef_pose_adapter.py            conversions reused by the twin
│   ├── envs/world_model/world_model_ctrl_world_env.py  Ctrl-World env (hook points)
│   └── algorithms/cross_rank_grpo.py                   production advantages
├── stage15_plugin/                   the plugin pattern twin_plugin/ will copy (WP 5.1)
├── docs/
│   ├── code/                         these pages (MkDocs, mkdocs.yml at the root)
│   ├── book/                         the concept book (LaTeX), built to book.pdf by CI
│   └── thesis/                       roadmap, progress log, open items, plan, guide, notes
├── mkdocs.yml
├── .github/workflows/docs.yml        builds the book and the site, deploys to GitHub Pages
└── CLAUDE.md                         rules for Claude Code, definition of done
```

## Three things about the layout

- **`src/` layout.** `pyproject.toml` sets `package-dir = {"" = "src"}`, and pytest uses
  `pythonpath = ["src"]`. That is why the code writes `from twin.ik import ...`, not
  `from src.twin...`. Scripts in `scripts/` add `src/` to `sys.path` themselves.
- **The vendored runtime is read, never edited.** The twin reuses three functions of
  `eef_pose_adapter.py` by loading that file directly (`twin.repo_import`, see
  [Files](files.md#twinrepo_import)). Integration will patch the runtime at run time from
  `twin_plugin/` (WP 5.1), not by editing it.
- **Generated files are never hand-edited.** `src/twin/assets/ur5.xml`, the FK fixture and the
  marked block of [deps.md](deps.md) are written by scripts, and tests check that they match.
