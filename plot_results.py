#!/usr/bin/env python3
"""
Makes the line graphs (mean +/- 95% CI over runs) from results/*.csv.
    python3 plot_results.py            -> results/plots/*.png + results/summary.csv

Graphs:
    metrics_interval_*.png     every configuration
    comparison_interval_*.png  Default vs best fixed minBE (picked per N and metric) vs Adaptive
    minbe_over_time.png        adaptive minBE per sensor over time (needs `run_experiments.py trace`)
"""
import glob, os, re
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
HIGHER_IS_BETTER = {"pdr"}
DEFAULT = "Default (minBE=3)"
ADAPTIVE = "Adaptive (W=10, hi=0.5, lo=0.2)"  # the proposed rule's default parameters


def label(r):
    if r["mode"] == "adaptive":
        return f"Adaptive (W={int(r['window'])}, hi={r['hi']:.1f}, lo={r['lo']:.1f})"
    return DEFAULT if r["minBE"] == 3 else f"Fixed minBE={int(r['minBE'])}"


def ci95(x):
    n = len(x)
    if n < 2:
        return 0.0
    return stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / n ** 0.5


def better_title(ax, m):
    ax.ticklabel_format(axis="y", useOffset=False)  # show 99.99, not "+1e2" and -0.01
    better = "higher" if m in HIGHER_IS_BETTER else "lower"
    ax.set_title(f"{'↑' if better == 'higher' else '↓'} {better.capitalize()} is better",
                 fontsize=10, loc="left", color="dimgray")


def traffic_name(it):
    return "light (1 s)" if it >= 1 else f"heavy ({it:g} s)"


def interval_tag(it):
    return str(float(it)).replace(".", "p")


def best_fixed(sub, m):
    """Best fixed-minBE row at each N for metric m (oracle: chosen after seeing the results)."""
    fixed = sub[sub["config"].str.startswith(("Fixed", "Default"))]
    pick = fixed.groupby("N")[m].idxmax() if m in HIGHER_IS_BETTER else fixed.groupby("N")[m].idxmin()
    best = fixed.loc[pick].sort_values("N")
    best["minBE"] = best["config"].str.extract(r"minBE=(\d)", expand=False).astype(int)
    return best


def plot_comparison(sub, it):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (m, title) in zip(axes.flat, METRICS):
        lines = [(DEFAULT, sub[sub["config"] == DEFAULT], dict(color="gray")),
                 ("Best fixed minBE (per N)", best_fixed(sub, m), dict(color="black", linestyle="--")),
                 (ADAPTIVE, sub[sub["config"] == ADAPTIVE], dict(color="tab:red"))]
        for name, c, style in lines:
            ax.errorbar(c["N"], c[m], yerr=c[m + "_ci95"], marker="o", capsize=3, label=name, **style)
        for _, r in lines[1][1].iterrows():  # which minBE won at each N
            ax.annotate(f"BE={r['minBE']}", (r["N"], r[m]), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=7)
        ax.set_xlabel("Number of sensors (N)")
        ax.set_ylabel(title)
        ax.grid(alpha=0.3)
        better_title(ax, m)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(f"Default vs best fixed vs adaptive — {traffic_name(it)} traffic, mean ± 95% CI")
    fig.tight_layout()
    out = f"results/plots/comparison_interval_{interval_tag(it)}.png"
    fig.savefig(out, dpi=150)
    print("saved", out)


def plot_minbe_traces():
    def case(f):  # "minbe_N30_interval_0p1.csv" -> (30, 0.1)
        n, it = re.search(r"N(\d+)_interval_([\dp]+)", f).groups()
        return int(n), float(it.replace("p", "."))

    # light traffic first, then by N
    files = sorted(glob.glob("results/traces/minbe_N*_interval_*.csv"), key=lambda f: (-case(f)[1], case(f)[0]))
    if not files:
        return
    traces = [pd.read_csv(f).sort_values("time_s", kind="stable") for f in files]
    end = -(-max(t["time_s"].max() for t in traces) // 10) * 10  # sim length: last change rounded up to 10 s
    fig, axes = plt.subplots(len(files), 1, figsize=(11, 2.6 * len(files)), sharex=True, squeeze=False)
    for ax, f, t in zip(axes.flat, files, traces):
        n, it = case(f)
        for _, s in t.groupby("sensor"):
            ax.step(list(s["time_s"]) + [end], list(s["minBE"]) + [s["minBE"].iloc[-1]],
                    where="post", color="tab:blue", alpha=0.15, linewidth=0.8)
        # mean over sensors: each change shifts the sum by (new - previous value of that sensor);
        # keep only the last value at each timestamp so the t=0 start rows don't draw a ramp
        prev = t.groupby("sensor")["minBE"].shift().fillna(0)
        mean = ((t["minBE"] - prev).cumsum() / n).groupby(t["time_s"]).last()
        ax.step(list(mean.index) + [end], list(mean) + [mean.iloc[-1]], where="post",
                color="tab:red", linewidth=1.8, label="mean over sensors")
        ax.axhline(3, color="gray", linestyle=":", linewidth=1, label="IEEE default (3)")
        ax.set_ylim(-0.3, 5.3)
        ax.set_ylabel("minBE")
        ax.set_title(f"N={n}, {traffic_name(it)} traffic — {len(t) - n} changes", fontsize=10, loc="left")
        ax.set_title("↕ Neither is better: shows the rule reacting to load",
                     fontsize=9, loc="right", color="dimgray")
        ax.grid(alpha=0.3)
    axes.flat[0].legend(fontsize=8, loc="upper right", bbox_to_anchor=(1, 0.9))
    axes.flat[-1].set_xlabel("Simulation time (s)")
    fig.suptitle("Adaptive rule: macMinBE over time (thin = each sensor, run 1)")
    fig.tight_layout()
    out = "results/plots/minbe_over_time.png"
    fig.savefig(out, dpi=150)
    print("saved", out)


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
        sub = summ[summ["interval"] == it]
        fig, axes = plt.subplots(2, 2, figsize=(11, 8))
        for ax, (m, title) in zip(axes.flat, METRICS):
            for cfg, c in sub.groupby("config"):
                ax.errorbar(c["N"], c[m], yerr=c[m + "_ci95"], marker="o", capsize=3, label=cfg)
            ax.set_xlabel("Number of sensors (N)")
            ax.set_ylabel(title)
            ax.grid(alpha=0.3)
            better_title(ax, m)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle(f"IEEE 802.15.4 star network — {traffic_name(it)} traffic, mean ± 95% CI")
        fig.tight_layout()
        out = f"results/plots/metrics_interval_{interval_tag(it)}.png"
        fig.savefig(out, dpi=150)
        print("saved", out)

        if {DEFAULT, ADAPTIVE} <= set(sub["config"]) and sub["config"].str.startswith("Fixed").any():
            plot_comparison(sub, it)

    plot_minbe_traces()


if __name__ == "__main__":
    main()
