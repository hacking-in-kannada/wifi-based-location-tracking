/**
 * Analytics.tsx — WiFiSense Phase 10: Training Analytics Dashboard
 *
 * Renders five premium chart panels with data from /api/v1/analytics:
 *  1. KPI stat cards (rooms, positions, samples, completeness)
 *  2. Model accuracy bar chart (horizontal)
 *  3. 30-day accuracy trend line chart (SVG polyline)
 *  4. Zone coverage bar chart (per-position sample counts)
 *  5. RSSI signal distribution histogram
 *
 * All charts are pure SVG — no external charting library required.
 */

import { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  Layers,
  Wifi,
  RefreshCw,
  CheckCircle,
  Clock,
  Target,
  Database,
  Trash2,
} from "lucide-react";

// ---------- Types ----------

interface ModelBenchmark {
  name: string;
  accuracy: number;
  f1: number;
  latency_ms: number;
  color: string;
}

interface ZoneCoverage {
  room: string;
  label: string;
  sample_count: number;
  has_fingerprint: boolean;
}

interface AccuracyPoint {
  day: number;
  accuracy: number;
}

interface RssiBucket {
  range: string;
  count: number;
}

interface Summary {
  total_rooms: number;
  total_positions: number;
  total_samples: number;
  trained_positions: number;
  dataset_completeness_pct: number;
}

interface AnalyticsData {
  summary: Summary;
  model_benchmarks: ModelBenchmark[];
  zone_coverage: ZoneCoverage[];
  accuracy_history: AccuracyPoint[];
  rssi_distribution: RssiBucket[];
}

// ---------- Sub-components ----------

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="glow-card rounded-xl p-5 flex flex-col gap-3 relative overflow-hidden">
      <div
        className="absolute inset-0 opacity-5 pointer-events-none"
        style={{ background: `radial-gradient(ellipse at 20% 20%, ${color}, transparent 70%)` }}
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono uppercase tracking-widest text-gray-500">{label}</span>
        <div
          className="p-2 rounded-lg"
          style={{ backgroundColor: `${color}18`, border: `1px solid ${color}30` }}
        >
          <Icon className="w-4 h-4" style={{ color }} />
        </div>
      </div>
      <div>
        <p className="text-3xl font-bold text-white tabular-nums">{value}</p>
        {sub && <p className="text-xs text-gray-500 mt-0.5 font-mono">{sub}</p>}
      </div>
    </div>
  );
}

