#!/usr/bin/env python3
"""
Runs the zigbee-star scenario sweeps from the proposal and writes results/*.csv.

Usage (from the ns-3 root folder, after copying scratch/zigbee-star.cc in):
    python3 run_experiments.py baseline            # default settings, N = 5..50
    python3 run_experiments.py minbe               # macMinBE = 1..5
    python3 run_experiments.py adaptive            # adaptive rule
    python3 run_experiments.py sensitivity         # adaptive with nearby W / thresholds
    python3 run_experiments.py all
Options:
    --runs 10 --simTime 300 --jobs 4 --ns3 ./ns3
"""
import argparse, itertools, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

N_LIST = [5, 10, 20, 30, 40, 50]
INTERVALS = [1.0, 0.1]  # light, heavy


def experiments(name):
    if name == "baseline":
        for n, it in itertools.product(N_LIST, INTERVALS):
            yield dict(mode="fixed", nSensors=n, interval=it, minBE=3)
    elif name == "minbe":
        for be, n, it in itertools.product([1, 2, 3, 4, 5], N_LIST, INTERVALS):
            yield dict(mode="fixed", nSensors=n, interval=it, minBE=be)
    elif name == "adaptive":
        for n, it in itertools.product(N_LIST, INTERVALS):
            yield dict(mode="adaptive", nSensors=n, interval=it, minBE=3)
    elif name == "sensitivity":
        variants = [dict(window=w) for w in (5, 10, 20)] + \
                   [dict(hi=h, lo=l) for h, l in ((0.4, 0.2), (0.6, 0.2), (0.5, 0.1), (0.5, 0.3))]
        for v, n, it in itertools.product(variants, N_LIST, INTERVALS):
            yield dict(mode="adaptive", nSensors=n, interval=it, minBE=3, **v)


def run_one(ns3, params, run, simTime):
    args = " ".join(f"--{k}={v}" for k, v in params.items())
    cmd = [ns3, "run", "--no-build", f"zigbee-star {args} --run={run} --simTime={simTime}"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        return None
    return out.stdout.strip().splitlines()[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment", choices=["baseline", "minbe", "adaptive", "sensitivity", "all"])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--simTime", type=float, default=300)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--ns3", default="./ns3")
    a = ap.parse_args()

    subprocess.run([a.ns3, "build", "zigbee-star"], check=True, capture_output=True)
    header = subprocess.run([a.ns3, "run", "--no-build", "zigbee-star --header"],
                            capture_output=True, text=True).stdout.strip().splitlines()[-1]
    os.makedirs("results", exist_ok=True)

    names = ["baseline", "minbe", "adaptive", "sensitivity"] if a.experiment == "all" else [a.experiment]
    for name in names:
        jobs = [(p, r) for p in experiments(name) for r in range(1, a.runs + 1)]
        print(f"[{name}] {len(jobs)} simulations ...", flush=True)
        with ThreadPoolExecutor(a.jobs) as ex:
            rows = list(ex.map(lambda j: run_one(a.ns3, j[0], j[1], a.simTime), jobs))
        path = f"results/{name}.csv"
        with open(path, "w") as f:
            f.write(header + "\n")
            f.writelines(r + "\n" for r in rows if r)
        print(f"[{name}] wrote {path}")


if __name__ == "__main__":
    main()
