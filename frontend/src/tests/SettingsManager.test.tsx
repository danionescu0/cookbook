import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsManager } from "../backoffice/SettingsManager";
import { LanguageProvider } from "../i18n/LanguageContext";
import { api } from "../api/client";
import type { Settings } from "../types";

vi.mock("../api/client", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const baseSettings: Settings = {
  supported_languages: "ro,en",
  default_language: "ro",
  admin_password_is_set: true,
  anthropic_api_key_is_set: false,
  default_rate_limit_requests_per_minute: 6,
  scrape_timeout_seconds: 15,
  max_html_chars: 200_000,
  image_max_dimension: 1600,
  image_max_size_kb: 500,
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getSettings.mockResolvedValue(baseSettings);
});

function renderManager() {
  return render(
    <LanguageProvider>
      <SettingsManager />
    </LanguageProvider>
  );
}

describe("SettingsManager", () => {
  it("loads and displays the current settings", async () => {
    renderManager();

    expect(await screen.findByLabelText("Supported languages")).toHaveValue("ro,en");
    expect(screen.getByLabelText("Default language")).toHaveValue("ro");
    expect(screen.getByLabelText("Import rate limit (requests/minute)")).toHaveValue(6);
    expect(screen.getByLabelText("Max image size (KB)")).toHaveValue(500);
  });

  it("leaves secret fields blank and hints whether one is currently set", async () => {
    renderManager();
    await screen.findByLabelText("Supported languages");

    expect(screen.getByLabelText("Back office password")).toHaveValue("");
    expect(screen.getByLabelText("Back office password")).toHaveAttribute(
      "placeholder",
      "Leave blank to keep the current value"
    );
    expect(screen.getByLabelText("Anthropic API key")).toHaveAttribute("placeholder", "Not set");
  });

  it("applies changes without secrets when they're left blank", async () => {
    const user = userEvent.setup();
    mockedApi.updateSettings.mockResolvedValue(baseSettings);

    renderManager();
    const rateLimitInput = await screen.findByLabelText("Import rate limit (requests/minute)");
    await user.clear(rateLimitInput);
    await user.type(rateLimitInput, "30");

    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(mockedApi.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          supported_languages: "ro,en",
          default_language: "ro",
          default_rate_limit_requests_per_minute: 30,
        })
      )
    );
    const payload = mockedApi.updateSettings.mock.calls[0][0];
    expect(payload).not.toHaveProperty("admin_password");
    expect(payload).not.toHaveProperty("anthropic_api_key");
    expect(await screen.findByText("Settings applied.")).toBeInTheDocument();
  });

  it("includes a secret in the payload only when the admin types a new value", async () => {
    const user = userEvent.setup();
    mockedApi.updateSettings.mockResolvedValue({ ...baseSettings, admin_password_is_set: true });

    renderManager();
    await user.type(await screen.findByLabelText("Back office password"), "new-password");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(mockedApi.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ admin_password: "new-password" })
      )
    );
  });

  it("shows an error message when applying fails", async () => {
    const user = userEvent.setup();
    mockedApi.updateSettings.mockRejectedValue(new Error("boom"));

    renderManager();
    await screen.findByLabelText("Supported languages");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});
