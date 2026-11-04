# Zigbee Star Network Prototype (NSCOM03 S40B — Milestone 2 Code Demo)

ns-3 prototype for *"Improving Zigbee Network Reliability Through Adaptive Backoff in IEEE 802.15.4 CSMA/CA"* (Campo, Morgan, Garcia).

Tested on **ns-3.44** (lr-wpan module), Linux.

## Files

| File | What it does |
|---|---|
| `scratch/zigbee-star.cc` | The simulation: 1 coordinator + N sensors on a 10 m circle, unslotted CSMA/CA, 20-byte packets with ACK, fixed or adaptive `macMinBE`. Prints one CSV row per run. |
| `run_experiments.py` | Runs the sweeps from the proposal (baseline, minBE 1–5, adaptive, sensitivity), 10 RNG runs each, in parallel. |
| `plot_results.py` | Averages the runs, computes 95% CIs (t-distribution), saves `results/summary.csv` and line graphs. |
| `results/` | Baseline + adaptive results from our 300 s × 10-run sweep. |

## Setup

```bash
git clone --branch ns-3.44 https://gitlab.com/nsnam/ns-3-dev.git ns3
cd ns3
./ns3 configure --enable-modules=lr-wpan -d optimized --disable-examples --disable-tests
./ns3 build
cp /path/to/prototype/scratch/zigbee-star.cc scratch/
cp /path/to/prototype/*.py .
pip install pandas scipy matplotlib
```

## Run one simulation

```bash
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --minBE=3 --run=1"
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --mode=adaptive --window=10 --hi=0.5 --lo=0.2"
./ns3 run "zigbee-star --PrintHelp"     # list all parameters
```

## Run the experiments + graphs

```bash
python3 run_experiments.py baseline      # Experiment 1 (default settings, N = 5..50)
python3 run_experiments.py minbe         # Experiment 2 (macMinBE = 1..5)
python3 run_experiments.py adaptive      # Experiment 3 (adaptive rule)
python3 run_experiments.py sensitivity   # Experiment 4 (W = 5/10/20, thresholds ±0.1)
python3 plot_results.py
```

Add `--runs 3 --simTime 60` for a quick check.

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

## Preliminary results (300 s, 10 runs, mean ± 95% CI) — see `results/plots/`

| Traffic | N | PDR default | PDR adaptive | Delay default (ms) | Delay adaptive (ms) |
|---|---|---|---|---|---|
| light 1 s | 5 | 100.00 | 100.00 | 2.62 | 1.56 |
| light 1 s | 50 | 100.00 | 99.99 | 3.06 | 1.91 |
| heavy 0.1 s | 5 | 100.00 | 100.00 | 2.79 | 1.58 |
| heavy 0.1 s | 20 | 99.33 | 99.66 | 4.98 | 4.03 |
| heavy 0.1 s | 30 | 94.41 ± 1.02 | 96.01 ± 0.34 | 7.65 | 12.25 |
| heavy 0.1 s | 50 | 66.61 | 66.94 | 12.92 | 21.50 |

What we see so far:
- The baseline matches the hypothesis. Under heavy traffic, PDR falls from 100% (N=5) to about 67% (N=50), delay goes up, and channel access failures take over as the main cause of loss.
- Small networks: the adaptive rule cuts delay by about 40% (minBE drops toward 0–2).
- Mid-size networks (N=20–30, heavy): the adaptive rule raises PDR a little (+1.6 points at N=30), with fewer retransmissions and channel access failures, but delay is higher.
- N ≥ 40, heavy: the channel is saturated, so no backoff setting helps much. The adaptive rule pushes minBE up to macMaxBE (5), which adds delay but barely changes PDR. Next, compare it with the *best fixed* minBE (`minbe` sweep), and maybe also adapt macMaxBE or macMaxCSMABackoffs.
