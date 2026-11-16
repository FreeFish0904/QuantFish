import { Info } from "lucide-react";
import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

export type EmptyStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.state} role="status">
      <Info aria-hidden="true" size={26} />
      <div>
        <h3>{title}</h3>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
