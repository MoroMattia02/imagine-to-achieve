"""Regenerate the four images of book chapter 02 (from fpo_from_zero.tex) from its flow-model formulas.

field2d.pdf     vector field v(z) = (2 - z1, 1 - z2) with four trajectories
densities.pdf   p_tau(z) = 1/2 N(z; 2 tau, (1-tau)^2) + 1/2 N(z; -2 tau, (1-tau)^2) at four times
paths.pdf       left: straight training lines z_tau = tau x + (1-tau) eps; right: trajectories of v*
slopefield.pdf  slope field of v*(z, tau) = (2 tanh(2 tau z / (1-tau)^2) - z) / (1 - tau)

Usage: python scripts/make_book_figures.py [output_dir]

The default output_dir is the book's figures folder, docs/book/figures/, where the chapter's
\includegraphics finds them (\graphicspath in preamble.tex), whatever the working directory.
The PDFs are not committed (*.pdf is gitignored); CI and `make -C docs/book` run this first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE = "#2E6F95"
ORANGE = "#C96A1B"
GREY = "#6B7280"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
BOOK_FIGURES = Path(__file__).resolve().parents[1] / "docs" / "book" / "figures"


def v_star(z: np.ndarray, tau: float) -> np.ndarray:
    """Averaged velocity field of the two-point example (data at +2 and -2)."""
    mean_x = 2.0 * np.tanh(2.0 * tau * z / (1.0 - tau) ** 2)
    return (mean_x - z) / (1.0 - tau)


def integrate_v_star(z0: np.ndarray, n_steps: int = 4000, tau_end: float = 0.999):
    """Small-step Euler from tau = 0 to tau_end; returns (taus, paths)."""
    taus = np.linspace(0.0, tau_end, n_steps + 1)
    z = np.array(z0, dtype=float)
    out = [z.copy()]
    for t0, t1 in zip(taus[:-1], taus[1:]):
        z = z + (t1 - t0) * v_star(z, t0)
        out.append(z.copy())
    return taus, np.stack(out)


def field2d(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 4.0))
    g = np.linspace(-1, 4, 11)
    Z1, Z2 = np.meshgrid(g, np.linspace(-2, 4, 13))
    ax.quiver(Z1, Z2, 2 - Z1, 1 - Z2, color=GREY, angles="xy", scale_units="xy", scale=4, width=0.004)
    t = np.linspace(0, 4, 200)
    for s in [(-0.5, 3.5), (3.8, 3.6), (3.6, -1.6), (-0.8, -1.5)]:
        z1 = 2 + (s[0] - 2) * np.exp(-t)
        z2 = 1 + (s[1] - 1) * np.exp(-t)
        ax.plot(z1, z2, color=BLUE, lw=1.6)
        ax.plot(*s, "o", color=BLUE, ms=4)
    ax.plot(2, 1, "*", color=ORANGE, ms=12)
    ax.set_xlabel("$z_1$")
    ax.set_ylabel("$z_2$")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def densities(path: Path) -> None:
    z = np.linspace(-4, 4, 800)

    def normal(x, m, s):
        return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * np.sqrt(2 * np.pi))

    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    colors = ["#9CA3AF", "#6B9AC4", BLUE, "#14213D"]
    for tau, c in zip([0.0, 0.3, 0.6, 0.9], colors):
        s = 1 - tau
        p = 0.5 * normal(z, 2 * tau, s) + 0.5 * normal(z, -2 * tau, s)
        ax.plot(z, p, color=c, lw=1.8, label=rf"$\tau={tau}$")
    ax.set_xlabel("$z$")
    ax.set_ylabel(r"$p_\tau(z)$")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def paths(path: Path) -> None:
    rng = np.random.default_rng(0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.4), sharey=True)
    tau = np.linspace(0, 1, 50)
    eps = rng.standard_normal(22)
    xs = rng.choice([-2.0, 2.0], size=22)
    for e, x in zip(eps, xs):
        a1.plot(tau, tau * x + (1 - tau) * e, color=ORANGE if x > 0 else BLUE, lw=1.0, alpha=0.85)
    a1.set_title("straight training lines (they cross)")
    a1.set_xlabel(r"$\tau$")
    a1.set_ylabel("$z$")
    z0 = np.sort(eps)
    taus, zs = integrate_v_star(z0)
    for j in range(len(z0)):
        a2.plot(taus, zs[:, j], color=ORANGE if z0[j] > 0 else BLUE, lw=1.0)
    a2.set_title(r"trajectories of $v^\star$ (they do not cross)")
    a2.set_xlabel(r"$\tau$")
    for a in (a1, a2):
        a.set_ylim(-3.2, 3.2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def slopefield(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    T, Z = np.meshgrid(np.linspace(0.02, 0.92, 19), np.linspace(-3, 3, 21))
    V = v_star(Z, T)
    norm = np.sqrt(1 + V**2)
    ax.quiver(T, Z, 1 / norm, V / norm, color=GREY, angles="xy", pivot="mid", width=0.0035, scale=28)
    z0 = np.linspace(-2.2, 2.2, 9)
    taus, zs = integrate_v_star(z0, tau_end=0.95)
    for j in range(len(z0)):
        ax.plot(taus, zs[:, j], color=ORANGE if z0[j] > 0 else BLUE, lw=1.3)
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel("$z$")
    ax.set_ylim(-3.2, 3.2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BOOK_FIGURES
    out.mkdir(parents=True, exist_ok=True)
    field2d(out / "field2d.pdf")
    densities(out / "densities.pdf")
    paths(out / "paths.pdf")
    slopefield(out / "slopefield.pdf")
    print(f"wrote 4 figures to {out}/")


if __name__ == "__main__":
    main()
