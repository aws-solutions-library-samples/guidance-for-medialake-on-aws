#!/usr/bin/env python3
"""
This module serves as the entry point for the MediaLake CDK application.
"""
import aws_cdk as cdk
from config import config
from medialake_stacks.datalake import DataLake

app = cdk.App()

primary_stack = DataLake(
    app, 
    "MediaLake", 
    env={
        "region": config.primary_region,
        "account": app.account
    }
)

if config.enable_ha and config.secondary_region:
    secondary_stack = DataLake(
        app, 
        "MediaLakeSecondary", 
        env={
            "region": config.secondary_region,
            "account": app.account
        }
    )

app.synth()
