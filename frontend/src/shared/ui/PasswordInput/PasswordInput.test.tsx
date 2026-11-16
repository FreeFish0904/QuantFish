import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { I18nProvider } from "../../i18n";
import { PasswordInput } from "./PasswordInput";

describe("PasswordInput", () => {
  it("lets users reveal and hide a password without changing its value", async () => {
    render(
      <I18nProvider defaultLanguage="en">
        <PasswordInput aria-label="Team password" defaultValue="secret" />
      </I18nProvider>
    );

    const input = screen.getByLabelText("Team password");
    expect(input).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("secret");

    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input).toHaveAttribute("type", "password");
  });
});
