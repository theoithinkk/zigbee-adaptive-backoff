#!/usr/bin/env python3
"""
Makes the line graphs (mean +/- 95% CI over runs) from results/*.csv.
    python3 plot_results.py            -> results/plots/*.png + results/summary.csv
"""
import glob, os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

METRICS = [
    ("pdr", "Packet Delivery Ratio (%)"),
    ("avg_delay_ms", "Average delay (ms)"),
    ("retx_total", "Retransmissions (frames)"),
    ("ca_fail", "Channel access failures (pkts)"),
]


def label(r):
    if r["mode"] == "adaptive":
        return f"Adaptive (W={int(r['window'])}, hi={r['hi']:.1f}, lo={r['lo']:.1f})"
    return "Default (minBE=3)" if r["minBE"] == 3 else f"Fixed minBE={int(r['minBE'])}"


def ci95(x):
    n = len(x)
    if n < 2:
        return 0.0
    return stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / n ** 0.5


def main():
    files = glob.glob("results/*.csv")
    files = [f for f in files if not f.endswith("summary.csv")]
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["config"] = df.apply(label, axis=1)
    df = df.drop_duplicates(subset=["config", "N", "interval", "run"])

    g = df.groupby(["config", "interval", "N"])
    rows = []
    for (cfg, it, n), grp in g:
        r = dict(config=cfg, interval=it, N=n, runs=len(grp))
        for m, _ in METRICS:
            r[m] = grp[m].mean()
            r[m + "_ci95"] = ci95(grp[m])
        rows.append(r)
    summ = pd.DataFrame(rows).sort_values(["interval", "config", "N"])
    summ.to_csv("results/summary.csv", index=False)

    os.makedirs("results/plots", exist_ok=True)
    for it in sorted(summ["interval"].unique(), reverse=True):
        traffic = "light (1 s)" if it >= 1 else f"heavy ({it:g} s)"
        sub = summ[summ["interval"] == it]
        fig, axes = plt.subplots(2, 2, figsize=(11, 8))
        for ax, (m, title) in zip(axes.flat, METRICS):
            for cfg, c in sub.groupby("config"):
                ax.errorbar(c["N"], c[m], yerr=c[m + "_ci95"], marker="o", capsize=3, label=cfg)
            ax.set_xlabel("Number of sensors (N)")
            ax.set_ylabel(title)
            ax.grid(alpha=0.3)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle(f"IEEE 802.15.4 star network — {traffic} traffic, mean ± 95% CI")
        fig.tight_layout()
        out = f"results/plots/metrics_interval_{str(it).replace('.', 'p')}.png"
        fig.savefig(out, dpi=150)
        print("saved", out)


if __name__ == "__main__":
    main()
