import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Server,
  HardDrive,
  Database,
  TrendingDown,
} from "lucide-react";
import { clsx } from "clsx";
import type { Recommendation, RecommendationType } from "../types";
import { SeverityBadge } from "./SeverityBadge";
import { ProviderBadge } from "./ProviderBadge";

const TYPE_ICON: Record<RecommendationType, typeof Server> = {
  idle_instance: Server,
  unattached_volume: HardDrive,
  oversized_rds: Database,
  rightsizing: TrendingDown,
  reserved_instance: TrendingDown,
};

const TYPE_LABEL: Record<RecommendationType, string> = {
  idle_instance: "Idle Instance",
  unattached_volume: "Unattached Volume",
  oversized_rds: "Oversized Database",
  rightsizing: "Right-Sizing",
  reserved_instance: "Reserved Instance",
};

function RecRow({ rec }: { rec: Recommendation }) {
  const [open, setOpen] = useState(false);
  const Icon = TYPE_ICON[rec.recommendation_type] ?? Server;

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <div className="shrink-0 p-1.5 rounded-md bg-slate-100 text-slate-600">
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-slate-800 truncate">{rec.resource_name}</p>
          <p className="text-xs text-slate-500 truncate">{rec.resource_type} · {rec.region}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <ProviderBadge provider={rec.provider} />
          <SeverityBadge severity={rec.severity} />
          <span className="text-sm font-semibold text-emerald-600 w-20 text-right">
            ${rec.projected_monthly_savings.toLocaleString()}/mo
          </span>
          {open ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50 px-4 py-3 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Monthly Cost" value={`$${rec.current_monthly_cost.toLocaleString()}`} />
            <Metric
              label="Projected Savings"
              value={`$${rec.projected_monthly_savings.toLocaleString()}`}
              highlight
            />
            <Metric label="Savings %" value={`${rec.savings_percentage.toFixed(1)}%`} />
            <Metric label="Type" value={TYPE_LABEL[rec.recommendation_type]} />
          </div>

          <p className="text-sm text-slate-600">{rec.description}</p>

          <div className="bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
            <p className="text-xs font-semibold text-blue-700 mb-0.5">Recommended Action</p>
            <p className="text-sm text-blue-800">{rec.action}</p>
          </div>

          {rec.metrics.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">
                Metrics
              </p>
              <div className="flex flex-wrap gap-2">
                {rec.metrics.map((m) => (
                  <span
                    key={m.name}
                    className="text-xs bg-white border border-slate-200 rounded-full px-3 py-1 text-slate-600"
                  >
                    {m.name.replace(/_/g, " ")}: <strong>{m.value.toFixed(1)} {m.unit}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

          {Object.keys(rec.tags).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {Object.entries(rec.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="text-xs bg-slate-200 text-slate-600 rounded px-2 py-0.5"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p
        className={clsx(
          "text-sm font-semibold",
          highlight ? "text-emerald-600" : "text-slate-800"
        )}
      >
        {value}
      </p>
    </div>
  );
}

interface Props {
  recommendations: Recommendation[];
}

export function RecommendationsList({ recommendations }: Props) {
  const [filterType, setFilterType] = useState<string>("all");
  const [filterProvider, setFilterProvider] = useState<string>("all");

  const types = ["all", ...new Set(recommendations.map((r) => r.recommendation_type))];
  const providers = ["all", ...new Set(recommendations.map((r) => r.provider))];

  const filtered = recommendations.filter((r) => {
    const typeOk = filterType === "all" || r.recommendation_type === filterType;
    const provOk = filterProvider === "all" || r.provider === filterProvider;
    return typeOk && provOk;
  });

  const totalSavings = filtered.reduce(
    (sum, r) => sum + r.projected_monthly_savings,
    0
  );

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="font-semibold text-slate-800">
            Recommendations ({filtered.length})
          </h3>
          <p className="text-sm text-emerald-600 font-medium">
            Potential savings: ${totalSavings.toLocaleString(undefined, { maximumFractionDigits: 0 })}/mo
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            value={filterProvider}
            onChange={(e) => setFilterProvider(e.target.value)}
          >
            {providers.map((p) => (
              <option key={p} value={p}>
                {p === "all" ? "All Providers" : p.toUpperCase()}
              </option>
            ))}
          </select>
          <select
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            {types.map((t) => (
              <option key={t} value={t}>
                {t === "all"
                  ? "All Types"
                  : t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-2">
        {filtered.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-8">
            No recommendations match the current filters.
          </p>
        ) : (
          filtered.map((r) => <RecRow key={r.id} rec={r} />)
        )}
      </div>
    </div>
  );
}
