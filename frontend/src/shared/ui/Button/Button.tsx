import type { ButtonHTMLAttributes, ReactNode } from "react";

import styles from "./Button.module.css";

type ButtonVariant = "primary" | "ghost";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  children: ReactNode;
};

export function Button({ variant = "primary", className = "", children, ...rest }: ButtonProps) {
  const variantClass = variant === "ghost" ? styles.ghost : styles.primary;
  return (
    <button className={[styles.button, variantClass, className].join(" ")} type="button" {...rest}>
      {children}
    </button>
  );
}
