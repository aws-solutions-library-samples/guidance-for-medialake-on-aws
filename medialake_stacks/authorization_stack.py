"""
Authorization Stack for Media Lake.

This stack defines the AWS resources for the new authorization system, including:
- DynamoDB table for authorization configuration
- Amazon Verified Permissions (AVP) Policy Store
- Lambda functions for authorization and policy synchronization
- IAM roles and permissions
"""

from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_verifiedpermissions as avp,
    RemovalPolicy,
    CustomResource,
)
import aws_cdk as cdk
import datetime

from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig
from medialake_constructs.auth.shared_authorizer_construct import (
    SharedAuthorizerConstruct,
    SharedAuthorizerConstructProps,
)

from config import config


@dataclass
class AuthorizationStackProps:
    """Configuration for Authorization Stack."""
    cognito_user_pool: cognito.UserPool
    user_pool_client: str


class AuthorizationStack(Stack):
    """
    Stack for Authorization resources.
    
    This stack creates the DynamoDB table, AVP Policy Store, Lambda functions,
    and IAM roles for the new authorization system.
    """

    def __init__(
        self, scope: Construct, id: str, props: AuthorizationStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create the DynamoDB table for authorization configuration
        
        self._auth_table_props = DynamoDBProps(
            name=f"{config.resource_prefix}-authorization-{config.environment}",
            partition_key_name="PK",
            partition_key_type=dynamodb.AttributeType.STRING,
            sort_key_name="SK",
            sort_key_type=dynamodb.AttributeType.STRING,
            point_in_time_recovery=True,
            billing_mode=dynamodb.Billing.on_demand(),
            # Enable DynamoDB Streams for policy synchronization
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            global_secondary_indexes=[
                # GSI1 (Query assignments by PermissionSet or Group)
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI1",
                    partition_key=dynamodb.Attribute(
                        name="GSI1PK",
                        type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI1SK",
                        type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL
                ),
            ]
        )
        self._auth_table = DynamoDB(self, "AuthorizationTable", self._auth_table_props)

        # 2. Create the AVP Policy Store
        self._policy_store = avp.CfnPolicyStore(
            self,
            "AVPPolicyStore",
            validation_settings=avp.CfnPolicyStore.ValidationSettingsProperty(
                mode="OFF"
            ),
            schema=avp.CfnPolicyStore.SchemaDefinitionProperty(
                cedar_json="""{
                    "MediaLake": {
                        "entityTypes": {
                            "User": {
                                "memberOfTypes": ["Group"],
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            },
                            "Group": {
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            },
                            "Resource": {
                                "shape": {
                                    "type": "Record",
                                    "attributes": {}
                                }
                            }
                        },
                        "actions": {
                            "Action": {
                                "appliesTo": {
                                    "principalTypes": ["User", "Group"],
                                    "resourceTypes": ["Resource"],
                                    "context": {
                                        "type": "Record",
                                        "attributes": {}
                                    }
                                }
                            }
                        }
                    }
                }"""
            ),
        )

        # Create a default "permit all" policy in the AVP Policy Store
        self._default_policy = avp.CfnPolicy(
            self,
            "DefaultPermitAllPolicy",
            policy_store_id=self._policy_store.attr_policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement="permit(principal, action, resource);",
                    description="Default policy that permits all actions"
                )
            )
        )

        # Create the shared custom authorizer
        self._shared_authorizer = SharedAuthorizerConstruct(
            self,
            "SharedAuthorizer",
            props=SharedAuthorizerConstructProps(
                auth_table_name=self._auth_table.table_name,
                avp_policy_store_id=self._policy_store.attr_policy_store_id,
                avp_policy_store_arn=f"arn:aws:verifiedpermissions:{self.region}:{self.account}:policy-store/{self._policy_store.attr_policy_store_id}",
                cognito_user_pool_id=props.cognito_user_pool.user_pool_id,
            ),
        )

        # Grant table read access to the shared authorizer
        self._auth_table.table.grant_read_data(self._shared_authorizer.authorizer_lambda)

        # Common environment variables for Lambda functions
        common_env_vars = {
            "AUTH_TABLE_NAME": self._auth_table.table_name,
            "AVP_POLICY_STORE_ID": self._policy_store.attr_policy_store_id,
            "DEBUG_MODE": "true",
            "COGNITO_USER_POOL_ID": props.cognito_user_pool.user_pool_id,
            
        }

        # 3. Use the Custom API Gateway Lambda Authorizer from props
        # self._custom_authorizer_lambda = props.custom_authorizer_lambda

        self._custom_authorizer_lambda = Lambda(
            self,
            "CustomAuthorizerLambda",
            config=LambdaConfig(
                name="custom_api_authorizer",
                entry="lambdas/auth/custom_authorizer",
                memory_size=256,
                timeout_minutes=1,
                environment_variables=common_env_vars,
            ),
        )
        
        self._auth_table.table.grant_read_data(self._custom_authorizer_lambda.function)
        self._custom_authorizer_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "verifiedpermissions:IsAuthorizedWithToken",
                    "verifiedpermissions:IsAuthorized",
                ],
                resources=[f"arn:aws:verifiedpermissions:{self.region}:{self.account}:policy-store/{self._policy_store.attr_policy_store_id}"],
            )
        )
    
        # 4. Create the DynamoDB Stream Lambda for policy synchronization
        self._policy_sync_lambda = Lambda(
            self,
            "PolicySyncLambda",
            config=LambdaConfig(
                name="policy_sync",
                entry="lambdas/auth/policy_sync",
                memory_size=256,
                timeout_minutes=5,
                environment_variables=common_env_vars,
            ),
        )
        
        # 5. Create the Auth Table Seeder Lambda for seeding default permission sets
        self._auth_seeder_lambda = Lambda(
            self,
            "AuthTableSeederLambda",
            config=LambdaConfig(
                name="auth-table-seeder",
                entry="lambdas/auth/auth_seeder",
                memory_size=256,
                timeout_minutes=2,
                environment_variables=common_env_vars,
            ),
        )

        # Add DynamoDB Stream as an event source for the Policy Sync Lambda
        self._policy_sync_lambda.function.add_event_source(
            lambda_event_sources.DynamoEventSource(
                table=self._auth_table.table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=100,
                retry_attempts=3,
            )
        )



        # 5. Create the Cognito Pre-Token Generation Lambda
        self._pre_token_generation_lambda = Lambda(
            self,
            "PreTokenGenerationLambda",
            config=LambdaConfig(
                name="cognito_pre_token_generation",
                entry="lambdas/auth/cognito_pre_token_generation",
                memory_size=256,
                timeout_minutes=1,
                environment_variables=common_env_vars,
            ),
        )

        # 6. Create the Cognito Pre-Signup Lambda
        self._pre_signup_lambda = Lambda(
            self,
            "PreSignupLambda",
            config=LambdaConfig(
                name="cognito_pre_signup",
                entry="lambdas/auth/cognito_pre_signup",
                memory_size=256,
                timeout_minutes=1,
                environment_variables=common_env_vars,
            ),
        )

        # 7. Grant necessary permissions

        # Custom Authorizer Lambda: Read access to the auth table
        # self._auth_table.table.grant_read_data(self._custom_authorizer_lambda)

        # Add the Cognito Identity Source to the AVP Policy Store
        self._identity_source = avp.CfnIdentitySource(
            self,
            "CognitoIdentitySource",
            policy_store_id=self._policy_store.attr_policy_store_id,
            configuration=avp.CfnIdentitySource.IdentitySourceConfigurationProperty(
                cognito_user_pool_configuration=avp.CfnIdentitySource.CognitoUserPoolConfigurationProperty(
                    user_pool_arn=props.cognito_user_pool.user_pool_arn,
                    client_ids=[props.user_pool_client]
                )
            ),
            principal_entity_type="MediaLake::User"
)
        
        # Policy Sync Lambda: Permissions to manage policies in AVP
        self._policy_sync_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "verifiedpermissions:CreatePolicy",
                    "verifiedpermissions:UpdatePolicy",
                    "verifiedpermissions:DeletePolicy",
                    "verifiedpermissions:ListPolicies",
                    "verifiedpermissions:GetPolicy",
                    "verifiedpermissions:BatchIsAuthorized",
                ],
                resources=[f"arn:aws:verifiedpermissions:{self.region}:{self.account}:policy-store/{self._policy_store.attr_policy_store_id}"],
            )
        )

        # Cognito Pre-Token Generation Lambda: Read access to the auth table
        self._auth_table.table.grant_read_data(self._pre_token_generation_lambda.function)

        # Cognito Pre-Signup Lambda: Write access to the auth table
        self._auth_table.table.grant_read_write_data(self._pre_signup_lambda.function)
        
        # Auth Table Seeder Lambda: Write access to the auth table
        self._auth_table.table.grant_read_write_data(self._auth_seeder_lambda.function)

        # Create a custom resource to add the Pre-Token-Generation trigger
        pre_token_generation_lambda = lambda_.Function(
            self,
            "PreTokenGenerationTriggerProvider",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3
import cfnresponse
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')

def handler(event, context):
    logger.info(f"Event: {event}")
    
    request_type = event['RequestType']
    physical_id = event.get('PhysicalResourceId', 'PreTokenGenerationTrigger')
    
    try:
        user_pool_id = event['ResourceProperties']['UserPoolId']
        lambda_arn = event['ResourceProperties']['LambdaArn']
        
        if request_type in ['Create', 'Update']:
            logger.info(f"Adding Pre-Token-Generation trigger to user pool {user_pool_id}")
            
            # Get current Lambda config
            response = cognito.describe_user_pool(UserPoolId=user_pool_id)
            lambda_config = response.get('UserPool', {}).get('LambdaConfig', {})
            
            # Update with our trigger
            lambda_config['PreTokenGeneration'] = lambda_arn
            
            # Update the user pool
            cognito.update_user_pool(
                UserPoolId=user_pool_id,
                LambdaConfig=lambda_config
            )
            
            logger.info("Successfully added Pre-Token-Generation trigger")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        elif request_type == 'Delete':
            # Optionally remove the trigger on delete
            logger.info(f"Delete request for Pre-Token-Generation trigger on user pool {user_pool_id}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        else:
            logger.error(f"Unexpected request type: {request_type}")
            cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_id)
"""),
            timeout=cdk.Duration.minutes(5),
        )
        
        # Create a provider for the Pre-Token-Generation trigger
        pre_token_generation_provider = cdk.custom_resources.Provider(
            self,
            "PreTokenGenerationProvider",
            on_event_handler=pre_token_generation_lambda,
        )
        
        
        # Create a custom resource to add the Pre-Token-Generation trigger
        pre_token_generation_trigger = cdk.CustomResource(
            self,
            "PreTokenGenerationTrigger",
            service_token=pre_token_generation_provider.service_token,
            properties={
                "UserPoolId": props.cognito_user_pool.user_pool_id,
                "LambdaArn": self._pre_token_generation_lambda.function.function_arn,
                "Timestamp": str(datetime.datetime.now().timestamp()),
            },
        )

        # Add the Pre-Token-Generation trigger to the Cognito user pool
        # props.cognito_user_pool.add_trigger(
        #     trigger_type=cognito.UserPoolTriggerType.PRE_TOKEN_GENERATION,
        #     trigger_handler=pre_token_generation_trigger,
        # )

        # Create a Lambda function for the Pre-Signup trigger
        pre_signup_lambda = lambda_.Function(
            self,
            "PreSignupTriggerProvider",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3
import cfnresponse
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')

def handler(event, context):
    logger.info(f"Event: {event}")
    
    request_type = event['RequestType']
    physical_id = event.get('PhysicalResourceId', 'PreSignupTrigger')
    
    try:
        user_pool_id = event['ResourceProperties']['UserPoolId']
        lambda_arn = event['ResourceProperties']['LambdaArn']
        
        if request_type in ['Create', 'Update']:
            logger.info(f"Adding Pre-Signup trigger to user pool {user_pool_id}")
            
            # Get current Lambda config
            response = cognito.describe_user_pool(UserPoolId=user_pool_id)
            lambda_config = response.get('UserPool', {}).get('LambdaConfig', {})
            
            # Update with our trigger
            lambda_config['PreSignUp'] = lambda_arn
            
            # Update the user pool
            cognito.update_user_pool(
                UserPoolId=user_pool_id,
                LambdaConfig=lambda_config
            )
            
            logger.info("Successfully added Pre-Signup trigger")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        elif request_type == 'Delete':
            # Optionally remove the trigger on delete
            logger.info(f"Delete request for Pre-Signup trigger on user pool {user_pool_id}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
        else:
            logger.error(f"Unexpected request type: {request_type}")
            cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_id)
"""),
            timeout=cdk.Duration.minutes(5),
        )
        
        # Create a provider for the Pre-Signup trigger
        pre_signup_provider = cdk.custom_resources.Provider(
            self,
            "PreSignupProvider",
            on_event_handler=pre_signup_lambda,
        )
        
        # Create a custom resource to add the Pre-Signup trigger
        pre_signup_trigger = cdk.CustomResource(
            self,
            "PreSignupTrigger",
            service_token=pre_signup_provider.service_token,
            properties={
                "UserPoolId": props.cognito_user_pool.user_pool_id,
                "LambdaArn": self._pre_signup_lambda.function.function_arn,
                "Timestamp": str(datetime.datetime.now().timestamp()),  # Force update on each deployment
            },
        )
        
        # 9. Create a Custom Resource to seed the default permission sets
        self._auth_seeder_custom_resource = CustomResource(
            self,
            "AuthTableSeederCustomResource",
            service_token=self._auth_seeder_lambda.function.function_arn,
            removal_policy=RemovalPolicy.RETAIN,  # Don't remove permission sets on stack deletion
            properties={
                "timestamp": str(datetime.datetime.now().timestamp()),  # Force update on each deployment
            },
        )
        
        # Ensure the custom resource is created after the DynamoDB table
        self._auth_seeder_custom_resource.node.add_dependency(self._auth_table)

    @property
    def auth_table(self):
        """Return the authorization table"""
        return self._auth_table.table

    @property
    def policy_store(self):
        """Return the AVP policy store"""
        return self._policy_store

    @property
    def policy_sync_lambda(self):
        """Return the policy sync Lambda function"""
        return self._policy_sync_lambda.function

    @property
    def pre_token_generation_lambda(self):
        """Return the pre-token generation Lambda function"""
        return self._pre_token_generation_lambda.function

    @property
    def pre_signup_lambda(self):
        """Return the pre-signup Lambda function"""
        return self._pre_signup_lambda.function
        
    @property
    def auth_seeder_lambda(self):
        """Return the auth table seeder Lambda function"""
        return self._auth_seeder_lambda.function
    
    @property
    def authorizer_lambda(self):
        """Return the custom authorizer Lambda function"""
        return self._custom_authorizer_lambda.function

    @property
    def shared_authorizer_lambda(self):
        """Return the shared authorizer Lambda function"""
        return self._shared_authorizer.authorizer_lambda
