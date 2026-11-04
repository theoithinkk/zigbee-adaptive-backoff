/*
 * zigbee-star.cc
 * NSCOM03 S40B - Improving Zigbee Network Reliability Through Adaptive Backoff
 * in IEEE 802.15.4 CSMA/CA  (Campo, Morgan, Garcia)
 *
 * Star network: 1 coordinator at (0,0) + N sensors on a 10 m circle.
 * Each sensor sends a 20-byte packet (ACK requested) to the coordinator every
 * `interval` seconds, unslotted CSMA/CA, 2.4 GHz channel 11, 250 kbps.
 *
 * Modes:
 *   --mode=fixed     use --minBE (default 3 = IEEE default)
 *   --mode=adaptive  each sensor tunes its own macMinBE from its last W CCA results:
 *                    busy > hi  -> minBE+1 ; busy < lo -> minBE-1 ; clamp [0, maxBE]
 *
 * Adaptive hook: the PHY's PlmeCcaConfirm callback is re-pointed to a small wrapper
 * that records BUSY/IDLE and then forwards to the normal LrWpanCsmaCa::PlmeCcaConfirm.
 * => no modification of the lr-wpan module is needed.
 *
 * Output: one CSV row (see header printed with --header) to stdout.
 */

#include "ns3/core-module.h"
#include "ns3/lr-wpan-module.h"
#include "ns3/mobility-module.h"
#include "ns3/propagation-module.h"
#include "ns3/spectrum-module.h"

#include <cmath>
#include <deque>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
#include <vector>

using namespace ns3;
using namespace ns3::lrwpan;

NS_LOG_COMPONENT_DEFINE("ZigbeeStar");

// ---------------- global counters ----------------
struct Stats
{
    uint64_t generated = 0;      // packets handed to MAC (within measurement window)
    uint64_t delivered = 0;      // unique packets received by coordinator
    double delaySum = 0.0;       // seconds
    uint64_t txSuccess = 0;      // McpsDataConfirm SUCCESS
    uint64_t caFail = 0;         // CHANNEL_ACCESS_FAILURE
    uint64_t noAck = 0;          // NO_ACK (retry limit reached)
    uint64_t retxTotal = 0;      // total extra frame transmissions
    uint64_t retxPackets = 0;    // packets that needed >= 1 retransmission
    uint64_t ccaTotal = 0;       // CCAs performed by sensors
    uint64_t ccaBusy = 0;        // CCAs that found channel busy
    uint64_t beChanges = 0;      // adaptive minBE changes
};

static Stats g;
static std::set<std::pair<uint16_t, uint32_t>> g_seen; // (src, seq) dedup at coordinator
static double g_measureEnd = 0;
static const uint32_t PKT_SIZE = 20;

// ---------------- adaptive rule ----------------
struct AdaptiveState
{
    Ptr<LrWpanCsmaCa> csma;
    std::deque<bool> window; // true = busy
    uint32_t W = 10;
    double hi = 0.5;
    double lo = 0.2;
    uint8_t maxBE = 5;
    bool adaptive = false;
    double minBEtimeWeighted = 0; // for reporting avg minBE
    double lastChange = 0;
};

static std::vector<AdaptiveState> g_ad;
static std::ofstream g_beTrace; // --traceBE=<file>: "time_s,sensor,minBE" on every change

static void
CcaWrapper(uint32_t idx, PhyEnumeration status)
{
    AdaptiveState& s = g_ad[idx];
    bool busy = (status == IEEE_802_15_4_PHY_BUSY);
    g.ccaTotal++;
    if (busy)
    {
        g.ccaBusy++;
    }

    if (s.adaptive)
    {
        s.window.push_back(busy);
        if (s.window.size() > s.W)
        {
            s.window.pop_front();
        }
        if (s.window.size() == s.W)
        {
            uint32_t b = 0;
            for (bool x : s.window)
            {
                b += x;
            }
            double frac = double(b) / s.W;
            int be = s.csma->GetMacMinBE();
            int nbe = be;
            if (frac > s.hi)
            {
                nbe = std::min<int>(be + 1, s.maxBE);
            }
            else if (frac < s.lo)
            {
                nbe = std::max<int>(be - 1, 0);
            }
            if (nbe != be)
            {
                double now = Simulator::Now().GetSeconds();
                s.minBEtimeWeighted += be * (now - s.lastChange);
                s.lastChange = now;
                s.csma->SetMacMinBE(nbe); // takes effect at the next CSMA/CA run
                s.window.clear();         // require fresh evidence before next change
                g.beChanges++;
                if (g_beTrace.is_open())
                {
                    g_beTrace << now << "," << idx + 1 << "," << nbe << "\n";
                }
            }
        }
    }
    // forward to the normal CSMA/CA state machine
    s.csma->PlmeCcaConfirm(status);
}

