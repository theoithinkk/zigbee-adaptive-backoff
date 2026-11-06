<div align="center">

# zigbee-adaptive-backoff

**Does an adaptive CSMA/CA backoff rule beat the IEEE 802.15.4 defaults as a Zigbee network grows?**

![ns-3](https://img.shields.io/badge/ns--3-3.44-blue) ![lr-wpan](https://img.shields.io/badge/module-lr--wpan-blue) ![C++](https://img.shields.io/badge/C%2B%2B-17-00599C) ![Python](https://img.shields.io/badge/Python-3-3776AB)

[Overview](#overview) · [Getting started](#getting-started) · [Running experiments](#running-experiments) · [Results](#results) · [Demo script](#demo-script)

NSCOM03 – S40B · De La Salle University · Campo, Morgan, Garcia

</div>

## Overview

An ns-3 simulation of a Zigbee-style star network: 1 coordinator and N sensors (5–50) on a 10 m circle. It uses 2.4 GHz channel 11 at 250 kbps with unslotted CSMA/CA. Each sensor sends a 20-byte packet with ACK every 1 s (light traffic) or 0.1 s (heavy traffic).

**Adaptive rule:** each sensor looks only at its own last 10 channel checks (CCAs):

| Busy fraction | Action |
|---|---|
| > 50% | `macMinBE + 1` (wait longer) |
| < 20% | `macMinBE − 1` (wait less) |
| otherwise | keep, clamped to `[0, macMaxBE]` |

**Metrics:** packet delivery ratio (PDR), average delay, retransmissions and channel access failures. Each is the mean of 10 runs with a 95% confidence interval.

> [!NOTE]
> The lr-wpan module is **not modified**. The scenario re-points the PHY's `PlmeCcaConfirm` callback to a small wrapper, `CcaWrapper`. The wrapper records BUSY/IDLE, applies the rule, and then forwards the result to the normal `LrWpanCsmaCa`.

### How it fits together

```
run_experiments.py ──./ns3 run──► scratch/zigbee-star.cc ──1 CSV row──► results/*.csv ──► plot_results.py ──► results/plots/
  (4 sweeps × 10 runs)             (one 300 s simulation)                                    (mean ± 95% CI)
```

| File | Purpose |
|---|---|
| `scratch/zigbee-star.cc` | The ns-3 scenario: topology, traffic, adaptive hook, counters. Prints one CSV row per run. |
| `run_experiments.py` | Parameter sweeps from the proposal, run in parallel. |
| `plot_results.py` | Averages runs, computes 95% CIs and significance tests, writes `results/summary.csv`, `results/significance.csv` and graphs. |
| `results/` | CSVs, plots and `traces/` (minBE-over-time logs). |
| `zs` | Runs one simulation and prints its CSV row as labelled lines, for demos. |
| `DETAILS.md` | Full notes: code-to-proposal mapping, assumptions, detailed results. |

## Getting started

### Prerequisites

- Linux, or Windows with **WSL** (Ubuntu)
- Build tools and Python packages, installed with `apt`:

```bash
sudo apt update && sudo apt install -y g++ cmake ninja-build git python3 python3-pandas python3-scipy python3-matplotlib
```

> [!TIP]
> On Windows, open Windows Terminal and enter Ubuntu by name: `wsl -d Ubuntu-26.04`. If you have Docker Desktop, its distro can be the default one, and plain `wsl` then fails with `execvpe(bash) failed`.

> [!NOTE]
> Use `apt`, not `pip install`, for the Python packages. Recent Ubuntu marks its Python as externally managed, and `pip install` stops with `error: externally-managed-environment`.

### Install ns-3 and the scenario

```bash
git clone --branch ns-3.44 https://gitlab.com/nsnam/ns-3-dev.git ~/ns3 && cd ~/ns3
./ns3 configure --enable-modules=lr-wpan -d optimized --disable-examples --disable-tests
./ns3 build
```

Copy this repository's scenario, scripts and saved results into the ns-3 folder:

```bash
git clone https://github.com/theoithinkk/zigbee-adaptive-backoff ~/zigbee-adaptive-backoff
cd ~/ns3
cp ~/zigbee-adaptive-backoff/scratch/zigbee-star.cc scratch/
cp ~/zigbee-adaptive-backoff/*.py ~/zigbee-adaptive-backoff/zs .
cp -r ~/zigbee-adaptive-backoff/results .
chmod +x zs
./ns3 build zigbee-star
```

`results/` holds the saved 10-run results, so `python3 plot_results.py` can redraw the graphs without re-running any simulation.

### Update an existing setup

Get the latest version of the repository, then copy it into `~/ns3` again:

```bash
git -C ~/zigbee-adaptive-backoff pull
cd ~/ns3
cp ~/zigbee-adaptive-backoff/scratch/zigbee-star.cc scratch/
cp ~/zigbee-adaptive-backoff/*.py ~/zigbee-adaptive-backoff/zs . && chmod +x zs
./ns3 build zigbee-star
```

> [!WARNING]
> Add `cp -r ~/zigbee-adaptive-backoff/results .` only if you want the repository's results. It replaces any results you made yourself in `~/ns3/results`.

### Run one simulation

```bash
./ns3 run "zigbee-star --nSensors=20 --interval=0.1"                   # default settings (minBE = 3)
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --mode=adaptive"   # adaptive rule
./ns3 run "zigbee-star --header"                                       # CSV column names
./ns3 run "zigbee-star --PrintHelp"                                    # all parameters
```

| Flag | Default | Meaning |
|---|---|---|
| `--nSensors` | 10 | Number of sensors (N) |
| `--interval` | 1.0 | Sending interval per sensor, in seconds |
| `--mode` | `fixed` | `fixed` or `adaptive` |
| `--minBE` / `--maxBE` | 3 / 5 | Backoff exponent limits (adaptive: start value / ceiling) |
| `--maxBackoffs` / `--maxRetries` | 4 / 3 | `macMaxCSMABackoffs` / `macMaxFrameRetries` |
| `--window` `--hi` `--lo` | 10, 0.5, 0.2 | Adaptive window size and thresholds |
| `--simTime` / `--run` | 300 / 1 | Simulated seconds / RNG run number |
| `--traceBE=<file>` | – | Log every minBE change as `time_s,sensor,minBE` (use an absolute path) |

## Running experiments

```bash
python3 run_experiments.py baseline      # 1. default settings, N = 5..50
python3 run_experiments.py minbe         # 2. macMinBE = 1..5
python3 run_experiments.py adaptive      # 3. adaptive rule
python3 run_experiments.py sensitivity   # 4. W = 5/10/20, thresholds ±0.1
python3 run_experiments.py trace         # minBE over time, one run per case
python3 run_experiments.py all           # everything (2,240 simulations + traces)
python3 plot_results.py                  # graphs -> results/plots/
```

Options: `--runs 10 --simTime 300 --jobs <cpus> --ns3 ./ns3`. Add `--runs 3 --simTime 60` for a quick check.

To add network sizes without re-running the rest, pass `--N`. Only those N values run, and their rows are merged into the existing `results/<name>.csv`:

```bash
python3 run_experiments.py minbe --N 25 35
```

> [!WARNING]
> A sweep without `--N` **overwrites** `results/<name>.csv`. Back up the full 10-run results first: `cp -r results results_backup`.

## Results

Every metric panel is labelled **↑ Higher is better** (PDR) or **↓ Lower is better** (delay, retransmissions, channel access failures).

| File | Shows |
|---|---|
| `metrics_interval_*.png` | Every configuration: default, fixed minBE 1–5, adaptive and sensitivity variants |
| `comparison_interval_*.png` | Default vs **best fixed minBE** (best of 1–5 per N and metric) vs adaptive, with significance marks |
| `minbe_over_time.png` | Each sensor's `macMinBE` during one adaptive run, plus the mean |
| `results/significance.csv` | p-values for adaptive vs default and vs best fixed, per traffic level, N and metric (Welch t-test, raw and Holm-corrected) |

On the comparison graphs, red marks under an adaptive point show a significant difference: **†** vs the default, **\*** vs the best fixed minBE (single mark p < 0.05, double p < 0.01).

Key findings (N = 5, 10, 20, 25, 30, 35, 40, 50; 300 s × 10 runs):

- **Light traffic:** the adaptive rule cuts delay by about 40% against the default at every N (2.62 → 1.56 ms at N = 5; p < 0.001, also after Holm correction). Against the best fixed minBE (1) it is only significantly faster at N = 5.
- **Heavy traffic, N = 25–30:** the only significant PDR gains. N = 25: 97.4 → 98.8% (p = 0.015 vs default, 0.036 vs best fixed). N = 30: 94.4 → 96.0% (p = 0.007 and 0.020). Channel access failures fall too. These gains do not survive the strict Holm correction over all 128 tests.
- **Heavy traffic, delay:** the crossover is at N ≈ 25. From N = 30 the rule is significantly slower than the default and the best fixed value (12.3 vs 7.7 ms at N = 30; p < 0.001, also after Holm), because it settles at minBE 4–5.
- **Heavy traffic, N ≥ 35:** the channel is saturated. PDR does not differ significantly between settings (p ≥ 0.09).

See [DETAILS.md](DETAILS.md) for full tables and the best-fixed comparison.

## Demo script

### Research question

How does the number of devices affect IEEE 802.15.4 CSMA/CA performance, and can an adaptive backoff rule do better than the default fixed settings?

### Hypothesis

- **Default settings:** as N grows, PDR drops and delay rises. More sensors pick the same backoff and the channel is busy more often.
- **Adaptive rule:** keeps PDR higher in large networks (it raises minBE when the channel is busy) and delay low in small networks (it lowers minBE when the channel is free).

### Why this approach

- **Single-hop star, all sensors in range, no interference:** the only variable is channel contention, which is what backoff controls.
- **IEEE default MAC values:** the baseline is what real devices use.
- **minBE 1–5 sweep:** shows the best any fixed value can do at each N, a hard baseline for the rule.
- **Rule uses only each sensor's own channel checks:** no messages between devices, and no change to ns-3 (one re-pointed callback).
- **10 runs per setting, mean ± 95% CI, Welch t-tests:** separates real differences from random variation.

### Commands

Open Windows Terminal and enter the ns-3 folder in WSL:

```bash
wsl -d Ubuntu-26.04
```
```bash
cd ~/ns3
```

1. **Build the scenario.** Compiles `scratch/zigbee-star.cc`.
   ```bash
   ./ns3 build zigbee-star
   ```
2. **Get the `zs` helper (once).** Each run prints one CSV row. `./zs` runs the scenario and prints each value on its own line with a plain-English label, its unit, and the CSV column name in brackets.
   ```bash
   git -C ~/zigbee-adaptive-backoff pull && cp ~/zigbee-adaptive-backoff/zs . && chmod +x zs
   ```
3. **List the parameters.** Every proposal setting (N, interval, minBE, retries, window, thresholds) is a command-line flag.
   ```bash
   ./ns3 run "zigbee-star --PrintHelp"
   ```
4. **Baseline: default minBE 3, 30 sensors, heavy traffic (0.1 s).**
   ```bash
   ./zs --nSensors=30 --interval=0.1
   ```
   Result: delivery ratio 95.5289 %, average delay 7.1812 ms, 3914 dropped (channel busy).
5. **Same network with the adaptive rule.**
   ```bash
   ./zs --nSensors=30 --interval=0.1 --mode=adaptive
   ```
   Result: delivery ratio 96.2411 %, average delay 12.3048 ms, 3358 dropped (channel busy), average minBE 4.6219.
6. **Small network, light traffic: default, then adaptive.**
   ```bash
   ./zs --nSensors=5 --interval=1
   ```
   ```bash
   ./zs --nSensors=5 --interval=1 --mode=adaptive
   ```
   Result: delivery ratio 100 % in both. Average delay 2.6038 → 1.5625 ms; average minBE 0.1947.
7. **Re-make the graphs from the saved results.** Averages the 10 runs per setting in `results/*.csv` and redraws all 5 graphs plus `results/summary.csv`. Takes a few seconds.
   ```bash
   python3 plot_results.py
   ```
8. **Open the graphs.**
   ```bash
   explorer.exe results/plots
   ```
9. **Optional: re-run every experiment, then redraw.** Runs all 2,240 simulations (10 runs × 300 s per setting) plus the minBE traces. This takes a long time and overwrites `results/*.csv`, so back up first. `all` includes the minBE 1–5 sweep, which the two `comparison_*` graphs need.
   ```bash
   cp -r results results_backup
   ```
   ```bash
   python3 run_experiments.py all
   ```
   ```bash
   python3 plot_results.py
   ```

> [!NOTE]
> Live runs use RNG run 1, so their numbers differ slightly from the 10-run means in the graphs. `./zs` skips the build (`--no-build`), so run step 1 again after you change the code.

### Interpreted results

| Graph | What it shows |
|---|---|
| `metrics_interval_1p0.png` | Light traffic: every setting delivers > 99.9% (zoomed y-axis), so the difference is delay, which rises with minBE. The adaptive variants are on the fastest line. |
| `comparison_interval_1p0.png` | Light traffic: adaptive is significantly faster than the default at every N (†† marks), about 40%. It matches the best fixed minBE (1); the gap is significant only at N = 5. |
| `metrics_interval_0p1.png` | Heavy traffic: PDR holds to N = 20, then falls to about 66% at N = 50 for every setting; almost all losses are channel access failures. The adaptive variants overlap, so the result does not depend on the exact window or thresholds. |
| `comparison_interval_0p1.png` | Heavy traffic: adaptive delivers significantly more at N = 25 and 30 (+1.5 and +1.6 points over the default). From N = 30 its delay is significantly higher than both baselines (2–3.5× the best fixed delay), because it settles at minBE 4–5. |
| `minbe_over_time.png` | The rule follows the load: light traffic takes minBE down to 0 in about 30 s, heavy traffic pushes it to 4–5, and at N = 50 it stays at 5. |

**Answer:**
- The hypothesis holds for the defaults: delivery drops and delay rises with N.
- The adaptive rule significantly cuts delay at light load (vs the default) and raises delivery at N = 25–30 under heavy load, but significantly costs delay from N = 30.
- The delivery gain is small and does not survive a strict multiple-test correction; the delay effects do.
- At N ≥ 35 with heavy traffic the channel is saturated, and no backoff setting helps.

## Status

- [x] Star network and baseline (Milestone 2)
- [x] Adaptive rule (no lr-wpan changes needed)
- [x] minBE 1–5 sweep and sensitivity test
- [x] Best-fixed comparison and minBE-over-time trace
- [ ] Final paper and presentation (Milestone 3)
