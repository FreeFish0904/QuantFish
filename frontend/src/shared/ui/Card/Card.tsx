import type { ReactNode } from "react";

import styles from "./Card.module.css";

export type CardProps = {
  children: ReactNode;
  className?: string;
  header?: ReactNode;
};

export function Card({ children, className = "", header }: CardProps) {
  return (
    <article className={[styles.card, className].join(" ")}>
      {header ? <div className={styles.header}>{header}</div> : null}
      <div className={styles.body}>{children}</div>
    </article>
  );
}
