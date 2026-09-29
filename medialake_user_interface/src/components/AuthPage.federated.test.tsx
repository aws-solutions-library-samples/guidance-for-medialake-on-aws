import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import type { IdentityProvider } from "../common/helpers/identityProviders";

const signInWithRedirect = vi.fn(() => Promise.resolve());

vi.mock("aws-amplify/auth", () => ({
  signIn: vi.fn(),
  confirmSignIn: vi.fn(),
  signInWithRedirect: (...args: unknown[]) => signInWithRedirect(...(args as [])),
  resetPassword: vi.fn(),
  confirmResetPassword: vi.fn(),
  fetchAuthSession: vi.fn(),
  getCurrentUser: vi.fn(),
}));

// The Amplify form isn't what's under test; keep it out of the render.
vi.mock("@aws-amplify/ui-react", () => ({
  Authenticator: () => <div data-testid="password-sign-in" />,
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../common/hooks/auth-context", () => ({
  useAuth: () => ({ completeLogin: vi.fn(), isAuthenticated: false }),
}));

let providers: IdentityProvider[] = [];
vi.mock("../common/hooks/aws-config-context", () => ({
  useAwsConfig: () => ({
    Auth: {
      identity_providers: providers,
      Cognito: { userPoolId: "p", userPoolClientId: "c", identityPoolId: "i", domain: "d" },
    },
    API: {},
  }),
}));

import AuthPage from "./AuthPage";

function renderPage(configured: IdentityProvider[]) {
  providers = configured;
  return render(
    <MemoryRouter initialEntries={["/sign-in"]}>
      <AuthPage />
    </MemoryRouter>
  );
}

describe("AuthPage federated sign-in", () => {
  beforeEach(() => signInWithRedirect.mockClear());

  it("shows a button for an OIDC provider and redirects to it", async () => {
    renderPage([
      { identity_provider_method: "cognito" },
      { identity_provider_method: "oidc", identity_provider_name: "Entra" },
    ]);

    await userEvent.click(screen.getByRole("button", { name: "Sign in with Entra" }));

    expect(signInWithRedirect).toHaveBeenCalledWith({ provider: { custom: "Entra" } });
    expect(screen.getByText("OR")).toBeInTheDocument();
    expect(screen.getByTestId("password-sign-in")).toBeInTheDocument();
  });

  it("still shows SAML providers, one button each, in config order", () => {
    renderPage([
      { identity_provider_method: "saml", identity_provider_name: "Okta" },
      { identity_provider_method: "oidc", identity_provider_name: "Entra" },
    ]);

    const buttons = screen
      .getAllByRole("button")
      .map((b) => b.textContent)
      .filter((text) => text?.startsWith("Sign in with"));
    expect(buttons).toEqual(["Sign in with Okta", "Sign in with Entra"]);
    // No password form without the cognito provider, so no divider either.
    expect(screen.queryByText("OR")).not.toBeInTheDocument();
    expect(screen.queryByTestId("password-sign-in")).not.toBeInTheDocument();
  });

  it("shows only the password form for a Cognito-only config", () => {
    renderPage([{ identity_provider_method: "cognito" }]);

    expect(screen.queryByRole("button", { name: /^Sign in with/ })).not.toBeInTheDocument();
    expect(screen.queryByText("OR")).not.toBeInTheDocument();
    expect(screen.getByTestId("password-sign-in")).toBeInTheDocument();
  });
});
