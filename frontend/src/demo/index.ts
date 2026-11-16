import { DemoBanner } from "./DemoBanner";
import { enableDemoMode } from "./enableDemoMode";

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

export { DemoBanner, enableDemoMode };
