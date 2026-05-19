import { type ReactNode } from "react";
import { clsx } from "clsx";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  icon: ReactNode;
  accent?: "blue" | "green" | "amber" | "red";
}

const accentMap = {
  blue: "bg-blue-50 text-blue-700 border-blue-200",
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-red-50 text-red-700 border-red-200",
};

const iconMap = {
  blue: "bg-blue-100 text-blue-600",
  green: "bg-emerald-100 text-emerald-600",
  amber: "bg-amber-100 text-amber-600",
  red: "bg-red-100 text-red-600",
};

export function StatCard({ label, value, sub, icon, accent = "blue" }: StatCardProps) {
  return (
    <div
      className={clsx(
        "rounded-xl border p-5 flex items-start gap-4 shadow-sm",
        accentMap[accent]
      )}
    >
      <div className={clsx("rounded-lg p-2.5 shrink-0", iconMap[accent])}>
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium opacity-70">{label}</p>
        <p className="text-2xl font-bold mt-0.5">{value}</p>
        {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
      </div>
    </div>
  );
}
