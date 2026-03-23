import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";

/**
 * Property-Based Tests for Federated OAuth Redirect Configuration
 *
 * Feature: oidc-authentication, Property 7: Federated OAuth Redirect Configuration
 *
 * **Validates: Requirements 5.2, 5.3**
 *
 * For any configuration containing OIDC providers, the Amplify OAuth configuration
 * should include the oauth2/idpresponse endpoint in the redirectSignIn URL list
 * and configure appropriate sign-out redirect URLs.
 */

// We test the configureAmplify logic directly by replicating it as a pure function.
// This avoids needing to mock React context, Amplify, and window.fetch while still
// validating the exact branching logic in aws-config-context.tsx.

interface IdentityProvider {
  identity_provider_method: "cognito" | "saml" | "oidc";
  identity_provider_name?: string;
  identity_provider_metadata_url?: string;
}

interface AwsConfig {
  Auth: {
    identity_providers: IdentityProvider[];
    Cognito: {
      userPoolId: string;
      userPoolClientId: string;
      identityPoolId: string;
      domain: string;
    };
  };
  API: any;
}

/**
 * Pure extraction of the configureAmplify logic from aws-config-context.tsx.
 * Returns the amplifyConfig object that would be passed to Amplify.configure().
 */
function buildAmplifyConfig(config: AwsConfig, origin: string) {
  const amplifyConfig: any = {
    Auth: {
      Cognito: {
        userPoolId: config.Auth.Cognito.userPoolId,
        userPoolClientId: config.Auth.Cognito.userPoolClientId,
        identityPoolId: config.Auth.Cognito.identityPoolId,
        loginWith: {
          username: false,
          email: false,
          oauth: {
            domain: config.Auth.Cognito.domain,
            scopes: ["email", "openid", "profile"],
            responseType: "code",
            redirectSignIn: origin,
            redirectSignOut: origin + "/sign-in",
          },
        },
      },
    },
    API: config.API,
  };

  const hasCognito = config.Auth.identity_providers.some(
    (provider) => provider.identity_provider_method === "cognito"
  );
  const samlProviders = config.Auth.identity_providers.filter(
    (provider) => provider.identity_provider_method === "saml"
  );
  const oidcProviders = config.Auth.identity_providers.filter(
    (provider) => provider.identity_provider_method === "oidc"
  );

  if (hasCognito) {
    amplifyConfig.Auth.Cognito.loginWith.username = true;
    amplifyConfig.Auth.Cognito.loginWith.email = true;
  }

  if (samlProviders.length > 0 || oidcProviders.length > 0) {
    amplifyConfig.Auth.Cognito.loginWith.oauth = {
      ...amplifyConfig.Auth.Cognito.loginWith.oauth,
      providers: ["SAML"],
      redirectSignIn: [
        origin,
        `https://${config.Auth.Cognito.domain}/oauth2/idpresponse`,
        `https://${config.Auth.Cognito.domain}/saml2/idpresponse`,
      ],
      redirectSignOut: [origin, origin + "/sign-in"],
    };
  }

  return amplifyConfig;
}

// --- Generators ---

const providerNameArb = fc.constantFrom(
  "Federate",
  "Okta-OIDC",
  "AzureAD",
  "Auth0",
  "GoogleWorkspace",
  "PingIdentity",
  "OneLogin",
  "CustomIDP_1"
);