// ---------------- traffic ----------------
static void
SendPacket(Ptr<LrWpanNetDevice> dev, uint16_t src, uint32_t seq, Time interval)
{
    double now = Simulator::Now().GetSeconds();
    if (now >= g_measureEnd)
    {
        return;
    }
    // payload: [seq(4)][txTime ns(8)][padding]
    uint8_t buf[PKT_SIZE] = {0};
    int64_t ts = Simulator::Now().GetNanoSeconds();
    std::memcpy(buf, &seq, 4);
    std::memcpy(buf + 4, &ts, 8);
    Ptr<Packet> p = Create<Packet>(buf, PKT_SIZE);

    McpsDataRequestParams params;
    params.m_srcAddrMode = SHORT_ADDR;
    params.m_dstAddrMode = SHORT_ADDR;
    params.m_dstPanId = 0;
    params.m_dstAddr = Mac16Address("00:00");
    params.m_msduHandle = static_cast<uint8_t>(seq & 0xff);
    params.m_txOptions = TX_OPTION_ACK;
    dev->GetMac()->McpsDataRequest(params, p);
    g.generated++;

    Simulator::Schedule(interval, &SendPacket, dev, src, seq + 1, interval);
}

static void
CoordRx(McpsDataIndicationParams params, Ptr<Packet> p)
{
    if (p->GetSize() < 12)
    {
        return;
    }
    uint8_t buf[PKT_SIZE] = {0};
    p->CopyData(buf, std::min<uint32_t>(p->GetSize(), PKT_SIZE));
    uint32_t seq;
    int64_t ts;
    std::memcpy(&seq, buf, 4);
    std::memcpy(&ts, buf + 4, 8);

    uint8_t a[2];
    params.m_srcAddr.CopyTo(a);
    uint16_t src = (a[0] << 8) | a[1];
    if (!g_seen.insert({src, seq}).second)
    {
        return; // duplicate (ACK was lost, sensor retransmitted)
    }
    if (ts / 1e9 >= g_measureEnd)
    {
        return;
    }
    g.delivered++;
    g.delaySum += (Simulator::Now().GetNanoSeconds() - ts) / 1e9;
}

static void
SensorConfirm(McpsDataConfirmParams params)
{
    switch (params.m_status)
    {
    case MacStatus::SUCCESS:
        g.txSuccess++;
        break;
    case MacStatus::CHANNEL_ACCESS_FAILURE:
        g.caFail++;
        break;
    case MacStatus::NO_ACK:
        g.noAck++;
        break;
    default:
        break;
    }
}

// MacSentPkt: (packet, number of frame transmissions, number of CSMA attempts)
static void
SentPkt(Ptr<const Packet> p, uint8_t txCount, uint8_t /*backoffs*/)
{
    if (txCount > 1)
    {
        g.retxPackets++;
        g.retxTotal += txCount - 1;
    }
}

