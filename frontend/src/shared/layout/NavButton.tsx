import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "../i18n";
import styles from "./NavButton.module.css";

export type NavItem = {
  key: string;
  labelKey: string;
  shortLabelKey: string;
  icon: LucideIcon;
  href: string;
};

type NavButtonProps = {
  item: NavItem;
  active: boolean;
  compact?: boolean;
  mobile?: boolean;
};

export function NavButton({ item, active, compact, mobile }: NavButtonProps) {
  const { t } = useI18n();
  const Icon = item.icon;
  const label = t(item.labelKey);

  return (
    <Link
      className={[
        styles.button,
        active ? styles.active : "",
        compact ? styles.compact : "",
        mobile ? styles.mobile : ""
      ].join(" ")}
      aria-current={active ? "page" : undefined}
      to={item.href}
      title={compact ? label : undefined}
    >
      <Icon aria-hidden="true" size={mobile ? 20 : 18} />
      {!compact && <span>{label}</span>}
      {mobile && <span>{t(item.shortLabelKey)}</span>}
    </Link>
  );
}
