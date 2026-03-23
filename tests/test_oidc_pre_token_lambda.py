"""
Property-based tests for Pre-Token Generation Lambda auth-method agnosticism.
Feature: oidc-authentication, Property 9: Pre-Token Lambda Auth-Method Agnosticism
Validates: Requirements 8.1, 8.2, 8.3
"""

import copy
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# --- Strategies ---

# UUID-like sub values
uuid_sub_strategy = st.uuids().map(str)

# Auth trigger sources representing cognito, saml, and oidc flows
trigger_source_strategy = st.sampled_from([
    "TokenGeneration_HostedAuth",       # Cognito hosted UI
    "TokenGeneration_Authentication",   # Direct Cognito auth
    "TokenGeneration_NewPasswordChallenge",  # Cognito password challenge
    "TokenGeneration_AuthenticateDevice",    # Cognito device auth
    "TokenGeneration_RefreshTokens",         # Token refresh (any method)
])

# Event versions: V1 (legacy) and V2/V3
event_version_strategy = st.sampled_from(["1", "2", "3"])

# Group names
group_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=20,
)

# Group lists (0 to 5 groups)
group_list_strategy = st.lists(group_name_strategy, min_size=0, max_size=5, unique=True)

# Permission strings like "resource:action"
permission_strategy = st.builds(
    lambda r, a: f"{r}:{a}",
    r=st.sampled_from(["users", "pipelines", "assets", "collections", "admin"]),
    a=st.sampled_from(["view", "edit", "delete", "create", "manage"]),
)

# Permission lists (0 to 8 permissions)
permission_list_strategy = st.lists(permission_strategy, min_size=0, max_size=8, unique=True)


# --- Helpers ---

def build_cognito_event(sub, trigger_source, version, cognito_groups=None):
    """Build a Cognito pre-token generation event for any auth method."""
    event = {
        "version": version,
        "triggerSource": trigger_source,
        "region": "us-east-1",
        "userPoolId": "us-east-1_TestPool",
        "userName": f"user-{sub[:8]}",
        "callerContext": {
            "awsSdkVersion": "3.0.0",
            "clientId": "test-client-id",
        },
        "request": {
            "userAttributes": {
                "sub": sub,
                "email": f"user-{sub[:8]}@example.com",
            },
            "groupConfiguration": {
                "groupsToOverride": cognito_groups or [],
                "iamRolesToOverride": [],
                "preferredRole": None,
            },
        },
        "response": {},
    }

    if version in ("2", "3"):
        event["response"]["claimsAndScopeOverrideDetails"] = None
    else:
        event["response"]["claimsOverrideDetails"] = {}

    return event


# --- Mock Lambda context ---

def _make_lambda_context():
    """Create a mock Lambda context object with required attributes."""
    ctx = MagicMock()
    ctx.function_name = "pre_token_generation"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:pre_token_generation"
    ctx.aws_request_id = "test-request-id"
    return ctx


# --- Module import helper ---

def _import_handler():
    """
    Import the pre_token_generation handler module with proper path setup.
    Returns the module. Caller is responsible for mocking boto3/lambda_middleware
    BEFORE calling this if the module hasn't been imported yet.
    """
    lambda_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "lambdas", "auth", "pre_token_generation"
    )
    common_lib_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "lambdas", "common_libraries"
    )

    if lambda_path not in sys.path:
        sys.path.insert(0, lambda_path)
    if common_lib_path not in sys.path:
        sys.path.insert(0, common_lib_path)

    # Clear cached module so it re-imports with current mocks
    for mod_name in list(sys.modules.keys()):
        if mod_name == "index" or "pre_token_generation" in mod_name:
            del sys.modules[mod_name]

    import index as pre_token_module
    return pre_token_module


# --- Property Tests ---


