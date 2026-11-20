import { LoaderCircle } from "lucide-react";
import { Suspense, type ReactNode } from "react";

import { useI18n } from "../shared/i18n";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import styles from "../routes.module.css";

// Route chrome (suspense/loading/error) in a component-only module, so
// `routes.tsx` can export just the route table.
export function RouteLoading() {
  const { t } = useI18n();
  return (
    <div className={styles.routePlaceholder} role="status" aria-live="polite">
      <LoaderCircle aria-hidden="true" className={styles.spinner} />
      <span>{t("common.loading")}</span>
    </div>
  );
}

export function RouteError() {
  const { t } = useI18n();
  return (
    <div className={styles.errorWrapper}>
      <ErrorState
        title={t("common.error")}
        onRetry={() => window.location.reload()}
      />
    </div>
  );
}

export function RouteElement({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<RouteLoading />}>
      {children}
    </Suspense>
  );
}
