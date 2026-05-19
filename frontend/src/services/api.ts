import axios from "axios";
import type {
  CostSummary,
  ExportRequest,
  RecommendationSummary,
} from "../types";

const BASE = "/api/v1";

const http = axios.create({
  baseURL: BASE,
  timeout: 30_000,
});

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.detail ?? err.message ?? "Unknown error";
    console.error("[CloudLens API]", msg);
    return Promise.reject(new Error(String(msg)));
  }
);

export const api = {
  getCostSummary: (): Promise<CostSummary> =>
    http.get<CostSummary>("/costs/summary").then((r) => r.data),

  getRecommendations: (params?: {
    provider?: string[];
    rec_type?: string[];
    min_savings?: number;
  }): Promise<RecommendationSummary> =>
    http
      .get<RecommendationSummary>("/recommendations/", { params })
      .then((r) => r.data),

  exportPdf: async (body: ExportRequest): Promise<void> => {
    const resp = await http.post("/export/pdf", body, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(
      new Blob([resp.data], { type: "application/pdf" })
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "cloudlens-report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  },
};
