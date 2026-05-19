import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { CostSummary } from "../types";

const PROVIDER_COLORS: Record<string, string> = {
  aws: "#FF9900",
  azure: "#0089D6",
  gcp: "#4285F4",
};

const SERVICE_COLORS = [
  "#1e40af", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd",
  "#059669", "#10b981", "#34d399", "#6ee7b7",
  "#d97706", "#f59e0b",
];

function fmt(v: number) {
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

interface Props {
  data: CostSummary;
}

export function SpendTrendChart({ data }: Props) {
  const trend = data.trend.slice(-30).map((p) => ({
    date: p.date.slice(5),
    amount: p.amount,
  }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-4">30-Day Spend Trend</h3>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={trend}>
          <defs>
            <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={6}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <Tooltip
            formatter={(v: number) => [`$${v.toFixed(2)}`, "Daily Spend"]}
            contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
          />
          <Area
            type="monotone"
            dataKey="amount"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#trendGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProviderPieChart({ data }: Props) {
  const pieData = Object.entries(data.by_provider).map(([key, value]) => ({
    name: key.toUpperCase(),
    value,
    color: PROVIDER_COLORS[key] ?? "#94a3b8",
  }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-4">Spend by Provider</h3>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={3}
            dataKey="value"
          >
            {pieData.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(v: number) => [`$${v.toLocaleString()}`, "Spend"]}
            contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
          />
          <Legend
            formatter={(value) => (
              <span style={{ fontSize: 12, color: "#475569" }}>{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ServiceBarChart({ data }: Props) {
  const sorted = [...data.by_service]
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 8)
    .map((s, i) => ({
      service: s.service.replace(/^(Amazon|Azure|Google) /, ""),
      amount: s.amount,
      fill: SERVICE_COLORS[i % SERVICE_COLORS.length],
    }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-4">Top Services by Spend</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={fmt}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="service"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={110}
          />
          <Tooltip
            formatter={(v: number) => [`$${v.toLocaleString()}`, "Monthly Spend"]}
            contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
          />
          <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
            {sorted.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RegionBarChart({ data }: Props) {
  const sorted = [...data.by_region]
    .sort((a, b) => b.amount - a.amount)
    .map((r) => ({
      region: r.region,
      amount: r.amount,
      provider: r.provider,
      fill: PROVIDER_COLORS[r.provider] ?? "#94a3b8",
    }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-4">Spend by Region</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={sorted}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="region"
            tick={{ fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            angle={-20}
            textAnchor="end"
            height={40}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <Tooltip
            formatter={(v: number) => [`$${v.toLocaleString()}`, "Monthly Spend"]}
            contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12 }}
          />
          <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
            {sorted.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
