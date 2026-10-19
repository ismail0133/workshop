import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Payment } from "../../types/api";
import { money } from "../../utils/money";
import { Empty } from "../ui";
export function ActivityChart({ payments }: { payments: Payment[] }) {
  if (!payments.length)
    return (
      <Empty title="Pas encore d’activité">
        Les transactions chargées alimenteront ce graphique.
      </Empty>
    );
  const byDay = new Map<
    string,
    { day: string; success: number; rejected: number }
  >();
  for (const p of payments) {
    const day = p.created_at.slice(0, 10);
    const row = byDay.get(day) || { day, success: 0, rejected: 0 };
    row[p.status === "SUCCESS" ? "success" : "rejected"] += p.amount_minor;
    byDay.set(day, row);
  }
  const data = [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
  return (
    <div
      className="chart"
      role="img"
      aria-label="Montants des transactions chargées par jour UTC, réussies et rejetées"
    >
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} barGap={5}>
          <CartesianGrid stroke="#202c40" vertical={false} />
          <XAxis
            dataKey="day"
            stroke="#8090aa"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis
            stroke="#8090aa"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v / 100} €`}
          />
          <Tooltip
            contentStyle={{
              background: "#131e30",
              border: "1px solid #2a3b54",
              borderRadius: 10,
              color: "#f1f5ff",
            }}
            formatter={(v) => money(Number(v))}
          />
          <Bar
            name="SUCCESS"
            dataKey="success"
            fill="#37c6dc"
            radius={[4, 4, 0, 0]}
            maxBarSize={34}
          />
          <Bar
            name="REJECTED"
            dataKey="rejected"
            fill="#b087e8"
            radius={[4, 4, 0, 0]}
            maxBarSize={34}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
