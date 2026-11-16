import {
  BarChart3,
  Gauge,
  LineChart,
  Settings,
  UploadCloud
} from "lucide-react";

import { useI18n } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/Button/Button";
import styles from "./AdminTabs.module.css";

export type AdminSection =
  | "overview"
  | "dataset"
  | "execution"
  | "teams"
  | "submissions";

type AdminTab = {
  section: AdminSection;
  labelKey: `admin.${AdminSection}`;
  Icon: typeof Gauge;
};

const tabs: AdminTab[] = [
  { section: "overview", labelKey: "admin.overview", Icon: Gauge },
  { section: "dataset", labelKey: "admin.dataset", Icon: BarChart3 },
  { section: "execution", labelKey: "admin.execution", Icon: LineChart },
  { section: "teams", labelKey: "admin.teams", Icon: Settings },
  { section: "submissions", labelKey: "admin.submissions", Icon: UploadCloud }
];

export type AdminTabsProps = {
  activeSection: AdminSection;
  onSelect: (section: AdminSection) => void;
};

export function AdminTabs({ activeSection, onSelect }: AdminTabsProps) {
  const { t } = useI18n();

  return (
    <nav className={styles.tabs} aria-label={t("admin.eyebrow")}>
      <div className={styles.tablist} role="tablist">
        {tabs.map(({ section, labelKey, Icon }) => {
        const selected = activeSection === section;
        return (
          <Button
            key={section}
            aria-controls={`admin-panel-${section}`}
            aria-selected={selected}
            className={[styles.tab, selected ? styles.active : ""].join(" ")}
            id={`admin-tab-${section}`}
            onClick={() => onSelect(section)}
            role="tab"
            variant="ghost"
          >
            <Icon aria-hidden="true" size={16} />
            <span>{t(labelKey)}</span>
          </Button>
        );
      })}
      </div>
    </nav>
  );
}
