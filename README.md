# zigbee-adaptive-backoff

ns-3 simulation of an IEEE 802.15.4 (Zigbee-style) star network, testing whether an **adaptive CSMA/CA backoff rule** beats the default fixed settings as the network grows.

NSCOM03 – S40B, De La Salle University · Campo, Morgan, Garcia

## What it does

- 1 coordinator + N sensors (5–50) on a 10 m circle, 2.4 GHz, 250 kbps, unslotted CSMA/CA
- Each sensor sends a 20-byte packet (with ACK) every 1 s (light) or 0.1 s (heavy)
- **Adaptive rule:** each sensor looks at its last 10 channel checks:
  - busy > 50% → `macMinBE + 1` (wait longer)
  - busy < 20% → `macMinBE − 1` (wait less)
- Metrics: packet delivery ratio, average delay, retransmissions, channel access failures

## Quick start

```bash
# 1. Build ns-3 with lr-wpan
git clone --branch ns-3.44 https://gitlab.com/nsnam/ns-3-dev.git ns3 && cd ns3
./ns3 configure --enable-modules=lr-wpan -d optimized
./ns3 build

# 2. Add this project
cp <this-repo>/scratch/zigbee-star.cc scratch/
cp <this-repo>/*.py .
pip install pandas scipy matplotlib

# 3. Run
./ns3 run "zigbee-star --nSensors=20 --interval=0.1"                    # default settings
./ns3 run "zigbee-star --nSensors=20 --interval=0.1 --mode=adaptive"    # adaptive rule
python3 run_experiments.py baseline    # or: minbe | adaptive | sensitivity | all
python3 plot_results.py                # graphs -> results/plots/
```

## Repo layout

```
scratch/zigbee-star.cc   simulation scenario
run_experiments.py       parameter sweeps (10 runs each)
plot_results.py          mean ± 95% CI graphs + summary.csv
results/                 CSVs and plots
DETAILS.md               full notes: code-to-proposal mapping, assumptions, preliminary results
```

## Status

- [x] Star network + baseline (Milestone 2)
- [x] Adaptive rule (no changes to the lr-wpan module needed)
- [ ] minBE 1–5 sweep, sensitivity test
- [ ] Final paper
