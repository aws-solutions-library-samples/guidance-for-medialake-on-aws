/**
 * Identity providers as listed in aws-exports.json (``Auth.identity_providers``),
 * which mirrors ``authZ.identity_providers`` in config.json.
 */
export type IdentityProviderMethod = "cognito" | "saml" | "oidc";

export interface IdentityProvider {
  identity_provider_method: IdentityProviderMethod;
  identity_provider_name?: string;
  identity_provider_metadata_url?: string;
  identity_provider_metadata_path?: string;
}

export interface NamedFederatedProvider extends IdentityProvider {
  identity_provider_method: "saml" | "oidc";
  identity_provider_name: string;
}

/** SAML and OIDC providers sign in through a redirect to the Cognito hosted UI. */
export function isFederatedProvider(
  provider: IdentityProvider | null | undefined
): provider is NamedFederatedProvider {
  const method = provider?.identity_provider_method;
  return (method === "saml" || method === "oidc") && !!provider?.identity_provider_name;
}

export function federatedProviders(
  providers: ReadonlyArray<IdentityProvider> | null | undefined
): NamedFederatedProvider[] {
  return (providers ?? []).filter(isFederatedProvider);
}

export function hasCognitoProvider(
  providers: ReadonlyArray<IdentityProvider> | null | undefined
): boolean {
  return (providers ?? []).some((p) => p.identity_provider_method === "cognito");
}
