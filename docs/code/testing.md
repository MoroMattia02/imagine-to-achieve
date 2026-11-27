# Testing

Tests are flat `tests/test_*.py` files; pytest's configuration is in `pyproject.toml` (`src` is on
the path, `-ra` lists skips). Every WP writes its tests first and records a sensitivity check in
`docs/thesis/progress.md`: deliberate breaks of the code, each of which a test must catch.

```bash
python -m pytest tests/test_twin_*.py -q                    # twin subset
PYTHONPATH=third_party/rlinf_runtime \
  python -m pytest tests/test_trust_weighting.py tests/test_algorithms_contracts_rewards.py -q
python -m pytest tests/test_docs.py -q                      # docs drift tests, standard library only
python -m pytest tests/ -q                                  # everything (see the notes below)
```

- **`test_algorithms_contracts_rewards.py` imports the vendored runtime** (`rlinf.rewards`), so it
  needs `third_party/rlinf_runtime` on `PYTHONPATH`; without it, it fails at collection.
- **On Linux, `tests/conftest.py` sets `MUJOCO_GL=egl`** before MuJoCo is imported (an explicit
  value wins). The render tests skip, not fail, if no OpenGL context can be created; `-ra` lists
  the reason.
- **Tests that need torch or MuJoCo skip without them** (`pytest.importorskip`), so the numpy-only
  tests run anywhere.
- **The full suite has known local failures** that predate the twin: 13 config tests whose configs
  point at placeholder cluster paths (O14 in `open_items_and_deviations.md`).

## Which test covers what

| Test file | Covers | Main checks | Tests |
|---|---|---|---|
| `test_twin_fk.py` | `robot`, `transforms` | numpy FK = repo FK (fixture); rotation helpers; fixture staleness (with torch) | 11 |
| `test_twin_mujoco_fk.py` | `robot` (MJCF) | MuJoCo `tcp` site = repo FK; asset file = generator output; exact quarter turns | 10 |
| `test_twin_ik.py` | `ik` | Jacobian vs finite differences and `mj_jacSite`; FK(IK); singularities | 14 |
| `test_twin_actions.py` | `actions` | bit-equality with the production conversion; action checks | 12 |
| `test_twin_action_to_joints.py` | `actions`, `ik` | five chained chunks, offset T_WB | 5 |
| `test_twin_skeleton.py` | `scene`, `cameras`, `session` | gripper map, projection, scene stub raises, kinematics-only session | 4 |
| `test_twin_render.py` | `render` | shape, determinism, unknown camera; timing in `__main__` | 4 |
| `test_twin_view_script.py` | `scripts/twin_view.py` | argument parsing, file loading, demo chunk (no window) | 9 |
| `test_twin_compare.py` | `compare` | D̃ is a pseudometric and ≤ 4 (P4); P4 (c) under a constant offset; S = min over θ, κ = max pair; windows outside the chunk ignored; view averaging commutes with eq. (11) | 17 |
| `test_twin_verdict.py` | `verdict` | the six table cells partition 4000 random inputs (P11); Definition 1; sign-error bound (P9); P6 unbiasedness and variance; probe weight in [w_min, 1] and monotone | 66 |
| `test_twin_conformal.py` | `conformal` | coverage of q_α on 20,000 calibration sets; P12 "flagged iff T > q_α"; k* is the first flag; hard and soft g; w ∈ [w_min², 1]; m only from fitting ids, q only from calibration ids | 36 |
| `test_trust_weighting.py` | `trust`, `advantages` | w = 1 parity with both existing functions (bit for bit); P14; Lemma 1; D1 options A and B | 37 |
| `test_algorithms_contracts_rewards.py` | `advantages`, `fpo`, contracts, rewards | finite GRPO/PPO losses; reward helpers (pre-existing) | 9 |
| `test_docs.py` | these pages, `make_code_deps.py`, the book (`docs/book/`) | `deps.md` block current; a section and an API page per module; links resolve; the extra CSS and JavaScript files exist; no import cycle; the generator on a synthetic package. Book, at the source level: `main.tex` includes the seven chapters and Appendix A; `import/` is gone; no skeleton heading left; labels unique; every reference and citation resolves; one file per TikZ figure, each input once; the images are those of `make_book_figures.py`; macros defined once, in the preamble; chapter 05 links to Step 8 (O17); chapter 03 keeps the proposal's numbers | 24 |

The twin subset is 188 tests (26 Nov 2026).
