"""Inbound federation Lambda trigger for Media Lake.

Amazon Cognito invokes this trigger after it has received and verified the
response from an external identity provider, but *before* it creates or updates
the federated user's profile. It runs on every federated sign-in, not only the
first, and receives the raw provider attributes.

Its single job here is to make the identity provider's group assertion usable:

* Normalize the many shapes group names arrive in (plain, path-like, LDAP
  distinguished names) down to a bare name.
* Translate those names to Media Lake group ids through an explicit mapping,
  which doubles as the allowlist. An identity provider must never be able to
  name a Media Lake group directly, since that would let whoever controls the
  provider grant themselves any level of access.
* Keep the result inside the 2048-character limit Cognito enforces on a user
  pool attribute. An oversized assertion otherwise fails the whole sign-in,
  which is a common problem with providers that send every group a user belongs
  to.

Two things it deliberately does *not* do:

* It does not assign a default group. This trigger fires on every sign-in, so
  doing that here would re-apply the default after an administrator had moved
  the user somewhere else. The default is applied once per user by the
  pre-token-generation trigger instead.
* It does not confirm or verify users. Those are pre sign-up trigger
  responsibilities and have no equivalent in this trigger's response.

Response contract, which is unusually sharp: the only field Cognito reads is
``userAttributesToMap``, and any attribute missing from it is **dropped** from
the user profile. Returning an empty object means "change nothing". So on any
error, or when there is nothing to do, this function returns without setting
``userAttributesToMap`` at all, which Cognito treats as a no-op.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger

logger = Logger()

# Cognito rejects a user pool attribute longer than this.
MAX_ATTRIBUTE_LENGTH = 2048


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_json_dict(name: str) -> Dict[str, str]:
    raw = os.environ.get(name)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning(f"{name} is not valid JSON; ignoring")
        return {}
    if not isinstance(parsed, dict):
        logger.warning(f"{name} is not a JSON object; ignoring")
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


ALLOW_IDP_GROUP_ASSERTIONS = _env_flag("JIT_ALLOW_IDP_GROUP_ASSERTIONS", False)
# IdP-asserted group name -> Media Lake group id.
IDP_GROUP_MAPPING = _env_json_dict("JIT_IDP_GROUP_MAPPING")
# Provider name -> the raw attribute/claim that carries group membership. The
# keys written back must be raw provider attribute names, because Cognito
# applies the provider's attribute mapping to whatever this function returns.
PROVIDER_GROUPS_CLAIM = _env_json_dict("JIT_PROVIDER_GROUPS_CLAIM")
DEFAULT_GROUPS_CLAIM = os.environ.get("JIT_DEFAULT_GROUPS_CLAIM") or "groups"

_DN_PREFIX = re.compile(r"^cn=", re.IGNORECASE)
_DN_SEGMENT = re.compile(r",\s*(ou|dc)=", re.IGNORECASE)
_DN_CN_VALUE = re.compile(r"^cn=([^,]+)", re.IGNORECASE)


def extract_group_name(raw: str) -> str:
    """Reduce a provider's group name to a bare name.

    Handles the formats providers actually send:

    * ``Editors``
    * ``/Editors`` (leading slash marks a top-level group)
    * ``example.com/groups/Editors`` (path or URL style)
    * ``cn=Editors,OU=groups,DC=example,DC=com`` (LDAP distinguished name)
    """
    name = (raw or "").strip()
    if not name:
        return ""

    if name.startswith("/"):
        name = name[1:]

    if _DN_PREFIX.search(name) or _DN_SEGMENT.search(name):
        match = _DN_CN_VALUE.match(name)
        return match.group(1).strip() if match else name

    if "/" in name:
        segments = [segment for segment in name.split("/") if segment]
        return segments[-1] if segments else name

    return name


def parse_asserted_groups(value: Any) -> List[str]:
    """Turn whatever the provider sent into a list of raw group names."""
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]

    if not isinstance(value, str):
        return [str(value)] if str(value).strip() else []

    text = value.strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except (TypeError, ValueError):
            pass

    # Comma-separated, optionally quoted, is what Cognito attribute mapping and
    # most SAML assertions produce.
    return [
        part.strip().strip("'\"")
        for part in text.split(",")
        if part.strip().strip("'\"")
    ]


def map_to_medialake_groups(asserted: List[str]) -> List[str]:
    """Translate asserted names to Media Lake group ids via the allowlist."""
    resolved: List[str] = []
    for raw in asserted:
        name = extract_group_name(raw)
        if not name:
            continue
        group_id = IDP_GROUP_MAPPING.get(name)
        if not group_id:
            logger.debug(f"Ignoring unmapped IdP group: {name}")
            continue
        if group_id not in resolved:
            resolved.append(group_id)
    return resolved


def truncate_to_limit(values: List[str]) -> str:
    """Join group ids, dropping trailing entries that would exceed the limit."""
    result = ""
    for value in values:
        candidate = f"{result},{value}" if result else value
        if len(candidate) > MAX_ATTRIBUTE_LENGTH:
            logger.warning(
                "IdP group assertion exceeds the Cognito attribute limit; "
                "dropping the remaining groups"
            )
            break
        result = candidate
    return result


def get_raw_attributes(request: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the provider's attribute bag out of the request.

    SAML providers deliver ``samlResponse``. OIDC and social providers deliver
    ``userInfo`` and ``idToken``; ``userInfo`` is preferred because it is the
    fuller profile, with ``idToken`` filling any gaps.
    """
    attributes = request.get("attributes") or {}
    provider_type = str(request.get("providerType") or "").lower()

    if provider_type == "saml":
        saml = attributes.get("samlResponse")
        return dict(saml) if isinstance(saml, dict) else {}

    merged: Dict[str, Any] = {}
    id_token = attributes.get("idToken")
    if isinstance(id_token, dict):
        merged.update(id_token)
    user_info = attributes.get("userInfo")
    if isinstance(user_info, dict):
        merged.update(user_info)
    return merged