int
main(int argc, char* argv[])
{
    uint32_t nSensors = 10;
    double interval = 1.0;
    double simTime = 300.0;
    uint32_t run = 1;
    uint32_t minBE = 3;
    uint32_t maxBE = 5;
    uint32_t maxBackoffs = 4;
    uint32_t maxRetries = 3;
    std::string mode = "fixed";
    uint32_t window = 10;
    double hi = 0.5;
    double lo = 0.2;
    double radius = 10.0;
    bool header = false;
    std::string traceBE = "";

    CommandLine cmd(__FILE__);
    cmd.AddValue("nSensors", "Number of sensors (N)", nSensors);
    cmd.AddValue("interval", "Sending interval per sensor [s]", interval);
    cmd.AddValue("simTime", "Simulation time [s]", simTime);
    cmd.AddValue("run", "RNG run number", run);
    cmd.AddValue("mode", "fixed | adaptive", mode);
    cmd.AddValue("minBE", "macMinBE (fixed mode / adaptive start value)", minBE);
    cmd.AddValue("maxBE", "macMaxBE", maxBE);
    cmd.AddValue("maxBackoffs", "macMaxCSMABackoffs", maxBackoffs);
    cmd.AddValue("maxRetries", "macMaxFrameRetries", maxRetries);
    cmd.AddValue("window", "Adaptive: CCA history window W", window);
    cmd.AddValue("hi", "Adaptive: busy fraction above which minBE++", hi);
    cmd.AddValue("lo", "Adaptive: busy fraction below which minBE--", lo);
    cmd.AddValue("radius", "Sensor circle radius [m]", radius);
    cmd.AddValue("header", "Print CSV header and exit", header);
    cmd.AddValue("traceBE", "Write every minBE change (time_s,sensor,minBE) to this CSV file",
                 traceBE);
    cmd.Parse(argc, argv);

    if (header)
    {
        std::cout << "mode,N,interval,minBE,window,hi,lo,run,generated,delivered,pdr,"
                     "avg_delay_ms,retx_total,retx_packets,ca_fail,no_ack,"
                     "cca_busy_frac,be_changes,avg_minBE\n";
        return 0;
    }

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(run);
    g_measureEnd = simTime;
    bool adaptive = (mode == "adaptive");

    // ---- nodes & devices ----
    NodeContainer nodes;
    nodes.Create(nSensors + 1); // node 0 = coordinator

    LrWpanHelper helper;
    helper.SetPropagationDelayModel("ns3::ConstantSpeedPropagationDelayModel");
    helper.AddPropagationLossModel("ns3::LogDistancePropagationLossModel");
    NetDeviceContainer devs = helper.Install(nodes);

    for (uint32_t i = 0; i < devs.GetN(); i++)
    {
        Ptr<LrWpanNetDevice> d = devs.Get(i)->GetObject<LrWpanNetDevice>();
        // short address i  (coordinator = 00:00)
        uint8_t a[2] = {uint8_t(i >> 8), uint8_t(i & 0xff)};
        Mac16Address addr;
        addr.CopyFrom(a);
        d->GetMac()->SetShortAddress(addr);
        d->GetMac()->SetPanId(0);

        Ptr<ConstantPositionMobilityModel> mob = CreateObject<ConstantPositionMobilityModel>();
        if (i == 0)
        {
            mob->SetPosition(Vector(0, 0, 0));
        }
        else
        {
            double th = 2 * M_PI * (i - 1) / nSensors;
            mob->SetPosition(Vector(radius * std::cos(th), radius * std::sin(th), 0));
        }
        d->GetPhy()->SetMobility(mob);

        Ptr<LrWpanCsmaCa> csma = d->GetCsmaCa();
        csma->SetMacMaxBE(maxBE);
        csma->SetMacMinBE(minBE);
        csma->SetMacMaxCSMABackoffs(maxBackoffs);
        d->GetMac()->SetMacMaxFrameRetries(maxRetries);
    }

    // coordinator receive hook
    Ptr<LrWpanNetDevice> coord = devs.Get(0)->GetObject<LrWpanNetDevice>();
    coord->GetMac()->SetMcpsDataIndicationCallback(MakeCallback(&CoordRx));

    if (!traceBE.empty())
    {
        g_beTrace.open(traceBE);
        NS_ABORT_MSG_UNLESS(g_beTrace, "cannot open --traceBE file " << traceBE);
        g_beTrace << "time_s,sensor,minBE\n";
        for (uint32_t i = 1; i <= nSensors; i++)
        {
            g_beTrace << 0.0 << "," << i << "," << minBE << "\n"; // starting value
        }
    }

    // sensors: hooks + traffic
    g_ad.resize(nSensors);
    Ptr<UniformRandomVariable> start = CreateObject<UniformRandomVariable>();
    for (uint32_t i = 1; i <= nSensors; i++)
    {
        Ptr<LrWpanNetDevice> d = devs.Get(i)->GetObject<LrWpanNetDevice>();
        d->GetMac()->SetMcpsDataConfirmCallback(MakeCallback(&SensorConfirm));
        d->GetMac()->TraceConnectWithoutContext("MacSentPkt", MakeCallback(&SentPkt));

        AdaptiveState& s = g_ad[i - 1];
        s.csma = d->GetCsmaCa();
        s.W = window;
        s.hi = hi;
        s.lo = lo;
        s.maxBE = maxBE;
        s.adaptive = adaptive;
        // re-point the PHY CCA confirm to our wrapper (then forwards to CSMA/CA)
        d->GetPhy()->SetPlmeCcaConfirmCallback(MakeBoundCallback(&CcaWrapper, i - 1));

        // randomized start within first interval
        Time t0 = Seconds(start->GetValue(0.0, interval));
        Simulator::ScheduleWithContext(i, t0, &SendPacket, d, uint16_t(i), 0u, Seconds(interval));
    }

    Simulator::Stop(Seconds(simTime + 1.0)); // 1 s grace for in-flight packets
    Simulator::Run();

    // average minBE across sensors (time-weighted)
    double avgBE = 0;
    double T = simTime + 1.0;
    for (auto& s : g_ad)
    {
        avgBE += (s.minBEtimeWeighted + s.csma->GetMacMinBE() * (T - s.lastChange)) / T;
    }
    avgBE /= nSensors;

    double pdr = g.generated ? 100.0 * g.delivered / g.generated : 0;
    double delay = g.delivered ? 1000.0 * g.delaySum / g.delivered : 0;
    double busy = g.ccaTotal ? double(g.ccaBusy) / g.ccaTotal : 0;

    std::cout << std::fixed << std::setprecision(4) << mode << "," << nSensors << ","
              << interval << "," << minBE << "," << window << "," << hi << "," << lo << ","
              << run << "," << g.generated << "," << g.delivered << "," << pdr << "," << delay
              << "," << g.retxTotal << "," << g.retxPackets << "," << g.caFail << ","
              << g.noAck << "," << busy << "," << g.beChanges << "," << avgBE << "\n";

    Simulator::Destroy();
    return 0;
}
