import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  RouterProvider,
  createBrowserRouter,
  createHashRouter
} from "react-router-dom";

import { DEMO_MODE, DemoBanner, enableDemoMode } from "./demo";
import { routes } from "./routes";
import { I18nProvider } from "./shared/i18n";
import { ThemeProvider } from "./shared/theme";
import "./theme/globals.css";

const queryClient = new QueryClient();

async function bootstrap(): Promise<void> {
  await enableDemoMode();

  // Hash routing keeps the static demo working on GitHub Pages sub-paths.
  const createRouter = DEMO_MODE ? createHashRouter : createBrowserRouter;
  const router = createRouter(routes);

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ThemeProvider>
        <I18nProvider>
          <QueryClientProvider client={queryClient}>
            {DEMO_MODE ? <DemoBanner /> : null}
            <RouterProvider router={router} />
          </QueryClientProvider>
        </I18nProvider>
      </ThemeProvider>
    </StrictMode>
  );
}

void bootstrap();

