import { clsx } from "clsx";
import type { CloudProvider } from "../types";

const map: Record<CloudProvider, { label: string; cls: string }> = {
  aws: { label: "AWS", cls: "bg-orange-50 text-orange-700 border-orange-200" },
  azure: { label: "Azure", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  gcp: { label: "GCP", cls: "bg-indigo-50 text-indigo-700 border-indigo-200" },
};

export function ProviderBadge({ provider }: { provider: CloudProvider }) {
  const { label, cls } = map[provider];
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border",
        cls
      )}
    >
      {label}
    </span>
  );
}
