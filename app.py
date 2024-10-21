#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
from aws_cdk import App
from medialake_stacks.user_interface_stack import UserInterfaceStack
from medialake_stacks.api_gateway_stack import ApiGatewayStack

app = App()

ui_stack = UserInterfaceStack(app, "UserInterfaceStack")
api_stack = ApiGatewayStack(
    app,
    "ApiGatewayStack",
    user_pool=ui_stack.user_pool,
    distribution=ui_stack.distribution,
)

app.synth()