function ModelBenchmarkChart({ models }: { models: ModelBenchmark[] }) {
  return (
    <div className="glow-card rounded-xl p-6">
      <div className="flex items-center gap-2 mb-6">
        <BarChart3 className="w-4 h-4 text-neon-purple" />
        <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">
          Model Benchmark — Zone Accuracy
        </h3>
        <span className="ml-auto text-[10px] text-gray-500 font-mono">5-fold cross-validation · 5 zones</span>
      </div>
      <div className="space-y-4">
        {models.map((m, i) => (
          <div key={i}>
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-mono text-gray-300">{m.name}</span>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-gray-500 font-mono">F1: {m.f1.toFixed(3)}</span>
                <span className="text-[10px] font-mono text-gray-400">{m.latency_ms.toFixed(2)}ms</span>
                <span className="text-sm font-bold font-mono" style={{ color: m.color }}>{m.accuracy.toFixed(1)}%</span>
              </div>
            </div>
            <div className="h-2.5 w-full bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${m.accuracy}%`,
                  background: `linear-gradient(90deg, ${m.color}88 0%, ${m.color} 100%)`,
                  boxShadow: `0 0 8px ${m.color}66`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5 p-3 rounded-lg bg-white/[0.02] border border-white/5">
        <p className="text-[10px] text-gray-500 font-mono leading-relaxed">
          Accuracy represents closest matching trained zone/location — not centimeter-level coordinates. All predictions include a confidence score.
        </p>
      </div>
    </div>
  );
}

function AccuracyTrendChart({ history }: { history: AccuracyPoint[] }) {
  if (!history.length) return null;
  const W = 680; const H = 160;
  const PAD = { top: 16, right: 16, bottom: 32, left: 44 };
  const minAcc = Math.min(...history.map((h) => h.accuracy)) - 3;
  const maxAcc = Math.max(...history.map((h) => h.accuracy)) + 3;
  const toX = (day: number) => PAD.left + ((day - 1) / Math.max(history.length - 1, 1)) * (W - PAD.left - PAD.right);
  const toY = (acc: number) => PAD.top + (1 - (acc - minAcc) / (maxAcc - minAcc)) * (H - PAD.top - PAD.bottom);
  const points = history.map((h) => `${toX(h.day)},${toY(h.accuracy)}`).join(" ");
  const fillPath = [
    `M ${toX(history[0].day)},${toY(history[0].accuracy)}`,
    ...history.slice(1).map((h) => `L ${toX(h.day)},${toY(h.accuracy)}`),
    `L ${toX(history[history.length - 1].day)},${H - PAD.bottom}`,
    `L ${toX(history[0].day)},${H - PAD.bottom}`,
    "Z",
  ].join(" ");
  const yLabels = [80, 85, 90, 95, 100];
  const last = history[history.length - 1];
  return (
    <div className="glow-card rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-neon-green" />
        <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">30-Day Accuracy Trend</h3>
        <span className="ml-auto text-xs font-bold text-neon-green font-mono">{last?.accuracy.toFixed(1)}% latest</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible" style={{ height: H }} aria-label="30-day accuracy trend">
        <defs>
          <linearGradient id="accGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#34d399" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
          </linearGradient>
          <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {yLabels.map((y) => (
          <g key={y}>
            <line x1={PAD.left} y1={toY(y)} x2={W - PAD.right} y2={toY(y)} stroke="rgba(255,255,255,0.04)" strokeWidth="1" strokeDasharray="4 4" />
            <text x={PAD.left - 6} y={toY(y) + 4} textAnchor="end" fill="#4b5563" fontSize="10" fontFamily="JetBrains Mono, monospace">{y}%</text>
          </g>
        ))}
        {[1, 7, 14, 21, 28, 30].map((d) => {
          const h = history.find((x) => x.day === d);
          if (!h) return null;
          return <text key={d} x={toX(d)} y={H - PAD.bottom + 14} textAnchor="middle" fill="#4b5563" fontSize="10" fontFamily="JetBrains Mono, monospace">D{d}</text>;
        })}
        <path d={fillPath} fill="url(#accGradient)" />
        <polyline points={points} fill="none" stroke="#34d399" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" filter="url(#lineGlow)" />
        {last && (
          <g>
            <circle cx={toX(last.day)} cy={toY(last.accuracy)} r="5" fill="#08060b" stroke="#34d399" strokeWidth="2" />
            <circle cx={toX(last.day)} cy={toY(last.accuracy)} r="9" fill="none" stroke="#34d39944" strokeWidth="1" />
          </g>
        )}
      </svg>
    </div>
  );
}

function ZoneCoverageChart({ zones }: { zones: ZoneCoverage[] }) {
  if (!zones.length) return null;
  const maxCount = Math.max(...zones.map((z) => z.sample_count), 1);
  const TARGET = 150;
  return (
    <div className="glow-card rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Layers className="w-4 h-4 text-neon-yellow" />
        <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">Zone Coverage</h3>
        <span className="ml-auto text-[10px] text-gray-500 font-mono">Target: {TARGET} samples</span>
      </div>
      <div className="space-y-3">
        {zones.map((z, i) => {
          const pct = Math.min((z.sample_count / maxCount) * 100, 100);
          const targetPct = Math.min((TARGET / maxCount) * 100, 100);
          const color = z.has_fingerprint ? "#34d399" : "#fbbf24";
          return (
            <div key={i}>
              <div className="flex justify-between items-center mb-1">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }} />
                  <span className="text-xs font-mono text-gray-300 truncate max-w-[140px]">{z.label}</span>
                  {!z.has_fingerprint && (
                    <span className="text-[9px] font-mono bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">NEEDS CAPTURE</span>
                  )}
                </div>
                <span className="text-xs font-mono font-bold" style={{ color }}>{z.sample_count}</span>
              </div>
              <div className="h-2 w-full bg-white/5 rounded-full overflow-visible relative">
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}44 0%, ${color} 100%)` }} />
                <div className="absolute top-[-3px] bottom-[-3px] w-px" style={{ left: `${targetPct}%`, backgroundColor: "#ffffff22" }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex items-center gap-4 text-[10px] font-mono text-gray-500">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-neon-green inline-block" /> Fingerprint ready</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-neon-yellow inline-block" /> Needs more captures</span>
      </div>
    </div>
  );
}

function RssiHistogram({ buckets }: { buckets: RssiBucket[] }) {
  if (!buckets.length) return null;
  const maxCount = Math.max(...buckets.map((b) => b.count), 1);
  const W = 600; const H = 120;
  const PAD = { top: 10, right: 10, bottom: 30, left: 40 };
  const barW = (W - PAD.left - PAD.right) / buckets.length;
  return (
    <div className="glow-card rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Wifi className="w-4 h-4 text-cyan-400" />
        <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">RSSI Signal Distribution</h3>
        <span className="ml-auto text-[10px] text-gray-500 font-mono">HT20 · 2.4 GHz</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }} aria-label="RSSI distribution">
        <defs>
          <linearGradient id="rssiGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.2" />
          </linearGradient>
          <filter id="rssiGlow" x="-10%" y="-30%" width="120%" height="160%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {[0, Math.round(maxCount / 2), maxCount].map((v) => {
          const yy = PAD.top + (1 - v / maxCount) * (H - PAD.top - PAD.bottom);
          return (
            <g key={v}>
              <line x1={PAD.left} y1={yy} x2={W - PAD.right} y2={yy} stroke="rgba(255,255,255,0.04)" strokeWidth="1" strokeDasharray="3 3" />
              <text x={PAD.left - 6} y={yy + 4} textAnchor="end" fill="#4b5563" fontSize="9" fontFamily="JetBrains Mono, monospace">{v}</text>
            </g>
          );
        })}
        {buckets.map((b, i) => {
          const bH = ((b.count / maxCount) * (H - PAD.top - PAD.bottom));
          const x = PAD.left + i * barW + 4;
          const y = PAD.top + (H - PAD.top - PAD.bottom) - bH;
          return (
            <g key={i} filter="url(#rssiGlow)">
              <rect x={x} y={y} width={barW - 8} height={bH} rx={3} fill="url(#rssiGrad)" />
            </g>
          );
        })}
        {buckets.map((b, i) => {
          const cx = PAD.left + i * barW + barW / 2;
          const short = b.range.split(" ")[0];
          return <text key={i} x={cx} y={H - PAD.bottom + 14} textAnchor="middle" fill="#4b5563" fontSize="9" fontFamily="JetBrains Mono, monospace">{short}</text>;
        })}
      </svg>
      <p className="text-[10px] text-gray-600 font-mono mt-1">RSSI range (dBm) — lower bars indicate weak/rare signal</p>
    </div>
  );
}

function LatencyChart({ models }: { models: ModelBenchmark[] }) {
  const max = Math.max(...models.map((m) => m.latency_ms), 1);
  return (
    <div className="glow-card rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <Clock className="w-4 h-4 text-orange-400" />
        <h3 className="text-sm font-semibold text-white font-mono uppercase tracking-wider">Inference Latency</h3>
        <span className="ml-auto text-[10px] text-gray-500 font-mono">ms per prediction</span>
      </div>
      <div className="space-y-4">
        {[...models].sort((a, b) => a.latency_ms - b.latency_ms).map((m, i) => (
          <div key={i}>
            <div className="flex justify-between mb-1">
              <span className="text-xs font-mono text-gray-400">{m.name}</span>
              <span className="text-xs font-mono font-bold text-orange-400">{m.latency_ms.toFixed(2)} ms</span>
            </div>
            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(m.latency_ms / max) * 100}%`, background: "linear-gradient(90deg, #f97316aa, #f97316)" }} />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-600 font-mono mt-4">SVM and KNN deliver sub-millisecond inference. Neural Net suitable for batch classification.</p>
    </div>
  );
}

// ---------- Main Analytics Component ----------

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string>("");

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`http://${window.location.hostname}:8000/api/v1/analytics`);
      if (!resp.ok) throw new Error(`Server error ${resp.status}`);
      const json: AnalyticsData = await resp.json();
      setData(json);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handlePurgeAllData = async () => {
    if (!window.confirm("CRITICAL WARNING: Are you sure you want to delete ALL old rooms, positions, fingerprints, and CSI samples? This will clear the entire analytics history.")) return;
    try {
      const resp = await fetch(`http://${window.location.hostname}:8000/api/v1/reset`, { method: "POST" });
      if (!resp.ok) throw new Error("Failed to purge data");
      fetchAnalytics();
    } catch (e: any) {
      alert(`Purge failed: ${e.message}`);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 30_000);
    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Analytics</h2>
          <p className="text-xs text-gray-500 font-mono mt-0.5">Training dataset quality · Model benchmarks · Signal diagnostics</p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && <span className="text-[10px] text-gray-600 font-mono">Refreshed {lastRefresh}</span>}
          <button onClick={fetchAnalytics} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-white/5 border border-white/10 text-gray-300 hover:text-white hover:border-neon-purple/50 transition disabled:opacity-40 cursor-pointer">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button onClick={handlePurgeAllData} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 hover:border-rose-500/60 transition disabled:opacity-40 cursor-pointer">
            <Trash2 className="w-3 h-3 text-rose-400" />
            PURGE ALL OLD DATA
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-mono">
          Failed to fetch analytics: {error}. Is the backend running on port 8000?
        </div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="glow-card rounded-xl h-28 animate-pulse" />)}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={Database} label="Total Samples" value={data.summary.total_samples.toLocaleString()} sub={`across ${data.summary.total_positions} positions`} color="#c084fc" />
            <StatCard icon={Target} label="Dataset Complete" value={`${data.summary.dataset_completeness_pct}%`} sub={`${data.summary.trained_positions}/${data.summary.total_positions} zones trained`} color="#34d399" />
            <StatCard icon={CheckCircle} label="Best Accuracy" value={`${Math.max(...data.model_benchmarks.map((m) => m.accuracy)).toFixed(1)}%`} sub={data.model_benchmarks.find((m) => m.accuracy === Math.max(...data.model_benchmarks.map((x) => x.accuracy)))?.name ?? ""} color="#fbbf24" />
            <StatCard icon={Clock} label="Fastest Inference" value={`${Math.min(...data.model_benchmarks.map((m) => m.latency_ms)).toFixed(2)} ms`} sub={data.model_benchmarks.find((m) => m.latency_ms === Math.min(...data.model_benchmarks.map((x) => x.latency_ms)))?.name ?? ""} color="#22d3ee" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2"><AccuracyTrendChart history={data.accuracy_history} /></div>
            <LatencyChart models={data.model_benchmarks} />
          </div>

          <ModelBenchmarkChart models={data.model_benchmarks} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ZoneCoverageChart zones={data.zone_coverage} />
            <RssiHistogram buckets={data.rssi_distribution} />
          </div>

          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-gray-500 font-mono leading-relaxed">
            <strong className="text-gray-400">Accuracy Disclaimer:</strong> All zone predictions represent the closest matching trained location — not centimeter-accurate GPS coordinates. Confidence scores accompany every prediction. Minimum recommended: 100 samples per zone, 3+ zones.
          </div>
        </>
      )}
    </div>
  );
}
