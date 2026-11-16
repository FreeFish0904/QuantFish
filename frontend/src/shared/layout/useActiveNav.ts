import { useLocation, useNavigate } from "react-router-dom";

import { navItems } from "./navConfig";

export function useActiveNav() {
  const location = useLocation();
  const navigate = useNavigate();

  const activeItem = location.pathname.startsWith("/submissions/")
    ? navItems.find((item) => item.key === "leaderboard")
    : navItems.find((item) =>
        item.href === "/" ? location.pathname === "/" : location.pathname.startsWith(item.href)
      );

  return {
    activeKey: activeItem?.key,
    navigate: (href: string) => navigate(href)
  };
}
