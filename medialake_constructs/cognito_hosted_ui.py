"""Hosted-UI settings the UI stack applies to the Cognito app client.

The app client is created in the Cognito stack, before the CloudFront
distribution exists, so its template only knows the Cognito hosted-domain
callback URLs. The UI stack adds the app's own URLs afterwards through the
``HostedUiAppClientUrls`` custom resource
(``lambdas/custom_resources/auth/app_client_callbacks``), which re-applies
them on every deploy because any CloudFormation update of the client resets
them.

These helpers decide what that resource sets.
"""

from typing import Iterable, List, Optional, Tuple

FEDERATED_METHODS = ("saml", "oidc")

# Local development (vite dev server). Kept from the original callback list.
LOCAL_CALLBACK_URLS = (
    "https://localhost:5173",
    "https://localhost:5173/",
    "https://localhost:5173/login",
)


def _method(provider) -> str:
    return str(getattr(provider, "identity_provider_method", "") or "").lower()


def _name(provider) -> str:
    return str(getattr(provider, "identity_provider_name", "") or "")


def hosted_ui_identity_providers(identity_providers: Iterable) -> List[str]:
    """Value for the app client's ``SupportedIdentityProviders``.

    ``COGNITO`` is always included, as it has been; password sign-in through
    the hosted UI keeps working whatever else is configured. Every SAML and
    OIDC provider is listed, since ``UpdateUserPoolClient`` replaces the list
    wholesale and a provider left out is switched off.
    """
    names = ["COGNITO"]
    for provider in identity_providers:
        name = _name(provider)
        if _method(provider) in FEDERATED_METHODS and name and name not in names:
            names.append(name)
    return names


def _app_urls(domain: str) -> List[str]:
    # The SPA's sign-in route is /sign-in; Amplify sends the redirect URL that
    # matches the page the user is on, so the bare origin, "/" and /sign-in
    # are all needed.
    return [f"https://{domain}", f"https://{domain}/", f"https://{domain}/sign-in"]


def hosted_ui_urls(
    cognito_domain: str,
    cloudfront_domain: str,
    custom_domain: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Callback and logout URLs for the app client.

    Both the CloudFront domain and the custom domain (when one is configured)
    are listed: users and identity providers can reach the app through either,
    and a redirect to a URL that isn't listed fails sign-in.
    """
    domains = [cloudfront_domain]
    if custom_domain and custom_domain.strip():
        domains.append(custom_domain.strip())

    hosted = f"https://{cognito_domain}"
    callbacks = [f"{hosted}/oauth2/idpresponse", f"{hosted}/saml2/idpresponse"]
    logouts = [hosted, f"{hosted}/", f"{hosted}/sign-in"]
    for domain in domains:
        callbacks += _app_urls(domain)
        logouts += _app_urls(domain)
    callbacks += LOCAL_CALLBACK_URLS
    logouts += LOCAL_CALLBACK_URLS
    return callbacks, logouts
