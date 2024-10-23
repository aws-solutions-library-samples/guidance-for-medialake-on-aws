#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
# from aws_cdk import App
import aws_cdk as cdk

# from aws_cdk import Aspects
from medialake_stacks.datalake import DataLake

# ui_stack = UserInterfaceStack(app, "UserInterfaceStack")
# api_stack = ApiGatewayStack(
#     app,
#     "ApiGatewayStack",
#     user_pool=ui_stack.user_pool,
#     distribution=ui_stack.distribution,
# )

app = cdk.App()

data_lake_for_media = DataLake(app, "MediaLake")


app.synth()
