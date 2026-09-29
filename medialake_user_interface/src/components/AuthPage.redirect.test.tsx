import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

vi.mock("aws-amplify/auth", () => ({
  signIn: vi.fn(),
  confirmSignIn: vi.fn(),
  signInWithRedirect: vi.fn(),
  resetPassword: vi.fn(),
  confirmResetPassword: vi.fn(),
  fetchAuthSession: vi.fn(),
  getCurrentUser: vi.fn(),
}));

vi.mock("@aws-amplify/ui-react", () => ({
  Authenticator: () => <div data-testid="password-sign-in" />,
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const auth = { isAuthenticated: false, isLoading: false, isInitialized: true };
vi.mock("../common/hooks/auth-context", () => ({
  useAuth: () => ({ completeLogin: vi.fn(), ...auth }),
}));

vi.mock("../common/hooks/aws-config-context", () => ({
  useAwsConfig: () => ({
    Auth: {
      identity_providers: [{ identity_provider_method: "cognito" }],
      Cognito: { userPoolId: "p", userPoolClientId: "c", identityPoolId: "i", domain: "d" },
    },
    API: {},
  }),
}));

import AuthPage from "./AuthPage";
import { ProtectedRoute } from "./ProtectedRoute";

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search + location.hash}</div>;
};

function renderSignIn(state: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/sign-in", state }]}>
      <Routes>
        <Route path="/sign-in" element={<AuthPage />} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AuthPage post-login redirect", () => {
  beforeEach(() => {
    auth.isAuthenticated = true;
  });

  it("returns to the deep link the user came from", async () => {
    renderSignIn({ from: { pathname: "/videos/1", search: "?t=5", hash: "#c" } });

    expect(await screen.findByTestId("location")).toHaveTextContent("/videos/1?t=5#c");
  });

  it("goes to / when there is no from", async () => {
    renderSignIn(undefined);

    expect(await screen.findByTestId("location")).toHaveTextContent(/^\/$/);
  });

  it.each([["//evil.com"], ["/sign-in"], ["https://evil.com"]])(
    "falls back to / for from=%s",
    async (pathname) => {
      renderSignIn({ from: { pathname } });

      expect(await screen.findByTestId("location")).toHaveTextContent(/^\/$/);
    }
  );
});

describe("ProtectedRoute -> AuthPage round trip", () => {
  it("remembers the requested location and returns there after sign-in", async () => {
    auth.isAuthenticated = false;
    const app = () => (
      <MemoryRouter initialEntries={["/images/42?x=1#h"]}>
        <Routes>
          <Route path="/sign-in" element={<AuthPage />} />
          <Route
            path="*"
            element={
              <ProtectedRoute>
                <LocationProbe />
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    const view = render(app());

    // Not signed in: ProtectedRoute sends the user to the sign-in page.
    expect(await screen.findByTestId("password-sign-in")).toBeInTheDocument();

    // Sign-in completes: AuthPage takes the user back to the original URL.
    auth.isAuthenticated = true;
    view.rerender(app());

    expect(await screen.findByTestId("location")).toHaveTextContent("/images/42?x=1#h");
  });
});
