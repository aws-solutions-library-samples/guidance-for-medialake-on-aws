"""Keep the MediaLake UI's hosted-UI settings on the Cognito app client.

The Cognito stack creates the app client before the CloudFront distribution
exists, so the client's template only lists the Cognito hosted-domain callback
URLs. This custom resource, in the UI stack, adds the UI's own URLs
(CloudFront, any custom domain, localhost) so hosted-UI sign-in -- SAML, OIDC
and the Cognito hosted UI -- can redirect back to the app.

Two properties make it safe:

* **It runs on every deploy.** Any CloudFormation update of the app client
  resets the callback URLs to the template's hosted-domain pair. The stack
  passes a per-deploy value, so the URLs are re-applied after every Cognito
  stack change instead of only when this resource's own inputs change.
* **It only ever adds.** ``UpdateUserPoolClient`` resets every field that is
  omitted, so the current client is read first and every setting is sent
  back. The UI's callback/logout URLs, OAuth flows and scopes, identity
  providers and the Cognito stack's auth flows are merged *into* what the
  client already has: nothing already on the client is removed. A callback
  someone added by hand (for example to recover from an outage) survives
  every deploy; the cost is that a URL that is no longer used, such as a
  replaced custom domain, has to be removed by hand.

  Identity providers are the one exception: a provider already on the client
  is kept only while it still exists in the user pool, so removing a provider
  from config.json doesn't make the update fail.
"""

import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Fields UpdateUserPoolClient accepts; any not sent are reset by Cognito.
UPDATABLE_FIELDS = (
    "ClientName",
    "RefreshTokenValidity",
    "AccessTokenValidity",
    "IdTokenValidity",
    "TokenValidityUnits",
    "ReadAttributes",
    "WriteAttributes",
    "ExplicitAuthFlows",
    "SupportedIdentityProviders",
    "CallbackURLs",
    "LogoutURLs",
    "DefaultRedirectURI",
    "AllowedOAuthFlows",
    "AllowedOAuthScopes",
    "AllowedOAuthFlowsUserPoolClient",
    "AnalyticsConfiguration",
    "PreventUserExistenceErrors",
    "EnableTokenRevocation",
    "EnablePropagateAdditionalUserContextData",
    "AuthSessionValidity",
    "RefreshTokenRotation",
)

# Fields this resource adds to; everything else comes from the current client.
MERGED_FIELDS = (
    "CallbackURLs",
    "LogoutURLs",
    "AllowedOAuthFlows",
    "AllowedOAuthScopes",
    "SupportedIdentityProviders",
    "ExplicitAuthFlows",
)

# Cognito's per-client limit for CallbackURLs and LogoutURLs.
MAX_URLS = 100

_cognito = None


def _client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


def _dedupe(values):
    seen = []
    for value in values or []:
        if value and value not in seen:
            seen.append(value)
    return seen


def _as_bool(value) -> bool:
    return str(value).lower() in ("true", "1", "yes")


def _merge(desired, current):
    """``desired`` first (so it survives the URL limit), then the rest of ``current``."""
    return _dedupe(list(desired or []) + list(current or []))


def _cap(name: str, urls: list, desired: list) -> list:
    """Keep every URL of ours, then as many of the client's others as fit."""
    if len(urls) <= MAX_URLS:
        return urls
    others = [u for u in urls if u not in desired]
    room = max(MAX_URLS - len(desired), 0)
    logger.warning(
        "%s would exceed Cognito's limit of %d; not keeping: %s",
        name,
        MAX_URLS,
        others[room:],
    )
    return desired[:MAX_URLS] + others[:room]


def build_update(current: dict, desired: dict, existing_providers=None) -> dict:
    """Parameters for UpdateUserPoolClient: the current client with ours merged in.

    ``existing_providers`` is the set of identity provider names in the user
    pool; providers on the client that are no longer in it are dropped.
    """
    params = {k: current[k] for k in UPDATABLE_FIELDS if k in current}
    params["UserPoolId"] = current["UserPoolId"]
    params["ClientId"] = current["ClientId"]

    for name in ("CallbackURLs", "LogoutURLs"):
        wanted = _dedupe(desired.get(name))
        params[name] = _cap(name, _merge(wanted, current.get(name)), wanted)
    params["AllowedOAuthFlows"] = _merge(
        desired.get("AllowedOAuthFlows"), current.get("AllowedOAuthFlows")
    )
    params["AllowedOAuthScopes"] = _merge(
        desired.get("AllowedOAuthScopes"), current.get("AllowedOAuthScopes")
    )
    params["AllowedOAuthFlowsUserPoolClient"] = _as_bool(
        desired.get("AllowedOAuthFlowsUserPoolClient", True)
    ) or bool(current.get("AllowedOAuthFlowsUserPoolClient"))

    kept_providers = [
        p
        for p in current.get("SupportedIdentityProviders") or []
        if p == "COGNITO" or existing_providers is None or p in existing_providers
    ]
    params["SupportedIdentityProviders"] = _merge(
        desired.get("SupportedIdentityProviders"), kept_providers
    )

    if desired.get("ExplicitAuthFlows") or current.get("ExplicitAuthFlows"):
        params["ExplicitAuthFlows"] = _merge(
            desired.get("ExplicitAuthFlows"), current.get("ExplicitAuthFlows")
        )
    # A default redirect must be one of the callback URLs, or Cognito rejects
    # the update; drop a stale one rather than failing the deploy.
    if params.get("DefaultRedirectURI") not in params["CallbackURLs"]:
        params.pop("DefaultRedirectURI", None)
    return params


def _pool_provider_names(cognito, user_pool_id: str) -> set:
    names, token = set(), None
    while True:
        kwargs = {"UserPoolId": user_pool_id, "MaxResults": 60}
        if token:
            kwargs["NextToken"] = token
        page = cognito.list_identity_providers(**kwargs)
        names.update(p["ProviderName"] for p in page.get("Providers", []))
        token = page.get("NextToken")
        if not token:
            return names


def handler(event, context):
    logger.info(
        "Request %s for %s",
        event.get("RequestType"),
        event.get("LogicalResourceId"),
    )
    props = event["ResourceProperties"]
    physical_id = f"{props['ClientId']}-hosted-ui-urls"

    if event["RequestType"] == "Delete":
        # Leave the client as it is: removing the URLs would break sign-in for
        # a deployment that is being rolled back or re-created.
        return {"PhysicalResourceId": physical_id}

    cognito = _client()
    current = cognito.describe_user_pool_client(
        UserPoolId=props["UserPoolId"], ClientId=props["ClientId"]
    )["UserPoolClient"]
    params = build_update(
        current, props, _pool_provider_names(cognito, props["UserPoolId"])
    )
    cognito.update_user_pool_client(**params)

    after = cognito.describe_user_pool_client(
        UserPoolId=props["UserPoolId"], ClientId=props["ClientId"]
    )["UserPoolClient"]
    missing = [
        u for u in params["CallbackURLs"] if u not in after.get("CallbackURLs", [])
    ]
    if missing:
        raise RuntimeError(f"Callback URLs were not applied: {missing}")
    logger.info(
        "Applied %d callback URLs, %d logout URLs, providers %s",
        len(params["CallbackURLs"]),
        len(params["LogoutURLs"]),
        params["SupportedIdentityProviders"],
    )
    return {
        "PhysicalResourceId": physical_id,
        "Data": {"CallbackURLCount": str(len(params["CallbackURLs"]))},
    }
