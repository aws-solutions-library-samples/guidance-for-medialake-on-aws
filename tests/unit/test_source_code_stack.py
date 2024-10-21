import aws_cdk as core
import aws_cdk.assertions as assertions

from source_code.source_code_stack import SourceCodeStack

# example tests. To run these tests, uncomment this file along with the example
# resource in source_code/source_code_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = SourceCodeStack(app, "source-code")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
