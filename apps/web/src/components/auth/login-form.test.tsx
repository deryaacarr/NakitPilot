import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm, loginSchema } from "./login-form";

const replace = vi.fn();
const refresh = vi.fn();
const loginRequest = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth/api", () => ({
  loginRequest: (...args: unknown[]) => loginRequest(...args),
}));

afterEach(() => {
  cleanup();
});

describe("loginSchema", () => {
  it("rejects empty password", () => {
    const result = loginSchema.safeParse({
      email: "a@b.com",
      password: "",
      remember: true,
    });
    expect(result.success).toBe(false);
  });
});

describe("LoginForm", () => {
  beforeEach(() => {
    replace.mockReset();
    refresh.mockReset();
    loginRequest.mockReset();
  });

  it("shows validation errors on empty submit", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(loginRequest).not.toHaveBeenCalled();
  });

  it("submits credentials and redirects on success", async () => {
    loginRequest.mockResolvedValue({
      ok: true,
      data: { access: "a", refresh: "r", user: { id: 1, email: "a@b.com" } },
    });
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.type(screen.getByLabelText("E-posta"), "demo@nakitpilot.local");
    await user.type(screen.getByLabelText("Şifre"), "DemoPass123!");
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    await waitFor(() => expect(loginRequest).toHaveBeenCalled());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows API error message", async () => {
    loginRequest.mockResolvedValue({
      ok: false,
      error: { code: "invalid_credentials", message: "E-posta veya şifre hatalı." },
    });
    const user = userEvent.setup();
    render(<LoginForm />);
    await user.type(screen.getByLabelText("E-posta"), "demo@nakitpilot.local");
    await user.type(screen.getByLabelText("Şifre"), "wrong");
    await user.click(screen.getByRole("button", { name: "Giriş yap" }));
    expect(await screen.findByText("E-posta veya şifre hatalı.")).toBeInTheDocument();
  });
});
