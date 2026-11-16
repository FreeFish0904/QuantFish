import { Card } from "../../../shared/ui/Card/Card";
import styles from "./KpiCard.module.css";

export type KpiCardProps = {
  label: string;
  value: string;
  tone?: "positive" | "warning" | "danger" | "neutral";
};

export function KpiCard({ label, value, tone = "neutral" }: KpiCardProps) {
  return (
    <Card className={styles.card}>
      <span className={styles.label}>{label}</span>
      <span className={[styles.value, styles[tone]].join(" ")}>{value}</span>
    </Card>
  );
}
