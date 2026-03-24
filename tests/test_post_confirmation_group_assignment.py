"""
Property-based tests for PostConfirmation Lambda group assignment.
Feature: federated-user-default-group, Property 5: Provider Name Extraction from userName
Validates: Requirements 2.2, 4.1
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# --- Strategies ---

# Provider names: non-empty alphanumeric strings without underscores
provider_names = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ),
    min_size=1,
    max_size=30,
)

# Provider user IDs: non-empty strings (can contain underscores)
provider_user_ids = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-"),
    min_size=1,
    max_size=50,
)

# Usernames without underscores (for unresolvable provider test)
usernames_without_underscore = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ),
    min_size=1,
    max_size=50,
)

# Valid default groups
VALID_GROUPS = ["editors", "read-only", "superAdministrators"]


def make_event(username, trigger_source="PostConfirmation_ConfirmSignUp"):
    """Build a minimal Cognito PostConfirmation event."""
    return {
        "triggerSource": trigger_source,
        "userName": username,
        "request": {"userAttributes": {"sub": "test-sub-id"}},
        "response": {},
    }


def _make_lambda_context():
    """Create a mock Lambda context with required attributes for Powertools."""
    ctx = MagicMock()
    ctx.function_name = "post_confirmation_group_assignment"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:post_confirmation"
    )
    ctx.aws_request_id = "test-request-id"
    return ctx


def _import_handler():
    """
    Import the post_confirmation_group_assignment handler module with proper
    path setup. Caller must mock boto3 and env vars BEFORE calling this.
    """
    lambda_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "lambdas",
        "auth",
        "post_confirmation_group_assignment",
    )

    if lambda_path not in sys.path:
        sys.path.insert(0, lambda_path)

    # Clear cached module so it re-imports with current mocks/env
    for mod_name in list(sys.modules.keys()):
        if mod_name == "index" or "post_confirmation_group_assignment" in mod_name:
            del sys.modules[mod_name]

    import index as handler_module

    return handler_module


# --- Property 5 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 5: Provider Name Extraction from userName
class TestProviderNameExtraction:
    """
    Property 5: Provider Name Extraction from userName
    **Validates: Requirements 2.2, 4.1**

    For any Cognito PostConfirmation event with a userName in the format
    {provider_name}_{provider_user_id}, the Lambda should extract {provider_name}
    as the identity provider name. For any userName without an underscore, the
    Lambda should treat the provider as unresolvable.
    """

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        group=st.sampled_from(VALID_GROUPS),
    )
    @settings(max_examples=100)
    def test_extracts_provider_name_from_underscore_username(
        self, provider_name, provider_user_id, group
    ):
        """
        Given a userName of the form {provider_name}_{provider_user_id} and a
        matching IDP_GROUP_MAPPING entry, the handler calls AdminAddUserToGroup
        with the correct provider's group — proving provider_name was extracted.

        # Feature: federated-user-default-group, Property 5: Provider Name Extraction from userName
        # **Validates: Requirements 2.2, 4.1**
        """
        username = f"{provider_name}_{provider_user_id}"
        idp_mapping = {provider_name: group}

        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # The handler extracted provider_name and called AdminAddUserToGroup
        mock_cognito.admin_add_user_to_group.assert_called_once_with(
            UserPoolId="us-east-1_testpool",
            Username=username,
            GroupName=group,
        )
        # Event is always returned
        assert result is event

    @given(username=usernames_without_underscore)
    @settings(max_examples=100)
    def test_no_underscore_username_treated_as_unresolvable(self, username):
        """
        Given a userName without an underscore, the handler does not attempt
        group assignment because the provider is unresolvable.

        # Feature: federated-user-default-group, Property 5: Provider Name Extraction from userName
        # **Validates: Requirements 2.2, 4.1**
        """
        assume("_" not in username)

        idp_mapping = {"SomeProvider": "editors"}
        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # No group assignment should be attempted
        mock_cognito.admin_add_user_to_group.assert_not_called()
        # Event is always returned
        assert result is event


# --- Property 6 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 6: Correct Group Assignment for Matched Providers
class TestCorrectGroupAssignmentForMatchedProviders:
    """
    Property 6: Correct Group Assignment for Matched Providers
    **Validates: Requirements 2.3, 4.2**

    For any Cognito PostConfirmation event where the extracted provider name
    matches a key in the IDP_GROUP_MAPPING, the Lambda should call
    AdminAddUserToGroup with the corresponding group name from the mapping
    and the full userName from the event.
    """

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        group=st.sampled_from(VALID_GROUPS),
    )
    @settings(max_examples=100)
    def test_matched_provider_triggers_correct_group_assignment(
        self, provider_name, provider_user_id, group
    ):
        """
        Given a userName whose provider prefix exists in IDP_GROUP_MAPPING,
        the handler calls AdminAddUserToGroup with the mapped GroupName and
        the full userName.

        # Feature: federated-user-default-group, Property 6: Correct Group Assignment for Matched Providers
        # **Validates: Requirements 2.3, 4.2**
        """
        username = f"{provider_name}_{provider_user_id}"
        idp_mapping = {provider_name: group}

        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup must be called exactly once with correct args
        mock_cognito.admin_add_user_to_group.assert_called_once_with(
            UserPoolId="us-east-1_testpool",
            Username=username,
            GroupName=group,
        )
        # Event is always returned
        assert result is event

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        extra_providers=st.dictionaries(
            keys=provider_names,
            values=st.sampled_from(VALID_GROUPS),
            min_size=0,
            max_size=5,
        ),
        group=st.sampled_from(VALID_GROUPS),
    )
    @settings(max_examples=100)
    def test_matched_provider_uses_correct_group_among_multiple_mappings(
        self, provider_name, provider_user_id, extra_providers, group
    ):
        """
        Given an IDP_GROUP_MAPPING with multiple providers, the handler selects
        the correct group for the matched provider and ignores others.

        # Feature: federated-user-default-group, Property 6: Correct Group Assignment for Matched Providers
        # **Validates: Requirements 2.3, 4.2**
        """
        username = f"{provider_name}_{provider_user_id}"
        # Ensure the target provider is in the mapping with the expected group
        idp_mapping = dict(extra_providers)
        idp_mapping[provider_name] = group

        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup called with the correct group for this provider
        mock_cognito.admin_add_user_to_group.assert_called_once_with(
            UserPoolId="us-east-1_testpool",
            Username=username,
            GroupName=group,
        )
        assert result is event


# --- Property 7 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 7: No-Match Provider Passthrough
class TestNoMatchProviderPassthrough:
    """
    Property 7: No-Match Provider Passthrough
    **Validates: Requirements 2.4, 4.3**

    For any Cognito PostConfirmation event where the extracted provider name
    does not match any key in the IDP_GROUP_MAPPING, the Lambda should not
    call AdminAddUserToGroup and should return the event unchanged.
    """

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        mapping_providers=st.lists(
            provider_names,
            min_size=1,
            max_size=5,
        ),
        mapping_groups=st.lists(
            st.sampled_from(VALID_GROUPS),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_unmatched_provider_does_not_trigger_group_assignment(
        self, provider_name, provider_user_id, mapping_providers, mapping_groups
    ):
        """
        Given a userName whose provider prefix does NOT exist in IDP_GROUP_MAPPING,
        the handler must not call AdminAddUserToGroup and must return the event
        unchanged.

        # Feature: federated-user-default-group, Property 7: No-Match Provider Passthrough
        # **Validates: Requirements 2.4, 4.3**
        """
        # Build a mapping that does NOT contain provider_name
        idp_mapping = {}
        for mp, mg in zip(mapping_providers, mapping_groups):
            idp_mapping[mp] = mg
        # Ensure the generated provider_name is NOT in the mapping
        assume(provider_name not in idp_mapping)

        username = f"{provider_name}_{provider_user_id}"
        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup must NOT be called
        mock_cognito.admin_add_user_to_group.assert_not_called()
        # Event must be returned unchanged (identity check)
        assert result is event

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
    )
    @settings(max_examples=100)
    def test_empty_mapping_never_triggers_group_assignment(
        self, provider_name, provider_user_id
    ):
        """
        Given an empty IDP_GROUP_MAPPING, no provider can match, so
        AdminAddUserToGroup must never be called and the event is returned
        unchanged.

        # Feature: federated-user-default-group, Property 7: No-Match Provider Passthrough
        # **Validates: Requirements 2.4, 4.3**
        """
        username = f"{provider_name}_{provider_user_id}"
        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps({}),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup must NOT be called
        mock_cognito.admin_add_user_to_group.assert_not_called()
        # Event must be returned unchanged (identity check)
        assert result is event


# --- Property 8 Tests ---


@pytest.mark.property
# Feature: federated-user-default-group, Property 8: Error Resilience on API Failure
class TestErrorResilienceOnAPIFailure:
    """
    Property 8: Error Resilience on API Failure
    **Validates: Requirements 2.5**

    For any Cognito PostConfirmation event where AdminAddUserToGroup raises
    an exception, the Lambda should catch the exception, log the error, and
    return the original event without re-raising.
    """

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        group=st.sampled_from(VALID_GROUPS),
        error_message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_api_exception_is_caught_and_event_returned(
        self, provider_name, provider_user_id, group, error_message
    ):
        """
        Given a userName whose provider prefix exists in IDP_GROUP_MAPPING and
        AdminAddUserToGroup raises an arbitrary exception, the handler must
        catch the exception without re-raising and return the original event.

        # Feature: federated-user-default-group, Property 8: Error Resilience on API Failure
        # **Validates: Requirements 2.5**
        """
        username = f"{provider_name}_{provider_user_id}"
        idp_mapping = {provider_name: group}

        mock_cognito = MagicMock()
        mock_cognito.admin_add_user_to_group.side_effect = Exception(error_message)

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                # Must NOT raise — the handler catches all exceptions
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup was attempted (and raised)
        mock_cognito.admin_add_user_to_group.assert_called_once_with(
            UserPoolId="us-east-1_testpool",
            Username=username,
            GroupName=group,
        )
        # Event is returned unchanged despite the failure
        assert result is event

    @given(
        provider_name=provider_names,
        provider_user_id=provider_user_ids,
        group=st.sampled_from(VALID_GROUPS),
    )
    @settings(max_examples=100)
    def test_runtime_error_is_caught_and_event_returned(
        self, provider_name, provider_user_id, group
    ):
        """
        Given a userName whose provider prefix exists in IDP_GROUP_MAPPING and
        AdminAddUserToGroup raises a RuntimeError, the handler must catch it
        without re-raising and return the original event.

        # Feature: federated-user-default-group, Property 8: Error Resilience on API Failure
        # **Validates: Requirements 2.5**
        """
        username = f"{provider_name}_{provider_user_id}"
        idp_mapping = {provider_name: group}

        mock_cognito = MagicMock()
        mock_cognito.admin_add_user_to_group.side_effect = RuntimeError(
            "Simulated runtime failure"
        )

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username)
                # Must NOT raise
                result = handler_module.handler(event, _make_lambda_context())

        # AdminAddUserToGroup was attempted (and raised)
        mock_cognito.admin_add_user_to_group.assert_called_once()
        # Event is returned unchanged despite the failure
        assert result is event


# --- Property 9 Tests ---

# Strategies for broad input generation
trigger_sources = st.sampled_from(
    [
        "PostConfirmation_ConfirmSignUp",
        "PostConfirmation_ConfirmForgotPassword",
    ]
) | st.text(min_size=0, max_size=60)

# userNames: with underscore (federated), without underscore, and empty
federated_usernames = st.builds(
    lambda p, u: f"{p}_{u}",
    provider_names,
    provider_user_ids,
)
plain_usernames = usernames_without_underscore
empty_username = st.just("")
all_usernames = st.one_of(federated_usernames, plain_usernames, empty_username)


@pytest.mark.property
# Feature: federated-user-default-group, Property 9: Event Passthrough Invariant
class TestEventPassthroughInvariant:
    """
    Property 9: Event Passthrough Invariant
    **Validates: Requirements 2.6, 2.7**

    For any input event (regardless of trigger source, userName format, or
    provider match status), the Lambda should always return the original event
    object. This invariant holds for confirmation triggers, non-confirmation
    triggers, matched providers, unmatched providers, and API failures alike.
    """

    @given(
        trigger_source=trigger_sources,
        username=all_usernames,
        idp_mapping=st.dictionaries(
            keys=provider_names,
            values=st.sampled_from(VALID_GROUPS),
            min_size=0,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_handler_always_returns_original_event(
        self, trigger_source, username, idp_mapping
    ):
        """
        Given any combination of triggerSource, userName format, and
        IDP_GROUP_MAPPING contents, the handler must always return the
        exact same event object it received (identity check with `is`).

        # Feature: federated-user-default-group, Property 9: Event Passthrough Invariant
        # **Validates: Requirements 2.6, 2.7**
        """
        mock_cognito = MagicMock()

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username, trigger_source=trigger_source)
                result = handler_module.handler(event, _make_lambda_context())

        assert result is event

    @given(
        trigger_source=trigger_sources,
        username=all_usernames,
        idp_mapping=st.dictionaries(
            keys=provider_names,
            values=st.sampled_from(VALID_GROUPS),
            min_size=0,
            max_size=5,
        ),
        error_message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_handler_returns_original_event_even_on_api_failure(
        self, trigger_source, username, idp_mapping, error_message
    ):
        """
        Given any combination of triggerSource, userName, and IDP_GROUP_MAPPING,
        even when AdminAddUserToGroup raises an exception, the handler must
        return the exact same event object (identity check with `is`).

        # Feature: federated-user-default-group, Property 9: Event Passthrough Invariant
        # **Validates: Requirements 2.6, 2.7**
        """
        mock_cognito = MagicMock()
        mock_cognito.admin_add_user_to_group.side_effect = Exception(error_message)

        with patch.dict(
            os.environ,
            {
                "USER_POOL_ID": "us-east-1_testpool",
                "IDP_GROUP_MAPPING": json.dumps(idp_mapping),
                "POWERTOOLS_SERVICE_NAME": "test",
            },
        ):
            with patch("boto3.client", return_value=mock_cognito):
                handler_module = _import_handler()

                event = make_event(username, trigger_source=trigger_source)
                result = handler_module.handler(event, _make_lambda_context())

        assert result is event