def groups_claim_for(provider_name: Optional[str]) -> str:
    """Which raw attribute carries groups for this provider."""
    if provider_name and provider_name in PROVIDER_GROUPS_CLAIM:
        return PROVIDER_GROUPS_CLAIM[provider_name]
    return DEFAULT_GROUPS_CLAIM


@logger.inject_lambda_context
def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Normalize the identity provider's group assertion.

    Always returns the event. On any problem it returns it without setting
    ``userAttributesToMap``, which Cognito treats as "keep the original
    attributes" -- failing a legitimate sign-in would be far worse than skipping
    the normalization.
    """
    try:
        request = event.get("request") or {}
        provider_name = request.get("providerName")
        provider_type = request.get("providerType")

        logger.info(
            "Inbound federation trigger invoked",
            extra={"provider_name": provider_name, "provider_type": provider_type},
        )

        if not ALLOW_IDP_GROUP_ASSERTIONS:
            # Nothing to transform; leave every attribute exactly as sent.
            logger.debug("IdP group assertions are disabled; passing through")
            return event

        if not IDP_GROUP_MAPPING:
            logger.info(
                "No IdP group mapping is configured, so no assertion can be "
                "honoured; passing attributes through unchanged"
            )
            return event

        raw_attributes = get_raw_attributes(request)
        if not raw_attributes:
            logger.info("No provider attributes present; passing through")
            return event

        claim_key = groups_claim_for(provider_name)
        if claim_key not in raw_attributes:
            logger.info(
                f"Provider did not send the '{claim_key}' claim; passing through"
            )
            return event

        asserted = parse_asserted_groups(raw_attributes.get(claim_key))
        mapped = map_to_medialake_groups(asserted)

        # Echo every attribute. Anything omitted here is dropped from the user
        # profile, which would also starve a pre sign-up trigger of attributes.
        attributes_to_map = dict(raw_attributes)

        if mapped:
            attributes_to_map[claim_key] = truncate_to_limit(mapped)
        else:
            # Nothing survived the allowlist. Remove the claim so a stale value
            # is not carried over from a previous sign-in, and let the
            # pre-token-generation trigger fall back to the default group.
            attributes_to_map.pop(claim_key, None)

        event.setdefault("response", {})
        event["response"]["userAttributesToMap"] = attributes_to_map

        logger.info(
            "Normalized IdP group assertion",
            extra={
                "provider_name": provider_name,
                "asserted_count": len(asserted),
                "mapped_groups": mapped,
                "claim_key": claim_key,
            },
        )
        return event

    except Exception as e:  # noqa: BLE001
        # Returning the event without userAttributesToMap is an explicit no-op,
        # so sign-in proceeds with the provider's original attributes.
        logger.exception(
            f"Inbound federation trigger failed, passing through: {str(e)}"
        )
        if isinstance(event, dict) and isinstance(event.get("response"), dict):
            event["response"].pop("userAttributesToMap", None)
        return event
