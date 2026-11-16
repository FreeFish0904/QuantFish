import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { routes } from "./routes";
import { I18nProvider } from "./shared/i18n";
import { ThemeProvider } from "./shared/theme/ThemeContext";
import "./theme/globals.css";

const queryClient = new QueryClient();
const router = createBrowserRouter(routes);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>
);
