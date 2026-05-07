from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from config import config


class CloudFrontWafStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):

        super().__init__(scope, construct_id, **kwargs)
        self.template_options.description = "Guidance for MediaLake on AWS (SO9598)"

        self.web_acl = wafv2.CfnWebACL(
            self,
            "CloudFrontWAF",
            default_action={"allow": {}},
            scope="CLOUDFRONT",
            visibility_config={
                "sampledRequestsEnabled": True,
                "cloudWatchMetricsEnabled": True,
                "metricName": "CloudFrontWAFMetrics",
            },
            rules=[
                {
                    "name": "AWSManagedRulesCommonRuleSet",
                    "priority": 1,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesCommonRuleSet",
                            "ruleActionOverrides": [
                                {
                                    "name": "SizeRestrictions_BODY",
                                    "actionToUse": {"allow": {}},
                                }
                            ],
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "AWSManagedRulesCommonRuleSetMetric",
                    },
                },
                {
                    "name": "AWSManagedRulesKnownBadInputsRuleSet",
                    "priority": 2,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesKnownBadInputsRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "KnownBadInputsRuleSetMetric",
                    },
                },
                {
                    "name": "PortalPublicChallengeRule",
                    "priority": 3,
                    "action": {"challenge": {}},
                    "statement": {
                        "byteMatchStatement": {
                            "searchString": "/p/",
                            "fieldToMatch": {"uriPath": {}},
                            "textTransformations": [{"priority": 0, "type": "NONE"}],
                            "positionalConstraint": "STARTS_WITH",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "PortalPublicChallengeRuleMetric",
                    },
                },
                {
                    "name": "PortalApiRateLimitRule",
                    "priority": 4,
                    "action": {"block": {}},
                    "statement": {
                        "rateBasedStatement": {
                            "limit": config.portal_rate_limit_per_5min or 1000,
                            "aggregateKeyType": "IP",
                            "scopeDownStatement": {
                                "byteMatchStatement": {
                                    "searchString": "/portal/",
                                    "fieldToMatch": {"uriPath": {}},
                                    "textTransformations": [
                                        {"priority": 0, "type": "NONE"}
                                    ],
                                    "positionalConstraint": "STARTS_WITH",
                                }
                            },
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "PortalApiRateLimitRuleMetric",
                    },
                },
            ],
        )

        # Store WAF ACL ARN in SSM Parameter Store for cross-region access
        self.waf_acl_parameter = ssm.StringParameter(
            self,
            "CloudFrontWafAclArnParam",
            parameter_name=config.ssm_param_global("cloudfront-waf-acl-arn"),
            string_value=self.web_acl.attr_arn,
            description="ARN of the CloudFront WAF ACL",
        )

        # Output the WAF ACL ARN for reference
        CfnOutput(
            self,
            "CloudFrontWafAclArn",
            value=self.web_acl.attr_arn,
            description="ARN of the CloudFront WAF ACL",
        )
