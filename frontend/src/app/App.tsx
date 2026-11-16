import { Outlet } from "react-router-dom";

import { Shell } from "../shared/layout";

export function App() {
  return (
    <Shell>
      <Outlet />
    </Shell>
  );
}
