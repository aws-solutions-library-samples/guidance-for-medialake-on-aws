# from aws_cdk import (
#     Stack,
#     aws_cognito as cognito,
# )
# from aws_cdk.aws_cognito_identitypool_alpha import IdentityPool
# from constructs import Construct
# from dataclasses import dataclass
# from medialake_constructs.cognito import CognitoConstruct, CognitoProps


# @dataclass
# class AuthStackProps:
#     """Configuration for Auth Stack."""

#     stub: bool = False


# class AuthStack(Stack):
#     def __init__(self, scope: Construct, id: str, props: AuthStackProps, **kwargs):
#         super().__init__(scope, id, **kwargs)

#         self._cognito_construct = CognitoConstruct(
#             self,
#             "Cognito",
#             props=CognitoProps(),
#         )

#     @property
#     def user_pool(self) -> cognito.IUserPool:
#         """Returns the Cognito user pool."""
#         return self._cognito_construct.user_pool

#     @property
#     def user_pool_id(self) -> str:
#         """Returns the Cognito user pool id."""
#         return self._cognito_construct.user_pool_id

#     @property
#     def identity_pool(self) -> str:
#         """Returns the Cognito identity pool."""
#         return self._cognito_construct.identity_pool

#     @property
#     def user_pool_client(self) -> str:
#         """Returns the Cognito user pool client."""
#         return self._cognito_construct.user_pool_client

#     @property
#     def user_pool_ref(self) -> cognito.UserPoolClient:
#         """Returns the Cognito user pool client reference."""
#         return self._cognito_construct.user_pool_ref
