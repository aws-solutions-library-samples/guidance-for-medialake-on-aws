import { describe, expect, it } from "vitest";
import {
  federatedProviders,
  hasCognitoProvider,
  isFederatedProvider,
  type IdentityProvider,
} from "./identityProviders";

const cognito: IdentityProvider = { identity_provider_method: "cognito" };
const okta: IdentityProvider = { identity_provider_method: "saml", identity_provider_name: "Okta" };
const entra: IdentityProvider = {
  identity_provider_method: "oidc",
  identity_provider_name: "Entra",
};

describe("identity provider helpers", () => {
  it("treats SAML and OIDC providers as federated", () => {
    expect(isFederatedProvider(okta)).toBe(true);
    expect(isFederatedProvider(entra)).toBe(true);
    expect(isFederatedProvider(cognito)).toBe(false);
  });

  it("ignores federated providers without a name, which cannot be redirected to", () => {
    expect(isFederatedProvider({ identity_provider_method: "oidc" })).toBe(false);
    expect(
      isFederatedProvider({ identity_provider_method: "saml", identity_provider_name: "" })
    ).toBe(false);
  });

  it("lists federated providers in config order", () => {
    expect(federatedProviders([okta, cognito, entra]).map((p) => p.identity_provider_name)).toEqual(
      ["Okta", "Entra"]
    );
    expect(federatedProviders(undefined)).toEqual([]);
  });

  it("detects the Cognito password provider", () => {
    expect(hasCognitoProvider([entra, cognito])).toBe(true);
    expect(hasCognitoProvider([entra])).toBe(false);
    expect(hasCognitoProvider(null)).toBe(false);
  });
});
