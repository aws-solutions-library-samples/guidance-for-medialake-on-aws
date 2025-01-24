from utils import common_utility, shared_helper, node_specific_helper


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": {
            "common_utility": common_utility(),  # Should use node-specific version
            "shared_helper": shared_helper(),  # From common libraries
            "node_helper": node_specific_helper(),  # From node-specific libraries
        },
    }
