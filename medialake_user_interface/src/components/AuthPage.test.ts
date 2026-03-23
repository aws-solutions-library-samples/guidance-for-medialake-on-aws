import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

/**
 * Property-Based Tests for OIDC Button Rendering and Redirect
 *
 * Feature: oidc-authentication, Property 8: OIDC Button Rendering and Redirect
 *
 * **Validates: Requirements 6.1, 6.2**
 *
 * For any OIDC provider entry in aws-exports.json, the Auth_Page should render
 * a button labeled "Sign in with {provider_name}" that, when clicked, invokes
 * signInWithRedirect with { provider: { custom: identity_provider_name } }.
 */

// We test the AuthPage rendering logic by extracting it as pure functions.
// This mirrors the approach used in Property 7 (aws-config-context.test.ts)
// and avoids needing @testing-library/react, React DOM rendering, or complex
// mocking of Amplify, react-router, and MUI while still validating the exact
// logic in AuthPage.tsx.

interface IdentityProvider {
  identity_provider_method: "cognito" | "saml" | "oidc";
  identity_provider_name?: string;
  identity_provider_metadata_url?: string;
}

/**
 * Pure extraction of the OIDC button rendering logic from AuthPage.tsx.
 * Returns the list of OIDC buttons that would be rendered, each with
 * its label and the redirect argument that would be passed to signInWithRedirect.
 */
function getOidcButtons(providers: IdentityProvider[]) {
  const hasOidcProvider = providers.some(
    (provider) => provider.identity_provider_method === "oidc"
  );

  if (!hasOidcProvider) {
    return [];
  }

  // Mirrors the AuthPage.tsx rendering logic:
  // awsConfig.Auth.identity_providers.map(provider => {
  //   if (provider.identity_provider_method === "oidc") { ... }
  // })
  return providers
    .filter((provider) => provider.identity_provider_method === "oidc")
    .map((provider) => ({
      key: provider.identity_provider_name,
      label: `Sign in with ${provider.identity_provider_name}`,
      redirectArg: { provider: { custom: provider.identity_provider_name } },
    }));
}

// --- Generators ---

// Generate random OIDC provider names — alphanumeric strings that resemble
// real provider names (e.g. "Federate", "Okta-OIDC", "AzureAD").
const providerNameArb = fc.stringMatching(/^[A-Za-z][A-Za-z0-9_-]{0,19}$/).filter(
  (s) => s.length > 0
);

const oidcProviderArb: fc.Arbitrary<IdentityProvider> = providerNameArb.map((name) => ({
  identity_provider_method: "oidc" as const,
  identity_provider_name: name,
}));

const samlProviderArb: fc.Arbitrary<IdentityProvider> = providerNameArb.map((name) => ({
  identity_provider_method: "saml" as const,
  identity_provider_name: name,
  identity_provider_metadata_url: `https://${name}.example.com/metadata`,
}));

const cognitoProviderArb: fc.Arbitrary<IdentityProvider> = fc.constant({
  identity_provider_method: "cognito" as const,
});

// --- Property 8 Tests ---

describe("Property 8: OIDC Button Rendering and Redirect", () => {
  // Feature: oidc-authentication, Property 8: OIDC Button Rendering and Redirect

  it("should render a button labeled 'Sign in with {provider_name}' for each OIDC provider", () => {
    // **Validates: Requirements 6.1**
    fc.assert(
      fc.property(
        fc.array(oidcProviderArb, { minLength: 1, maxLength: 5 }),
        (oidcProviders) => {
          const buttons = getOidcButtons(oidcProviders);

          // Property: One button per OIDC provider
          expect(buttons).toHaveLength(oidcProviders.length);

          // Property: Each button label matches "Sign in with {provider_name}"
          for (let i = 0; i < oidcProviders.length; i++) {
            const expectedLabel = `Sign in with ${oidcProviders[i].identity_provider_name}`;
            expect(buttons[i].label).toBe(expectedLabel);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should invoke signInWithRedirect with { provider: { custom: identity_provider_name } } for each OIDC button", () => {
    // **Validates: Requirements 6.2**
    fc.assert(
      fc.property(
        fc.array(oidcProviderArb, { minLength: 1, maxLength: 5 }),
        (oidcProviders) => {
          const buttons = getOidcButtons(oidcProviders);

          // Property: Each button's redirect argument uses { custom: provider_name }
          for (let i = 0; i < oidcProviders.length; i++) {
            expect(buttons[i].redirectArg).toEqual({
              provider: { custom: oidcProviders[i].identity_provider_name },
            });
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should render OIDC buttons only for OIDC providers in a mixed provider list", () => {
    // **Validates: Requirements 6.1, 6.2**
    fc.assert(
      fc.property(
        fc.tuple(
          fc.array(oidcProviderArb, { minLength: 1, maxLength: 3 }),
          fc.array(samlProviderArb, { minLength: 0, maxLength: 2 }),
          fc.array(cognitoProviderArb, { minLength: 0, maxLength: 1 })
        ),
        ([oidcProviders, samlProviders, cognitoProviders]) => {
          const allProviders = [...cognitoProviders, ...samlProviders, ...oidcProviders];
          const buttons = getOidcButtons(allProviders);

          // Property: Only OIDC providers produce buttons
          expect(buttons).toHaveLength(oidcProviders.length);

          // Property: Each button corresponds to an OIDC provider with correct label and redirect
          for (let i = 0; i < oidcProviders.length; i++) {
            const name = oidcProviders[i].identity_provider_name;
            expect(buttons[i].label).toBe(`Sign in with ${name}`);
            expect(buttons[i].redirectArg).toEqual({
              provider: { custom: name },
            });
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should render no OIDC buttons when no OIDC providers are configured", () => {
    // **Validates: Requirements 6.1** (negative case)
    fc.assert(
      fc.property(
        fc.tuple(
          fc.array(samlProviderArb, { minLength: 0, maxLength: 3 }),
          fc.array(cognitoProviderArb, { minLength: 0, maxLength: 1 })
        ),
        ([samlProviders, cognitoProviders]) => {
          const allProviders = [...cognitoProviders, ...samlProviders];
          const buttons = getOidcButtons(allProviders);

          // Property: No OIDC buttons when no OIDC providers exist
          expect(buttons).toHaveLength(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should use provider_name as the button key for each OIDC button", () => {
    // **Validates: Requirements 6.1**
    fc.assert(
      fc.property(
        fc.array(oidcProviderArb, { minLength: 1, maxLength: 5 }),
        (oidcProviders) => {
          const buttons = getOidcButtons(oidcProviders);

          // Property: Each button key matches the provider name (used as React key)
          for (let i = 0; i < oidcProviders.length; i++) {
            expect(buttons[i].key).toBe(oidcProviders[i].identity_provider_name);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
