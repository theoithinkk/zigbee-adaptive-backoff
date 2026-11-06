# Zigbee Star Network Prototype (NSCOM03 S40B — Milestone 2 Code Demo)

ns-3 prototype for *"Improving Zigbee Network Reliability Through Adaptive Backoff in IEEE 802.15.4 CSMA/CA"* (Campo, Morgan, Garcia).

Tested on **ns-3.44** (lr-wpan module), Linux.

## Files

| File | What it does |
|---|---|
| `scratch/zigbee-star.cc` | The simulation: 1 coordinator + N sensors on a 10 m circle, unslotted CSMA/CA, 20-byte packets with ACK, fixed or adaptive `macMinBE`. Prints one CSV row per run. |
| `run_experiments.py` | Runs the sweeps from the proposal (baseline, minBE 1–5, adaptive, sensitivity), 10 RNG runs each, in parallel. |
| `plot_results.py` | Averages the runs, computes 95% CIs (t-distribution) and Welch t-tests, saves `results/summary.csv`, `results/significance.csv` and line graphs. |
| `results/` | Baseline + adaptive results from our 300 s × 10-run sweep. |

## Setup

See [Getting started in the README](README.md#getting-started): the `apt` packages, building ns-3.44, copying the scenario, scripts and `results/` into `~/ns3`, and updating an existing setup.

## Run one simulation

```bash
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --minBE=3 --run=1"
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --mode=adaptive --window=10 --hi=0.5 --lo=0.2"
./ns3 run "zigbee-star --mode=adaptive --nSensors=30 --interval=0.1 --traceBE=$PWD/minbe.csv"  # log every minBE change
./ns3 run "zigbee-star --PrintHelp"     # list all parameters
```

`--traceBE` writes `time_s,sensor,minBE`: one row per sensor at t=0 (the start value), then one row per change. It only logs; the CSV result row is identical with or without it. Use an absolute path, since `./ns3 run` may not run from the folder you're in.

## Run the experiments + graphs

```bash
python3 run_experiments.py baseline      # Experiment 1 (default settings, N = 5, 10, 20, 25, 30, 35, 40, 50)
python3 run_experiments.py minbe         # Experiment 2 (macMinBE = 1..5)
python3 run_experiments.py adaptive      # Experiment 3 (adaptive rule)
python3 run_experiments.py sensitivity   # Experiment 4 (W = 5/10/20, thresholds ±0.1)
python3 run_experiments.py trace         # minBE over time: 1 adaptive run each for (N, interval) in TRACE_CASES
python3 plot_results.py
```

Add `--runs 3 --simTime 60` for a quick check. Add `--N 25 35` to run only those N values and merge them into the existing CSVs.

## How it maps to the proposal

| Proposal item | Where in the code |
|---|---|
| Star topology, 10 m circle | `main()` — mobility loop |
| 2.4 GHz ch. 11, 250 kbps | lr-wpan defaults (O-QPSK, page 0, channel 11) |
| macMinBE=3, macMaxBE=5, macMaxCSMABackoffs=4, macMaxFrameRetries=3 | command-line defaults, set on each device's `LrWpanCsmaCa`/`LrWpanMac` |
| Randomized start within first interval | `UniformRandomVariable` start times |
| 300 s, 10 runs, different RNG run | `--simTime`, `--run` (`RngSeedManager::SetRun`) |
| PDR | unique packets received at coordinator ÷ packets generated |
| Average delay | time stamp written into the payload at send, read at coordinator |
| Retransmissions | `MacSentPkt` trace (number of frame transmissions per packet − 1) |
| Channel access failures | `McpsDataConfirm` status `CHANNEL_ACCESS_FAILURE` |

### Adaptive rule — the lr-wpan hook (answers the "check lr-wpan hooks" task)

ns-3 does **not** expose a trace for each CCA result, but no module change is needed. Each device's PHY reports CCA results through `PlmeCcaConfirmCallback`, which normally points straight at `LrWpanCsmaCa::PlmeCcaConfirm`. The scenario re-points it to a wrapper (`CcaWrapper`) that:

1. records BUSY/IDLE in that sensor's last-W history,
2. if busy > 50% → `macMinBE + 1`; if busy < 20% → `macMinBE − 1` (clamped to [0, macMaxBE]),
3. forwards the result to the original `PlmeCcaConfirm`, so CSMA/CA behaves normally.

The new `macMinBE` applies from the next CSMA/CA run. After each change, the history is cleared so the next change needs 10 new CCAs as evidence (stops minBE from jumping every attempt).

## Notes / assumptions

- Packets created after `simTime` are not counted. The simulation runs 1 extra second so packets already in flight can still arrive.
- If an ACK is lost, the coordinator can receive the same packet twice. Duplicates are ignored, using (source, sequence number).
- MAC queues are unlimited (ns-3 default). Under heavy load, queued packets add to the delay.
- A packet can show up as `no_ack` (sensor never got the ACK) and still count as delivered, because the data frame did reach the coordinator.

## Results (300 s, 10 runs, mean ± 95% CI) — see `results/plots/`

| Traffic | N | PDR default | PDR adaptive | Delay default (ms) | Delay adaptive (ms) | CA failures default | CA failures adaptive |
|---|---|---|---|---|---|---|---|
| light 1 s | 5 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.62 | 1.56 | 0 | 0 |
| light 1 s | 10 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.71 | 1.65 | 0 | 0 |
| light 1 s | 20 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.77 | 1.68 | 0 | 0 |
| light 1 s | 25 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.85 | 1.73 | 0 | 0 |
| light 1 s | 30 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.84 | 1.73 | 0 | 0 |
| light 1 s | 35 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.87 | 1.73 | 0 | 0 |
| light 1 s | 40 | 100.00 ± 0.01 | 99.99 ± 0.01 | 2.95 | 1.82 | 0 | 1 |
| light 1 s | 50 | 100.00 ± 0.00 | 99.99 ± 0.01 | 3.06 | 1.91 | 1 | 1 |
| heavy 0.1 s | 5 | 100.00 ± 0.00 | 100.00 ± 0.00 | 2.79 | 1.58 | 0 | 0 |
| heavy 0.1 s | 10 | 99.97 ± 0.03 | 99.97 ± 0.03 | 3.44 | 2.17 | 8 | 9 |
| heavy 0.1 s | 20 | 99.33 ± 0.32 | 99.66 ± 0.17 | 4.98 | 4.03 | 393 | 211 |
| heavy 0.1 s | 25 | 97.36 ± 1.08 | 98.81 ± 0.38 | 6.53 | 7.39 | 1936 | 885 |
| heavy 0.1 s | 30 | 94.41 ± 1.02 | 96.01 ± 0.34 | 7.65 | 12.25 | 4892 | 3538 |
| heavy 0.1 s | 35 | 89.43 ± 1.37 | 90.29 ± 0.63 | 9.18 | 16.00 | 10780 | 9949 |
| heavy 0.1 s | 40 | 81.69 ± 0.84 | 82.43 ± 0.42 | 10.72 | 18.43 | 21429 | 20524 |
| heavy 0.1 s | 50 | 66.61 ± 0.50 | 66.94 ± 0.28 | 12.92 | 21.50 | 48548 | 47979 |

What the results show:
- The baseline matches the hypothesis. Under heavy traffic, PDR falls from 100% (N=5) to about 67% (N=50), delay goes up, and channel access failures take over as the main cause of loss.
- Small networks and light traffic: the adaptive rule cuts delay by about 40% (minBE drops toward 0–2).
- Heavy traffic, N=20–30: the adaptive rule raises PDR a little (+1.5 points at N=25, +1.6 at N=30), with fewer retransmissions and channel access failures. Its delay passes the default at N≈25.
- Heavy traffic, N ≥ 35: the channel is saturated, so no backoff setting helps much. The rule pushes minBE up to macMaxBE (5), which adds delay but barely changes PDR.

## Best fixed minBE vs adaptive — see `comparison_interval_*.png`

"Best fixed" picks, at each N and for each metric separately, whichever of minBE = 1–5 scored best. That's an oracle: nobody could choose it without running all five first, so it is the toughest fair baseline for the adaptive rule. The p-values are Welch t-tests of adaptive against that best fixed value.

| Traffic | N | PDR best fixed (minBE) | PDR adaptive | p | Delay best fixed (minBE) | Delay adaptive | p |
|---|---|---|---|---|---|---|---|
| light 1 s | 5 | 100.00 (3) | 100.00 | 1.000 | 1.66 (1) | 1.56 | < 0.001 |
| light 1 s | 10 | 100.00 (3) | 100.00 | 1.000 | 1.73 (1) | 1.65 | 0.220 |
| light 1 s | 20 | 100.00 (3) | 100.00 | 1.000 | 1.76 (1) | 1.68 | 0.151 |
| light 1 s | 25 | 100.00 (4) | 100.00 | 0.343 | 1.81 (1) | 1.73 | 0.284 |
| light 1 s | 30 | 100.00 (4) | 100.00 | 0.343 | 1.80 (1) | 1.73 | 0.103 |
| light 1 s | 35 | 100.00 (4) | 100.00 | 1.000 | 1.81 (1) | 1.73 | 0.132 |
| light 1 s | 40 | 100.00 (5) | 99.99 | 0.144 | 1.88 (1) | 1.82 | 0.295 |
| light 1 s | 50 | 100.00 (5) | 99.99 | 0.423 | 1.95 (1) | 1.91 | 0.576 |
| heavy 0.1 s | 5 | 100.00 (3) | 100.00 | 1.000 | 1.72 (1) | 1.58 | 0.112 |
| heavy 0.1 s | 10 | 99.97 (4) | 99.97 | 0.818 | 2.16 (1) | 2.17 | 0.969 |
| heavy 0.1 s | 20 | 99.51 (5) | 99.66 | 0.207 | 2.98 (1) | 4.03 | 0.049 |
| heavy 0.1 s | 25 | 98.09 (5) | 98.81 | 0.036 | 3.87 (1) | 7.39 | < 0.001 |
| heavy 0.1 s | 30 | 95.22 (5) | 96.01 | 0.020 | 4.27 (1) | 12.25 | < 0.001 |
| heavy 0.1 s | 35 | 90.17 (5) | 90.29 | 0.784 | 4.70 (1) | 16.00 | < 0.001 |
| heavy 0.1 s | 40 | 82.40 (5) | 82.43 | 0.909 | 5.34 (1) | 18.43 | < 0.001 |
| heavy 0.1 s | 50 | 66.85 (5) | 66.94 | 0.620 | 6.15 (1) | 21.50 | < 0.001 |

- Light traffic: adaptive matches the best fixed delay (minBE=1) without being told the load; it is significantly faster only at N=5.
- Heavy traffic: adaptive gets PDR at least as high as the best fixed minBE at every N (significantly higher at N=25 and 30), but from N=20 its delay is significantly higher, 2–3.5× the best fixed delay from N=30.
- The best minBE depends on the metric: minBE=1 always gives the lowest delay, while minBE=5 gives the highest PDR under heavy load. The rule only follows channel busyness, so under heavy load it settles on the PDR-friendly end.

## Significance — see `results/significance.csv`

Each cell is a two-sided Welch t-test over the 10 runs (adaptive vs the other setting). Runs with no spread at all, such as PDR 100% in every run, are compared exactly. For p < 0.05 the Holm-corrected p over all 128 tests is shown in brackets; Holm controls the chance of any false positive across the whole table.

| Traffic | N | PDR vs default | PDR vs best | Delay vs default | Delay vs best | CA failures vs default |
|---|---|---|---|---|---|---|
| light | 5 | 1.000 | 1.000 | < 0.001 (Holm < 0.001) | < 0.001 (Holm < 0.001) | 1.000 |
| light | 10 | 1.000 | 1.000 | < 0.001 (Holm < 0.001) | 0.220 | 1.000 |
| light | 20 | 1.000 | 1.000 | < 0.001 (Holm < 0.001) | 0.151 | 1.000 |
| light | 25 | 0.168 | 0.343 | < 0.001 (Holm < 0.001) | 0.284 | 1.000 |
| light | 30 | 0.557 | 0.343 | < 0.001 (Holm < 0.001) | 0.103 | 0.168 |
| light | 35 | 0.168 | 1.000 | < 0.001 (Holm < 0.001) | 0.132 | 1.000 |
| light | 40 | 0.387 | 0.144 | < 0.001 (Holm < 0.001) | 0.295 | 0.126 |
| light | 50 | 0.507 | 0.423 | < 0.001 (Holm < 0.001) | 0.576 | 0.263 |
| heavy | 5 | 1.000 | 1.000 | < 0.001 (Holm < 0.001) | 0.112 | 1.000 |
| heavy | 10 | 0.977 | 0.818 | < 0.001 (Holm 0.003) | 0.969 | 0.899 |
| heavy | 20 | 0.063 | 0.207 | 0.076 | 0.049 (Holm 1.000) | 0.085 |
| heavy | 25 | 0.015 (Holm 1.000) | 0.036 (Holm 1.000) | 0.135 | < 0.001 (Holm 0.003) | 0.016 (Holm 1.000) |
| heavy | 30 | 0.007 (Holm 0.678) | 0.020 (Holm 1.000) | < 0.001 (Holm < 0.001) | < 0.001 (Holm < 0.001) | 0.007 (Holm 0.760) |
| heavy | 35 | 0.219 | 0.784 | < 0.001 (Holm < 0.001) | < 0.001 (Holm < 0.001) | 0.250 |
| heavy | 40 | 0.099 | 0.909 | < 0.001 (Holm < 0.001) | < 0.001 (Holm < 0.001) | 0.102 |
| heavy | 50 | 0.207 | 0.620 | < 0.001 (Holm < 0.001) | < 0.001 (Holm < 0.001) | 0.156 |

How to read it:
- **Survives Holm (strong):** light-traffic delay vs default at every N; heavy-traffic delay at N=5–10 (adaptive faster) and N ≥ 30 (adaptive slower).
- **p < 0.05 but not after Holm (weak):** the heavy-traffic PDR and channel-access gains at N=25 and 30. Report them as small gains that need more runs to confirm.
- **No significant difference:** PDR at light load, and PDR at N ≥ 35 under heavy load.

## minBE over time — see `minbe_over_time.png`

Run 1 of the adaptive rule, from `results/traces/`:

- N=20, light: every sensor steps 3 → 2 → 1 → 0 within about 30 s and stays at 0. That's 60 changes in total (3 per sensor).
- N=10, heavy: drops quickly, then keeps moving; the mean hovers around 0.5, while individual sensors jump between 0 and 4.
- N=30, heavy: rises to 4–5 within a few seconds, mean ≈ 4.6, with constant 4↔5 switching (2,964 changes in 300 s).
- N=50, heavy: goes straight to macMaxBE (5) and stays there (192 changes).

So the rule does respond to load, in the direction the design intends. The heavy-traffic delay cost above comes from it settling at minBE 4–5.