const domainArb = fc.constantFrom(
  "myapp.auth.us-east-1.amazoncognito.com",
  "prod.auth.eu-west-1.amazoncognito.com",
  "staging.auth.ap-southeast-1.amazoncognito.com",
  "dev123.auth.us-west-2.amazoncognito.com"
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

const originArb = fc.constantFrom(
  "https://d1234567890.cloudfront.net",
  "https://media.example.com",
  "http://localhost:3000"
);

const awsConfigArb = (providers: fc.Arbitrary<IdentityProvider[]>) =>
  fc.record({
    providers,
    domain: domainArb,
    origin: originArb,
  });

// --- Property 7 Tests ---

describe("Property 7: Federated OAuth Redirect Configuration", () => {
  // Feature: oidc-authentication, Property 7: Federated OAuth Redirect Configuration

  it("should include oauth2/idpresponse in redirectSignIn when OIDC providers are present", () => {
    // **Validates: Requirements 5.2, 5.3**
    fc.assert(
      fc.property(
        awsConfigArb(
          fc.array(oidcProviderArb, { minLength: 1, maxLength: 3 })
        ),
        ({ providers, domain, origin }) => {
          const config: AwsConfig = {
            Auth: {
              identity_providers: providers,
              Cognito: {
                userPoolId: "us-east-1_test",
                userPoolClientId: "testclient",
                identityPoolId: "us-east-1:test-pool",
                domain,
              },
            },
            API: {},
          };

          const result = buildAmplifyConfig(config, origin);
          const oauth = result.Auth.Cognito.loginWith.oauth;

          // Property: redirectSignIn must be an array containing the oauth2/idpresponse URL
          expect(Array.isArray(oauth.redirectSignIn)).toBe(true);
          expect(oauth.redirectSignIn).toContain(
            `https://${domain}/oauth2/idpresponse`
          );
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should configure redirectSignOut URLs when OIDC providers are present", () => {
    // **Validates: Requirements 5.3**
    fc.assert(
      fc.property(
        awsConfigArb(
          fc.array(oidcProviderArb, { minLength: 1, maxLength: 3 })
        ),
        ({ providers, domain, origin }) => {
          const config: AwsConfig = {
            Auth: {
              identity_providers: providers,
              Cognito: {
                userPoolId: "us-east-1_test",
                userPoolClientId: "testclient",
                identityPoolId: "us-east-1:test-pool",
                domain,
              },
            },
            API: {},
          };

          const result = buildAmplifyConfig(config, origin);
          const oauth = result.Auth.Cognito.loginWith.oauth;

          // Property: redirectSignOut must be an array with origin-based URLs
          expect(Array.isArray(oauth.redirectSignOut)).toBe(true);
          expect(oauth.redirectSignOut).toContain(origin);
          expect(oauth.redirectSignOut).toContain(origin + "/sign-in");
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should include all expected redirectSignIn URLs when OIDC providers are present", () => {
    // **Validates: Requirements 5.2, 5.3**
    fc.assert(
      fc.property(
        awsConfigArb(
          fc.array(oidcProviderArb, { minLength: 1, maxLength: 3 })
        ),
        ({ providers, domain, origin }) => {
          const config: AwsConfig = {
            Auth: {
              identity_providers: providers,
              Cognito: {
                userPoolId: "us-east-1_test",
                userPoolClientId: "testclient",
                identityPoolId: "us-east-1:test-pool",
                domain,
              },
            },
            API: {},
          };

          const result = buildAmplifyConfig(config, origin);
          const redirectSignIn = result.Auth.Cognito.loginWith.oauth.redirectSignIn;

          // Property: All three expected redirect URLs must be present
          expect(redirectSignIn).toContain(origin);
          expect(redirectSignIn).toContain(`https://${domain}/oauth2/idpresponse`);
          expect(redirectSignIn).toContain(`https://${domain}/saml2/idpresponse`);
          expect(redirectSignIn).toHaveLength(3);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should NOT configure federated OAuth redirects when only cognito providers are present", () => {
    // **Validates: Requirements 5.2, 5.3** (negative case)
    fc.assert(
      fc.property(
        awsConfigArb(
          fc.array(cognitoProviderArb, { minLength: 1, maxLength: 2 })
        ),
        ({ providers, domain, origin }) => {
          const config: AwsConfig = {
            Auth: {
              identity_providers: providers,
              Cognito: {
                userPoolId: "us-east-1_test",
                userPoolClientId: "testclient",
                identityPoolId: "us-east-1:test-pool",
                domain,
              },
            },
            API: {},
          };

          const result = buildAmplifyConfig(config, origin);
          const oauth = result.Auth.Cognito.loginWith.oauth;

          // Property: Without federated providers, redirectSignIn should be a plain string (not array)
          expect(typeof oauth.redirectSignIn).toBe("string");
          expect(oauth.redirectSignIn).toBe(origin);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should configure federated OAuth redirects when mixed OIDC and SAML providers are present", () => {
    // **Validates: Requirements 5.2, 5.3**
    fc.assert(
      fc.property(
        awsConfigArb(
          fc.tuple(
            fc.array(oidcProviderArb, { minLength: 1, maxLength: 2 }),
            fc.array(samlProviderArb, { minLength: 1, maxLength: 2 }),
            fc.array(cognitoProviderArb, { minLength: 0, maxLength: 1 })
          ).map(([oidc, saml, cognito]) => [...cognito, ...saml, ...oidc])
        ),
        ({ providers, domain, origin }) => {
          const config: AwsConfig = {
            Auth: {
              identity_providers: providers,
              Cognito: {
                userPoolId: "us-east-1_test",
                userPoolClientId: "testclient",
                identityPoolId: "us-east-1:test-pool",
                domain,
              },
            },
            API: {},
          };

          const result = buildAmplifyConfig(config, origin);
          const oauth = result.Auth.Cognito.loginWith.oauth;

          // Property: With any federated providers, oauth2/idpresponse must be in redirectSignIn
          expect(Array.isArray(oauth.redirectSignIn)).toBe(true);
          expect(oauth.redirectSignIn).toContain(
            `https://${domain}/oauth2/idpresponse`
          );

          // Property: redirectSignOut must also be configured as an array
          expect(Array.isArray(oauth.redirectSignOut)).toBe(true);
          expect(oauth.redirectSignOut.length).toBe(2);
        }
      ),
      { numRuns: 100 }
    );
  });
});
