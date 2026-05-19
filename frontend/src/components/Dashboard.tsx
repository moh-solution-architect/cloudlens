import { DollarSign, TrendingDown, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useCostSummary, useRecommendations } from "../hooks/useCloudData";
import { StatCard } from "./StatCard";
import {
  SpendTrendChart,
  ProviderPieChart,
  ServiceBarChart,
  RegionBarChart,
} from "./CostCharts";
import { RecommendationsList } from "./Recommendations";
import { ExportButton } from "./ExportButton";

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-slate-100 ${className ?? ""}`}
    />
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <strong>Failed to load data:</strong> {message}. Make sure the backend is running on{" "}
      <code className="bg-red-100 px-1 rounded">localhost:8000</code>.
    </div>
  );
}

export function Dashboard() {
  const { data: costs, isLoading: costsLoading, error: costsError } = useCostSummary();
  const { data: recsData, isLoading: recsLoading, error: recsError } = useRecommendations();

  const anyError = costsError || recsError;
  const anyLoading = costsLoading || recsLoading;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <TrendingDown className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-slate-900 text-lg leading-none">CloudLens</span>
              <p className="text-xs text-slate-500 leading-none">Multi-Cloud Cost Optimizer</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 hidden sm:block">
              {costs
                ? `Updated ${new Date(costs.generated_at).toLocaleTimeString()}`
                : "Loading…"}
            </span>
            <ExportButton />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Error */}
        {anyError && (
          <ErrorBanner
            message={
              (costsError as Error)?.message ??
              (recsError as Error)?.message ??
              "Unknown error"
            }
          />
        )}

        {/* KPI row */}
        {anyLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : costs && recsData ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Total Monthly Spend"
              value={`$${costs.total_monthly_spend.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              sub="Across all providers"
              icon={<DollarSign className="w-5 h-5" />}
              accent="blue"
            />
            <StatCard
              label="Projected Savings"
              value={`$${costs.total_projected_savings.toLocaleString(undefined, { maximumFractionDigits: 0 })}/mo`}
              sub={`${costs.savings_percentage.toFixed(1)}% of total spend`}
              icon={<TrendingDown className="w-5 h-5" />}
              accent="green"
            />
            <StatCard
              label="Recommendations"
              value={String(recsData.total_recommendations)}
              sub={`${recsData.by_severity?.["critical"] ?? 0} critical, ${recsData.by_severity?.["high"] ?? 0} high`}
              icon={<AlertTriangle className="w-5 h-5" />}
              accent="amber"
            />
            <StatCard
              label="Providers Monitored"
              value={String(Object.keys(costs.by_provider).length)}
              sub="AWS · Azure · GCP"
              icon={<CheckCircle2 className="w-5 h-5" />}
              accent="blue"
            />
          </div>
        ) : null}

        {/* Charts grid */}
        {anyLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        ) : costs ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SpendTrendChart data={costs} />
            <ProviderPieChart data={costs} />
            <ServiceBarChart data={costs} />
            <RegionBarChart data={costs} />
          </div>
        ) : null}

        {/* Recommendations */}
        {anyLoading ? (
          <Skeleton className="h-96" />
        ) : recsData ? (
          <RecommendationsList recommendations={recsData.recommendations} />
        ) : null}
      </main>
    </div>
  );
}
