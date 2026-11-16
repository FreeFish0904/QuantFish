import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { server } from "../../test/server";
import { LoginView } from "./view";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <I18nProvider defaultLanguage="en">
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>{children}</MemoryRouter>
        </QueryClientProvider>
      </I18nProvider>
    );
  };
}

describe("LoginView", () => {
  it("logs in with team credentials and shows the active team", async () => {
    let requestBody: unknown = null;
    server.use(
      http.post("/api/session/login", async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        });
      })
    );

    render(<LoginView />, { wrapper: createWrapper() });

    expect(screen.getByText(/enter both fields to continue/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/team name/i), "Alpha Desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /show password/i }));
    expect(screen.getByLabelText(/team password/i)).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(requestBody).toEqual({ team_name: "Alpha Desk", password: "secret" })
    );
    expect(await screen.findByText(/logged in as Alpha Desk/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /submit strategy/i })).toHaveAttribute(
      "href",
      "/submit"
    );
  });
});
