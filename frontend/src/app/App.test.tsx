import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";

import { I18nProvider } from "../shared/i18n";
import { ThemeProvider } from "../shared/theme";
import { createTestQueryClient } from "../test/renderWithProviders";
import { server } from "../test/server";

import { App } from "./App";

function Wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <ThemeProvider>
      <I18nProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}

describe("App shell", () => {
  it("renders responsive navigation, live status, and toggles", async () => {
    render(<Wrapper><App /></Wrapper>);

    expect(screen.getByRole("banner")).toHaveTextContent("QuantFish");
    expect(screen.getByRole("navigation", { name: /主导航/i })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /移动导航/i })).toBeInTheDocument();
    expect(screen.getByText(/^实时$/i)).toBeInTheDocument();
    expect(await screen.findByText(/未登录/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /登录/i })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("button", { name: /切换主题/i })).toBeInTheDocument();
    const languageButton = screen.getByRole("button", { name: /切换语言/i });
    expect(languageButton).toHaveTextContent("中");

    await userEvent.click(languageButton);

    expect(screen.getByRole("banner")).toHaveTextContent("QuantFish");
    expect(screen.getByText(/^Live$/i)).toBeInTheDocument();
    expect(screen.getByText(/Not logged in/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /toggle language/i })).toHaveTextContent("EN");
  });

  it("shows the logged-in team in the top banner and logs out", async () => {
    let logoutCalled = false;
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.post("/api/session/logout", () => {
        logoutCalled = true;
        return HttpResponse.json({
          authenticated: false,
          team_id: null,
          team_name: null
        });
      })
    );

    render(<Wrapper><App /></Wrapper>);

    expect(await screen.findByText(/Alpha Desk/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /退出登录|log out/i }));

    expect(logoutCalled).toBe(true);
    expect(await screen.findByText(/未登录/)).toBeInTheDocument();
  });

  it("points the collapse arrow toward the action that will happen next", async () => {
    render(<Wrapper><App /></Wrapper>);

    const collapseButton = screen.getByRole("button", { name: /收起侧边栏/i });
    expect(collapseButton.querySelector(".lucide-chevrons-left")).toBeInTheDocument();

    await userEvent.click(collapseButton);

    const expandButton = screen.getByRole("button", { name: /展开侧边栏/i });
    expect(expandButton.querySelector(".lucide-chevrons-right")).toBeInTheDocument();
  });
});
