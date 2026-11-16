import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "../i18n";
import { navItems } from "./navConfig";
import { NavButton } from "./NavButton";
import styles from "./Layout.module.css";
import { useActiveNav } from "./useActiveNav";

export function Sidebar({
  collapsed,
  onToggleCollapse
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const { activeKey } = useActiveNav();
  const { t } = useI18n();

  return (
    <aside
      className={[styles.sidebar, collapsed ? styles.sidebarCollapsed : ""].join(" ")}
      aria-expanded={!collapsed}
    >
      <Link className={styles.brand} to="/" title={t("brand.name")}>
        <div className={styles.brandMark}>{t("brand.shortMark")}</div>
        {!collapsed && (
          <div className={styles.brandTitle}>
            <strong className={styles.brandName}>{t("brand.name")}</strong>
          </div>
        )}
      </Link>
      <nav aria-label={t("common.primaryNavigation")} className={styles.nav}>
        {navItems.map((item) => (
          <NavButton
            key={item.key}
            active={activeKey === item.key}
            compact={collapsed}
            item={item}
          />
        ))}
      </nav>
      <button
        className={[styles.iconButton, styles.collapse].join(" ")}
        type="button"
        aria-label={collapsed ? t("common.expandSidebar") : t("common.collapseSidebar")}
        onClick={onToggleCollapse}
      >
        {collapsed ? (
          <ChevronsRight aria-hidden="true" size={18} />
        ) : (
          <ChevronsLeft aria-hidden="true" size={18} />
        )}
      </button>
    </aside>
  );
}
