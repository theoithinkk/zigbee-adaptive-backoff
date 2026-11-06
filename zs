#!/usr/bin/env bash
# zs: run zigbee-star once and print the CSV row as labelled lines.
# Usage (from the ns-3 folder): ./zs --nSensors=30 --interval=0.1 [--mode=adaptive ...]
set -euo pipefail
row=$(./ns3 run --no-build "zigbee-star $*" | tail -1)
echo "$row" | awk -F, '
function line(label, i, unit) { printf "  %-46s %-16s %s %s\n", label, "[" H[i] "]", $i, unit }
BEGIN {
  split("mode,N,interval,minBE,window,hi,lo,run,generated,delivered,pdr,avg_delay_ms,retx_total,retx_packets,ca_fail,no_ack,cca_busy_frac,be_changes,avg_minBE", H, ",")
}
{
  ad = ($1 == "adaptive")
  print "Settings"
  line("Backoff mode (fixed or adaptive rule)", 1, "")
  line("Sensors (N)", 2, "")
  line("Send interval per sensor", 3, "s")
  line(ad ? "Starting macMinBE" : "macMinBE (fixed)", 4, "")
  if (ad) {
    line("Rule window: last CCAs looked at", 5, "")
    line("Rule: raise minBE if busy fraction >", 6, "")
    line("Rule: lower minBE if busy fraction <", 7, "")
  }
  line("Random-number run", 8, "")
  print "Results (300 s unless --simTime is set)"
  line("Packets sent by all sensors", 9, "")
  line("Packets received by coordinator (unique)", 10, "")
  line("Packet delivery ratio (received / sent)", 11, "%")
  line("Average delay, send -> arrival", 12, "ms")
  line("Retransmissions (frames sent again)", 13, "")
  line("Packets that needed >= 1 retransmission", 14, "")
  line("Dropped: channel busy 5 times in a row", 15, "")
  line("No ACK after 3 retries (may have arrived)", 16, "")
  line("Share of channel checks (CCA) found busy", 17, "(1 = 100%)")
  line("minBE changes made by the rule", 18, "")
  line("Average minBE over the run (time-weighted)", 19, "")
}'
