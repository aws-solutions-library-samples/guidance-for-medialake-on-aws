# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from __future__ import print_function

import json
import re

import urllib3

SUCCESS = "SUCCESS"
FAILED = "FAILED"

http = urllib3.PoolManager()


def send(
    event,
    context,
    responseStatus,
    responseData,
    physicalResourceId=None,
    noEcho=False,
    reason=None,
):
    responseUrl = event["ResponseURL"]

    responseBody = {
        "Status": responseStatus,
        "Reason": reason
        or "See the details in CloudWatch Log Stream: {}".format(
            context.log_stream_name
        ),
        "PhysicalResourceId": physicalResourceId or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": noEcho,
        "Data": responseData,
    }

    json_responseBody = json.dumps(responseBody)

    print("Response body:")
    print(json_responseBody)

    headers = {"content-type": "", "content-length": str(len(json_responseBody))}

    try:
        response = http.request(
            "PUT", responseUrl, headers=headers, body=json_responseBody
        )
        print("Status code:", response.status)
    except Exception as e:
        print(
            "send(..) failed executing http.request(..):",
            mask_credentials_and_signature(e),
        )


def mask_credentials_and_signature(message):
    message = re.sub(
        r"X-Amz-Credential=[^&\s]+",
        "X-Amz-Credential=*****",
        message,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"X-Amz-Signature=[^&\s]+",
        "X-Amz-Signature=*****",
        message,
        flags=re.IGNORECASE,
    )
