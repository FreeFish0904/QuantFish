import { useI18n } from "../i18n";
import { navItems } from "./navConfig";
import { NavButton } from "./NavButton";
import styles from "./Layout.module.css";
import { useActiveNav } from "./useActiveNav";

export function MobileNav() {
  const { activeKey } = useActiveNav();
  const { t } = useI18n();

  return (
    <nav aria-label={t("common.mobileNavigation")} className={styles.mobileNav}>
      {navItems.map((item) => (
        <NavButton
          key={item.key}
          active={activeKey === item.key}
          compact
          item={item}
          mobile
        />
      ))}
    </nav>
  );
}
