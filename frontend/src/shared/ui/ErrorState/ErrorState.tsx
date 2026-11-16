import { AlertTriangle } from "lucide-react";

import { useI18n } from "../../i18n";
import { Button } from "../Button/Button";
import styles from "./ErrorState.module.css";

export type ErrorStateProps = {
  title: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorState({ title, message, onRetry, retryLabel }: ErrorStateProps) {
  const { t } = useI18n();

  return (
    <div className={styles.state} role="alert">
      <AlertTriangle aria-hidden="true" size={26} />
      <div>
        <h3>{title}</h3>
        {message ? <p>{message}</p> : null}
      </div>
      {onRetry ? (
        <Button onClick={onRetry} variant="ghost">
          {retryLabel ?? t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}
