export type CloudProvider = "aws" | "azure" | "gcp";

export type RecommendationType =
  | "idle_instance"
  | "unattached_volume"
  | "oversized_rds"
  | "rightsizing"
  | "reserved_instance";

export type Severity = "low" | "medium" | "high" | "critical";

export interface ResourceMetric {
  name: string;
  value: number;
  unit: string;
  period_days: number;
}

export interface Recommendation {
  id: string;
  provider: CloudProvider;
  account_id: string;
  region: string;
  resource_id: string;
  resource_name: string;
  resource_type: string;
  recommendation_type: RecommendationType;
  severity: Severity;
  current_monthly_cost: number;
  projected_monthly_savings: number;
  savings_percentage: number;
  description: string;
  action: string;
  metrics: ResourceMetric[];
  tags: Record<string, string>;
  detected_at: string;
  metadata: Record<string, unknown>;
}

export interface RecommendationSummary {
  total_recommendations: number;
  total_projected_savings: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  by_provider: Record<string, number>;
  recommendations: Recommendation[];
}

export interface CostDataPoint {
  date: string;
  amount: number;
  currency: string;
}

export interface ServiceCost {
  service: string;
  provider: CloudProvider;
  amount: number;
  currency: string;
  period: string;
}

export interface RegionCost {
  region: string;
  provider: CloudProvider;
  amount: number;
  currency: string;
  period: string;
}

export interface AccountCost {
  account_id: string;
  account_name: string;
  provider: CloudProvider;
  amount: number;
  currency: string;
  period: string;
}

export interface CostSummary {
  total_monthly_spend: number;
  total_projected_savings: number;
  savings_percentage: number;
  recommendation_count: number;
  by_provider: Record<string, number>;
  by_service: ServiceCost[];
  by_region: RegionCost[];
  by_account: AccountCost[];
  trend: CostDataPoint[];
  generated_at: string;
}

export interface ExportRequest {
  include_providers: CloudProvider[];
  include_types: RecommendationType[];
  min_savings: number;
  format: "pdf";
}
