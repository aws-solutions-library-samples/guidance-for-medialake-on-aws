"""
Collections API Gateway module for MediaLake.

This module defines the CollectionsApi class which sets up API Gateway endpoints
and associated Lambda functions for managing collections. It handles:
- Collection types and metadata management
- Collection item management with batch operations
- Collection rules for automatic item assignment
- Collection sharing and permissions
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration
- Lambda function configuration
"""

import os
from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class CollectionsApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer


class CollectionsApi(Construct):
    """
    Collections API Gateway deployment with single-table DynamoDB design
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: CollectionsApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        from config import config

        # Get the current account ID
        Stack.of(self).account

        # Create single Collections table with GSIs following the schema design
        gsi_list = [
            # GSI1: UserCollectionsGSI - Find all collections a user has access to
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="UserCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI1_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI1_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI2: ItemCollectionsGSI - Find all collections containing a specific item
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ItemCollectionsGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI2_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI2_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI3: CollectionTypeGSI - Find collections by type
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="CollectionTypeGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI3_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI3_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI4: ParentChildGSI - Find all parent collections of a child collection
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="ParentChildGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI4_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI4_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
            # GSI5: RecentlyModifiedGSI - Find recently modified collections system-wide
            dynamodb.GlobalSecondaryIndexPropsV2(
                index_name="RecentlyModifiedGSI",
                partition_key=dynamodb.Attribute(
                    name="GSI5_PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="GSI5_SK", type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            ),
        ]

        self._collections_table = DynamoDB(
            self,
            "CollectionsTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_collections_{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                global_secondary_indexes=gsi_list,
                ttl_attribute="expiresAt",
            ),
        )

        # Create collections resource hierarchy
        collections_resource = props.api_resource.root.add_resource("collections")

        # /collection-types endpoints
        collection_types_resource = props.api_resource.root.add_resource(
            "collection-types"
        )

        # GET /collection-types
        collection_types_get_lambda = Lambda(
            self,
            "CollectionTypesGetLambda",
            config=LambdaConfig(
                name="collection_types_get",
                entry="lambdas/api/collections/collection-types/get_collection_types",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(
            collection_types_get_lambda.function
        )

        collection_types_get_integration = api_gateway.LambdaIntegration(
            collection_types_get_lambda.function
        )

        collection_types_get_method = collection_types_resource.add_method(
            "GET",
            collection_types_get_integration,
        )

        cfn_method = collection_types_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /collection-types
        collection_types_post_lambda = Lambda(
            self,
            "CollectionTypesPostLambda",
            config=LambdaConfig(
                name="collection_types_post",
                entry="lambdas/api/collections/collection-types/post_collection_type",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            collection_types_post_lambda.function
        )

        collection_types_post_integration = api_gateway.LambdaIntegration(
            collection_types_post_lambda.function
        )

        collection_types_post_method = collection_types_resource.add_method(
            "POST",
            collection_types_post_integration,
        )

        cfn_method = collection_types_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # GET /collections
        collections_get_lambda = Lambda(
            self,
            "CollectionsGetLambda",
            config=LambdaConfig(
                name="collections_get",
                entry="lambdas/api/collections/collections/get_collections",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(collections_get_lambda.function)

        collections_get_integration = api_gateway.LambdaIntegration(
            collections_get_lambda.function
        )

        collections_get_method = collections_resource.add_method(
            "GET",
            collections_get_integration,
        )

        cfn_method = collections_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /collections
        collections_post_lambda = Lambda(
            self,
            "CollectionsPostLambda",
            config=LambdaConfig(
                name="collections_post",
                entry="lambdas/api/collections/collections/post_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            collections_post_lambda.function
        )

        collections_post_integration = api_gateway.LambdaIntegration(
            collections_post_lambda.function
        )

        collections_post_method = collections_resource.add_method(
            "POST",
            collections_post_integration,
        )

        cfn_method = collections_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId} endpoints
        collection_id_resource = collections_resource.add_resource("{collectionId}")

        # GET /collections/{collectionId}
        collection_get_lambda = Lambda(
            self,
            "CollectionGetLambda",
            config=LambdaConfig(
                name="collection_get",
                entry="lambdas/api/collections/collections/get_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(collection_get_lambda.function)

        collection_get_integration = api_gateway.LambdaIntegration(
            collection_get_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        collection_get_method = collection_id_resource.add_method(
            "GET",
            collection_get_integration,
        )

        cfn_method = collection_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # PATCH /collections/{collectionId}
        collection_patch_lambda = Lambda(
            self,
            "CollectionPatchLambda",
            config=LambdaConfig(
                name="collection_patch",
                entry="lambdas/api/collections/collections/patch_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            collection_patch_lambda.function
        )

        collection_patch_integration = api_gateway.LambdaIntegration(
            collection_patch_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        collection_patch_method = collection_id_resource.add_method(
            "PATCH",
            collection_patch_integration,
        )

        cfn_method = collection_patch_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /collections/{collectionId}
        collection_delete_lambda = Lambda(
            self,
            "CollectionDeleteLambda",
            config=LambdaConfig(
                name="collection_delete",
                entry="lambdas/api/collections/collections/delete_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            collection_delete_lambda.function
        )

        collection_delete_integration = api_gateway.LambdaIntegration(
            collection_delete_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        collection_delete_method = collection_id_resource.add_method(
            "DELETE",
            collection_delete_integration,
        )

        cfn_method = collection_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/items endpoints
        items_resource = collection_id_resource.add_resource("items")

        # GET /collections/{collectionId}/items
        items_get_lambda = Lambda(
            self,
            "ItemsGetLambda",
            config=LambdaConfig(
                name="items_get",
                entry="lambdas/api/collections/collections/get_collection_items",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(items_get_lambda.function)

        items_get_integration = api_gateway.LambdaIntegration(
            items_get_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        items_get_method = items_resource.add_method(
            "GET",
            items_get_integration,
        )

        cfn_method = items_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /collections/{collectionId}/items
        items_post_lambda = Lambda(
            self,
            "ItemsPostLambda",
            config=LambdaConfig(
                name="items_post",
                entry="lambdas/api/collections/collections/add_collection_item",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(items_post_lambda.function)

        items_post_integration = api_gateway.LambdaIntegration(
            items_post_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        items_post_method = items_resource.add_method(
            "POST",
            items_post_integration,
        )

        cfn_method = items_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/items/batch endpoints
        batch_resource = items_resource.add_resource("batch")

        # POST /collections/{collectionId}/items/batch
        batch_post_lambda = Lambda(
            self,
            "BatchPostLambda",
            config=LambdaConfig(
                name="batch_post",
                entry="lambdas/api/collections/collections/batch_add_items",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(batch_post_lambda.function)

        batch_post_integration = api_gateway.LambdaIntegration(
            batch_post_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        batch_post_method = batch_resource.add_method(
            "POST",
            batch_post_integration,
        )

        cfn_method = batch_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/items/batch-remove endpoints
        batch_remove_resource = items_resource.add_resource("batch-remove")

        # POST /collections/{collectionId}/items/batch-remove
        batch_remove_post_lambda = Lambda(
            self,
            "BatchRemovePostLambda",
            config=LambdaConfig(
                name="batch_remove_post",
                entry="lambdas/api/collections/collections/batch_remove_items",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            batch_remove_post_lambda.function
        )

        batch_remove_post_integration = api_gateway.LambdaIntegration(
            batch_remove_post_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        batch_remove_post_method = batch_remove_resource.add_method(
            "POST",
            batch_remove_post_integration,
        )

        cfn_method = batch_remove_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/items/{itemId} endpoints
        item_id_resource = items_resource.add_resource("{itemId}")

        # PUT /collections/{collectionId}/items/{itemId}
        item_put_lambda = Lambda(
            self,
            "ItemPutLambda",
            config=LambdaConfig(
                name="item_put",
                entry="lambdas/api/collections/collections/update_collection_item",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(item_put_lambda.function)

        item_put_integration = api_gateway.LambdaIntegration(
            item_put_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')", "itemId": "$input.params(\'itemId\')" }'
            },
        )

        item_put_method = item_id_resource.add_method(
            "PUT",
            item_put_integration,
        )

        cfn_method = item_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /collections/{collectionId}/items/{itemId}
        item_delete_lambda = Lambda(
            self,
            "ItemDeleteLambda",
            config=LambdaConfig(
                name="item_delete",
                entry="lambdas/api/collections/collections/remove_collection_item",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(item_delete_lambda.function)

        item_delete_integration = api_gateway.LambdaIntegration(
            item_delete_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')", "itemId": "$input.params(\'itemId\')" }'
            },
        )

        item_delete_method = item_id_resource.add_method(
            "DELETE",
            item_delete_integration,
        )

        cfn_method = item_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/rules endpoints
        rules_resource = collection_id_resource.add_resource("rules")

        # GET /collections/{collectionId}/rules
        rules_get_lambda = Lambda(
            self,
            "RulesGetLambda",
            config=LambdaConfig(
                name="rules_get",
                entry="lambdas/api/collections/collections/get_collection_rules",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(rules_get_lambda.function)

        rules_get_integration = api_gateway.LambdaIntegration(
            rules_get_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        rules_get_method = rules_resource.add_method(
            "GET",
            rules_get_integration,
        )

        cfn_method = rules_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /collections/{collectionId}/rules
        rules_post_lambda = Lambda(
            self,
            "RulesPostLambda",
            config=LambdaConfig(
                name="rules_post",
                entry="lambdas/api/collections/collections/create_collection_rule",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(rules_post_lambda.function)

        rules_post_integration = api_gateway.LambdaIntegration(
            rules_post_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        rules_post_method = rules_resource.add_method(
            "POST",
            rules_post_integration,
        )

        cfn_method = rules_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/rules/{ruleId} endpoints
        rule_id_resource = rules_resource.add_resource("{ruleId}")

        # PUT /collections/{collectionId}/rules/{ruleId}
        rule_put_lambda = Lambda(
            self,
            "RulePutLambda",
            config=LambdaConfig(
                name="rule_put",
                entry="lambdas/api/collections/collections/update_collection_rule",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(rule_put_lambda.function)

        rule_put_integration = api_gateway.LambdaIntegration(
            rule_put_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')", "ruleId": "$input.params(\'ruleId\')" }'
            },
        )

        rule_put_method = rule_id_resource.add_method(
            "PUT",
            rule_put_integration,
        )

        cfn_method = rule_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # DELETE /collections/{collectionId}/rules/{ruleId}
        rule_delete_lambda = Lambda(
            self,
            "RuleDeleteLambda",
            config=LambdaConfig(
                name="rule_delete",
                entry="lambdas/api/collections/collections/delete_collection_rule",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(rule_delete_lambda.function)

        rule_delete_integration = api_gateway.LambdaIntegration(
            rule_delete_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')", "ruleId": "$input.params(\'ruleId\')" }'
            },
        )

        rule_delete_method = rule_id_resource.add_method(
            "DELETE",
            rule_delete_integration,
        )

        cfn_method = rule_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/share endpoints
        share_resource = collection_id_resource.add_resource("share")

        # GET /collections/{collectionId}/share
        share_get_lambda = Lambda(
            self,
            "ShareGetLambda",
            config=LambdaConfig(
                name="share_get",
                entry="lambdas/api/collections/collections/get_collection_shares",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(share_get_lambda.function)

        share_get_integration = api_gateway.LambdaIntegration(
            share_get_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        share_get_method = share_resource.add_method(
            "GET",
            share_get_integration,
        )

        cfn_method = share_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # POST /collections/{collectionId}/share
        share_post_lambda = Lambda(
            self,
            "SharePostLambda",
            config=LambdaConfig(
                name="share_post",
                entry="lambdas/api/collections/collections/share_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(share_post_lambda.function)

        share_post_integration = api_gateway.LambdaIntegration(
            share_post_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        share_post_method = share_resource.add_method(
            "POST",
            share_post_integration,
        )

        cfn_method = share_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/share/{userId} endpoints
        share_user_id_resource = share_resource.add_resource("{userId}")

        # DELETE /collections/{collectionId}/share/{userId}
        share_user_delete_lambda = Lambda(
            self,
            "ShareUserDeleteLambda",
            config=LambdaConfig(
                name="share_user_delete",
                entry="lambdas/api/collections/collections/unshare_collection",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_write_data(
            share_user_delete_lambda.function
        )

        share_user_delete_integration = api_gateway.LambdaIntegration(
            share_user_delete_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')", "userId": "$input.params(\'userId\')" }'
            },
        )

        share_user_delete_method = share_user_id_resource.add_method(
            "DELETE",
            share_user_delete_integration,
        )

        cfn_method = share_user_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/shared-with-me endpoint
        shared_with_me_resource = collections_resource.add_resource("shared-with-me")

        # GET /collections/shared-with-me
        shared_with_me_get_lambda = Lambda(
            self,
            "SharedWithMeGetLambda",
            config=LambdaConfig(
                name="shared_with_me_get",
                entry="lambdas/api/collections/collections/get_shared_collections",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                },
            ),
        )

        self._collections_table.table.grant_read_data(
            shared_with_me_get_lambda.function
        )

        shared_with_me_get_integration = api_gateway.LambdaIntegration(
            shared_with_me_get_lambda.function
        )

        shared_with_me_get_method = shared_with_me_resource.add_method(
            "GET",
            shared_with_me_get_integration,
        )

        cfn_method = shared_with_me_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /collections/{collectionId}/assets endpoints
        assets_resource = collection_id_resource.add_resource("assets")

        # GET /collections/{collectionId}/assets
        assets_get_lambda = Lambda(
            self,
            "AssetsGetLambda",
            config=LambdaConfig(
                name="assets_get",
                entry="lambdas/api/collections/collections/get_collection_assets",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": self._collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": self._collections_table.table_arn,
                    "OPENSEARCH_ENDPOINT": os.environ.get("OPENSEARCH_ENDPOINT", ""),
                    "OPENSEARCH_INDEX": os.environ.get("OPENSEARCH_INDEX", ""),
                    "SCOPE": "es",
                },
            ),
        )

        self._collections_table.table.grant_read_data(assets_get_lambda.function)

        # Grant OpenSearch access permissions
        opensearch_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "es:ESHttpGet",
                "es:ESHttpPost",
                "es:ESHttpPut",
            ],
            resources=[
                f"arn:aws:es:{Stack.of(self).region}:{Stack.of(self).account}:domain/*"
            ],
        )
        assets_get_lambda.function.add_to_role_policy(opensearch_policy)

        assets_get_integration = api_gateway.LambdaIntegration(
            assets_get_lambda.function,
            request_templates={
                "application/json": '{ "collectionId": "$input.params(\'collectionId\')" }'
            },
        )

        assets_get_method = assets_resource.add_method(
            "GET",
            assets_get_integration,
        )

        cfn_method = assets_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(collection_types_resource)
        add_cors_options_method(collections_resource)
        add_cors_options_method(collection_id_resource)
        add_cors_options_method(items_resource)
        add_cors_options_method(batch_resource)
        add_cors_options_method(batch_remove_resource)
        add_cors_options_method(item_id_resource)
        add_cors_options_method(assets_resource)
        add_cors_options_method(rules_resource)
        add_cors_options_method(rule_id_resource)
        add_cors_options_method(share_resource)
        add_cors_options_method(share_user_id_resource)
        add_cors_options_method(shared_with_me_resource)

    @property
    def collections_table(self) -> DynamoDB:
        """
        Get the Collections DynamoDB table construct.

        Returns:
            DynamoDB: The Collections table construct
        """
        return self._collections_table
