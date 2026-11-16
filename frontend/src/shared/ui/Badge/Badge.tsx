import {
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  Clock3,
  Info,
  LoaderCircle,
  Wifi,
  WifiOff
} from "lucide-react";

import styles from "./Badge.module.css";

export type BadgeStatus =
  | "online"
  | "degraded"
  | "offline"
  | "queued"
  | "running"
  | "scored"
  | "failed"
  | "stale";

type BadgeTone = "positive" | "warning" | "danger" | "neutral";

function statusMeta(status: BadgeStatus): { Icon: typeof Info; tone: BadgeTone } {
  switch (status) {
    case "online":
      return { Icon: Wifi, tone: "positive" };
    case "degraded":
    case "queued":
      return { Icon: Clock3, tone: "warning" };
    case "offline":
      return { Icon: WifiOff, tone: "danger" };
    case "running":
      return { Icon: LoaderCircle, tone: "neutral" };
    case "scored":
      return { Icon: CheckCircle2, tone: "positive" };
    case "failed":
      return { Icon: CircleAlert, tone: "danger" };
    case "stale":
      return { Icon: CircleDashed, tone: "warning" };
    default:
      return { Icon: Info, tone: "neutral" };
  }
}

export type BadgeProps = {
  status: BadgeStatus;
  label: string;
};

export function Badge({ status, label }: BadgeProps) {
  const { Icon, tone } = statusMeta(status);
  const iconClassName = status === "running" ? styles.spin : undefined;

  return (
    <span className={[styles.badge, styles[tone]].join(" ")} role="status">
      <Icon aria-hidden="true" className={iconClassName} size={14} />
      {label}
    </span>
  );
}