@pytest.mark.property
# Feature: oidc-authentication, Property 9: Pre-Token Lambda Auth-Method Agnosticism
class TestPreTokenLambdaAuthMethodAgnosticism:
    """
    Property 9: Pre-Token Lambda Auth-Method Agnosticism
    **Validates: Requirements 8.1, 8.2, 8.3**

    For any Cognito pre-token generation event containing a `sub` attribute in
    `userAttributes`, the Lambda should extract the user identifier from `sub`,
    query DynamoDB for group memberships and permissions, and add
    `custom:permissions` and `cognito:groups` claims to both the ID token and
    access token, regardless of whether the user authenticated via Cognito,
    SAML, or OIDC.
    """

    @given(
        sub=uuid_sub_strategy,
        trigger_source=trigger_source_strategy,
        version=event_version_strategy,
        mock_groups=group_list_strategy,
        mock_permissions=permission_list_strategy,
    )
    @settings(max_examples=100, deadline=2000)
    def test_claims_added_regardless_of_auth_method(
        self, sub, trigger_source, version, mock_groups, mock_permissions
    ):
        """
        The Lambda adds custom:permissions and cognito:groups claims to the
        token response for any valid sub value and any trigger source,
        proving auth-method agnosticism.

        # Feature: oidc-authentication, Property 9: Pre-Token Lambda Auth-Method Agnosticism
        # **Validates: Requirements 8.1, 8.2, 8.3**
        """
        event = build_cognito_event(sub, trigger_source, version)

        # Mock module-level dependencies before importing
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict(os.environ, {"AUTH_TABLE_NAME": "test-auth-table"}):
            with patch("boto3.resource", return_value=mock_dynamodb):
                pre_token_module = _import_handler()

                # Patch the functions that do DynamoDB calls
                with patch.object(
                    pre_token_module, "get_user_groups", return_value=mock_groups
                ), patch.object(
                    pre_token_module, "get_user_permissions", return_value=mock_permissions
                ):
                    result = pre_token_module.handler(copy.deepcopy(event), _make_lambda_context())

        # --- Assertions ---

        # Requirement 8.3: custom:permissions added to token claims
        if version in ("2", "3"):
            # V2/V3: check both ID token and access token
            override = result["response"]["claimsAndScopeOverrideDetails"]

            id_claims = override["idTokenGeneration"]["claimsToAddOrOverride"]
            access_claims = override["accessTokenGeneration"]["claimsToAddOrOverride"]

            # custom:permissions in both tokens
            assert "custom:permissions" in id_claims
            assert "custom:permissions" in access_claims
            assert json.loads(id_claims["custom:permissions"]) == mock_permissions
            assert json.loads(access_claims["custom:permissions"]) == mock_permissions

            # cognito:groups in ID token when groups exist
            if mock_groups:
                assert "cognito:groups" in id_claims
                assert id_claims["cognito:groups"] == mock_groups
        else:
            # V1: check claimsOverrideDetails
            claims = result["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]

            assert "custom:permissions" in claims
            assert json.loads(claims["custom:permissions"]) == mock_permissions

            if mock_groups:
                assert "cognito:groups" in claims
                assert claims["cognito:groups"] == mock_groups

    @given(
        sub=uuid_sub_strategy,
        mock_groups=group_list_strategy,
        mock_permissions=permission_list_strategy,
    )
    @settings(max_examples=100, deadline=2000)
    def test_user_id_extracted_from_sub(
        self, sub, mock_groups, mock_permissions
    ):
        """
        The Lambda extracts user_id from event.request.userAttributes.sub
        and passes it to get_user_groups, regardless of auth method.

        # Feature: oidc-authentication, Property 9: Pre-Token Lambda Auth-Method Agnosticism
        # **Validates: Requirements 8.1, 8.2**
        """
        event = build_cognito_event(sub, "TokenGeneration_HostedAuth", "2")

        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict(os.environ, {"AUTH_TABLE_NAME": "test-auth-table"}):
            with patch("boto3.resource", return_value=mock_dynamodb):
                pre_token_module = _import_handler()

                mock_get_groups = MagicMock(return_value=mock_groups)
                mock_get_perms = MagicMock(return_value=mock_permissions)

                with patch.object(
                    pre_token_module, "get_user_groups", mock_get_groups
                ), patch.object(
                    pre_token_module, "get_user_permissions", mock_get_perms
                ):
                    pre_token_module.handler(copy.deepcopy(event), _make_lambda_context())

        # Requirement 8.1: user_id extracted from sub
        mock_get_groups.assert_called_once()
        call_args = mock_get_groups.call_args
        assert call_args[0][0] == sub, (
            f"Expected get_user_groups called with sub={sub}, "
            f"got {call_args[0][0]}"
        )

        # Requirement 8.2: same DynamoDB query logic used
        mock_get_perms.assert_called_once()
        perm_call_args = mock_get_perms.call_args
        assert perm_call_args[0][0] == sub
        assert perm_call_args[0][1] == mock_groups
