import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { I18nProvider } from "../shared/i18n";
import { ThemeProvider } from "../shared/theme/ThemeContext";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });
}

export function renderWithProviders(
  _ui: ReactElement,
  { initialEntries = ["/"] }: { initialEntries?: string[] } = {}
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <I18nProvider>
          <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
          </QueryClientProvider>
        </I18nProvider>
      </ThemeProvider>
    );
  }

  return { Wrapper, queryClient };
}
