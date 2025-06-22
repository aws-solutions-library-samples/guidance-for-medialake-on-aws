"""
Cognito Update Stack for Media Lake.

This stack handles additional Cognito User Pool configuration and triggers that need to be
applied after the core Cognito resources are created. This includes:
- Pre-signup Lambda trigger configuration
- Additional Lambda trigger setup
- User pool updates that might conflict if done during initial creation
"""

import datetime
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cognito as cognito,
    CustomResource,
    Duration,
)
import aws_cdk as cdk

from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CognitoUpdateStackProps:
    """Configuration for Cognito Update Stack."""
    cognito_user_pool: cognito.IUserPool
    cognito_user_pool_id: str
    cognito_user_pool_arn: str
    auth_table_name: str


class CognitoUpdateStack(Stack):
    """
    Stack for Cognito User Pool updates and additional trigger configuration.
    
    This stack applies additional configuration to the Cognito User Pool after
    it has been created, including triggers that might conflict if applied
    during the initial user pool creation.
    """

    def __init__(
        self, scope: Construct, id: str, props: CognitoUpdateStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        common_env_vars = {
            "AUTH_TABLE_NAME": props.auth_table_name,
            "COGNITO_USER_POOL_ID": props.cognito_user_pool_id,
        }

        # Create the Cognito Pre-Signup Lambda for additional signup validation
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

        # Create the Pre-Token Generation Lambda
        pre_token_env_vars = {
            **common_env_vars,
            "DEBUG_MODE": "true",
        }
        
        self._pre_token_generation_lambda = Lambda(
            self,
            "PreTokenGenerationLambda",
            config=LambdaConfig(
                name="pre_token_generation",
                entry="lambdas/auth/pre_token_generation",
                timeout_minutes=1,
                lambda_handler="handler",
                snap_start=False,
                environment_variables=pre_token_env_vars,
            ),
        )

        # Grant permissions for both lambdas to interact with the auth table
        auth_table_arn = f"arn:aws:dynamodb:{self.region}:{self.account}:table/{props.auth_table_name}"
        
        for lambda_function in [self._pre_signup_lambda.function, self._pre_token_generation_lambda.function]:
            lambda_function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                    ],
                    resources=[auth_table_arn],
                )
            )

        # Create a Lambda function for updating Cognito User Pool triggers
        cognito_trigger_update_lambda = lambda_.Function(
            self,
            "CognitoTriggerUpdateProvider",
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
    physical_id = event.get('PhysicalResourceId', 'CognitoTriggerUpdate')
    
         try:
         user_pool_id = event['ResourceProperties']['UserPoolId']
         pre_signup_lambda_arn = event['ResourceProperties']['PreSignupLambdaArn']
         pre_token_generation_lambda_arn = event['ResourceProperties']['PreTokenGenerationLambdaArn']
         
         if request_type in ['Create', 'Update']:
             logger.info(f"Updating triggers for user pool {user_pool_id}")
             
             # Get current user pool configuration
             response = cognito.describe_user_pool(UserPoolId=user_pool_id)
             current_config = response['UserPool']
             lambda_config = current_config.get('LambdaConfig', {})
             
             # Add or update the triggers
             lambda_config['PreSignUp'] = pre_signup_lambda_arn
             lambda_config['PreTokenGenerationConfig'] = {
                 'LambdaArn': pre_token_generation_lambda_arn,
                 'LambdaVersion': 'V2_0'
             }
            
                         # Update the user pool with the new Lambda configuration
             # Only include parameters that are valid for update_user_pool API
             update_params = {
                 'UserPoolId': user_pool_id,
                 'LambdaConfig': lambda_config
             }
             
             # Preserve existing configuration - only include updateable parameters
             if 'Policies' in current_config:
                 update_params['Policies'] = current_config['Policies']
             if 'AutoVerifiedAttributes' in current_config:
                 update_params['AutoVerifiedAttributes'] = current_config['AutoVerifiedAttributes']
             if 'AdminCreateUserConfig' in current_config:
                 update_params['AdminCreateUserConfig'] = current_config['AdminCreateUserConfig']
             if 'VerificationMessageTemplate' in current_config:
                 update_params['VerificationMessageTemplate'] = current_config['VerificationMessageTemplate']
             if 'UserPoolAddOns' in current_config:
                 update_params['UserPoolAddOns'] = current_config['UserPoolAddOns']
             # Note: UsernameAttributes cannot be updated after user pool creation
            
            cognito.update_user_pool(**update_params)
            
            logger.info("Successfully updated Cognito triggers")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
            
        elif request_type == 'Delete':
            logger.info(f"Delete request for Cognito triggers on user pool {user_pool_id}")
            # On delete, we can optionally remove our triggers
                         try:
                 response = cognito.describe_user_pool(UserPoolId=user_pool_id)
                 lambda_config = response['UserPool'].get('LambdaConfig', {})
                 
                 # Remove our triggers if they match
                 if lambda_config.get('PreSignUp') == pre_signup_lambda_arn:
                     lambda_config.pop('PreSignUp', None)
                 
                 pre_token_config = lambda_config.get('PreTokenGenerationConfig', {})
                 if pre_token_config.get('LambdaArn') == pre_token_generation_lambda_arn:
                     lambda_config.pop('PreTokenGenerationConfig', None)
                     
                     cognito.update_user_pool(
                         UserPoolId=user_pool_id,
                         LambdaConfig=lambda_config
                     )
                     logger.info("Removed Cognito triggers during cleanup")
            except Exception as cleanup_error:
                logger.warning(f"Error during trigger cleanup: {str(cleanup_error)}")
                # Don't fail the stack deletion for cleanup errors
                
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
        
        # Grant permission for the custom resource Lambda to update Cognito
        cognito_trigger_update_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:UpdateUserPool",
                ],
                resources=[props.cognito_user_pool_arn],
            )
        )
        
        # Create a provider for the Cognito trigger updates
        cognito_update_provider = cdk.custom_resources.Provider(
            self,
            "CognitoUpdateProvider",
            on_event_handler=cognito_trigger_update_lambda,
        )
        
        # Create a custom resource to update the Cognito triggers
        self._cognito_trigger_update = cdk.CustomResource(
            self,
            "CognitoTriggerUpdate",
            service_token=cognito_update_provider.service_token,
            properties={
                "UserPoolId": props.cognito_user_pool_id,
                "PreSignupLambdaArn": self._pre_signup_lambda.function.function_arn,
                "PreTokenGenerationLambdaArn": self._pre_token_generation_lambda.function.function_arn,
                "Timestamp": str(datetime.datetime.now().timestamp()),  # Force update on each deployment
            },
        )
        
        # Grant permissions for Cognito to invoke both Lambda functions
        self._pre_signup_lambda.function.add_permission(
            "CognitoInvokePermissionPreSignup",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=props.cognito_user_pool_arn,
        )
        
        self._pre_token_generation_lambda.function.add_permission(
            "CognitoInvokePermissionPreTokenGeneration",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=props.cognito_user_pool_arn,
        )

    @property
    def pre_signup_lambda(self):
        """Return the pre-signup Lambda function"""
        return self._pre_signup_lambda.function
        
    @property
    def pre_token_generation_lambda(self):
        """Return the pre-token generation Lambda function"""
        return self._pre_token_generation_lambda.function
        
    @property
    def cognito_trigger_update(self):
        """Return the Cognito trigger update custom resource"""
        return self._cognito_trigger_update 