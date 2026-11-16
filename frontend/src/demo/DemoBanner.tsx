import { Sparkles } from "lucide-react";

import { useI18n } from "../shared/i18n";
import styles from "./DemoBanner.module.css";

export function DemoBanner() {
  const { t } = useI18n();

  return (
    <aside className={styles.banner} role="status">
      <Sparkles aria-hidden="true" size={14} />
      <span className={styles.label}>{t("demo.badge")}</span>
      <span className={styles.message}>{t("demo.message")}</span>
    </aside>
  );
}
