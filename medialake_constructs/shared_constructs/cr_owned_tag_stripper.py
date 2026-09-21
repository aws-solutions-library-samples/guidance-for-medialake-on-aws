"""Aspect that strips CDK's ``aws-cdk:cr-owned:*`` markers from chosen buckets.

Why this exists
---------------
``s3deploy.BucketDeployment`` unconditionally tags its destination bucket:

.. code-block:: javascript

    const tagKey = CUSTOM_RESOURCE_OWNER_TAG + prefix;   // aws-cdk:cr-owned:<prefix>:<hash>
    cdk().Tags.of(this.destinationBucket).add(tagKey, 'true');

(aws-cdk-lib ``aws-s3-deployment/lib/bucket-deployment.js``, end of the
constructor). The marker exists so CDK can detect two deployments pruning the
same key prefix. It is written whether or not ``prune`` is enabled, and it is
never consolidated — one deployment means one permanent tag on the bucket.

``NodesStack`` creates a ``LambdaDeployment`` per pipeline node, each with its own
``BucketDeployment`` into the single shared IAC assets bucket, so every node
permanently consumes one of that bucket's **50** tag slots. Measured on a
deployed dev account the bucket sat at 39/50 (34 markers, plus CloudFormation's
own ``aws:cloudformation:*`` tags and the app's ``Application`` tag) — about
eleven nodes short of failing, and the failure lands on the *BaseInfrastructure*
stack rather than the nodes stack that grew.

``LambdaDeployment`` already passes ``prune=False``, which is precisely the
behaviour the marker guards, so removing it from that bucket costs nothing:
nothing is pruned there, so there is no prefix collision to detect.

Scope
-----
Only the buckets handed to the aspect are touched, and only keys under
``aws-cdk:cr-owned:``. Buckets whose deployments still prune (the pipeline-node
templates bucket, the UI bucket) keep their markers and CDK's protection.
"""

from typing import List

import jsii
from aws_cdk import IAspect, TagManager
from aws_cdk import aws_s3 as s3
from constructs import IConstruct

# The prefix CDK uses for the marker (CUSTOM_RESOURCE_OWNER_TAG in bucket-deployment.ts).
CR_OWNED_TAG_PREFIX = "aws-cdk:cr-owned:"

# Removal priority. CDK defaults are 100 for a tag add and 200 for a tag removal, so
# anything at or above 200 wins over BucketDeployment's add. Kept explicit and high so a
# future construct that raises its add priority does not silently reinstate the marker.
_REMOVAL_PRIORITY = 1000

# Aspect priority this must be applied at: the bucket's TagManager is only populated by the
# time READONLY-priority aspects run (verified against aws-cdk-lib 2.262 — at 200, 300 and
# 500 the manager is still empty, so there would be nothing to strip).
STRIPPER_PRIORITY = 1000


@jsii.implements(IAspect)
class StripCrOwnedBucketTags:
    """Drops ``aws-cdk:cr-owned:*`` tags from the given buckets during synthesis.

    Apply at :py:attr:`~aws_cdk.AspectPriority.READONLY` (1000) or later. The marker keys
    carry a construct-address hash, so they can only be discovered by reading the bucket's
    :class:`TagManager` — and measurement shows the manager is still empty when aspects run
    at 200/300/500 and populated at 1000. The removal itself is applied at a priority above
    CDK's tag-add default, and rendering happens after every aspect, so a late removal still
    takes effect. See ``STRIPPER_PRIORITY``.
    """

    def __init__(self, *buckets: s3.IBucket) -> None:
        # Matched by construct path, not identity: jsii hands ``visit`` a different Python
        # proxy for the same underlying resource, so ``is`` comparisons never match.
        self._target_paths = set()
        for bucket in buckets:
            default_child = bucket.node.default_child
            if isinstance(default_child, s3.CfnBucket):
                self._target_paths.add(default_child.node.path)
        # Keys stripped so far, for assertions and for operators reading synth output.
        self.removed_tag_keys: List[str] = []

    def visit(self, node: IConstruct) -> None:
        if node.node.path not in self._target_paths:
            return
        tags = getattr(node, "tags", None)
        if not isinstance(tags, TagManager):
            return
        for key in list(tags.tag_values().keys()):
            if key.startswith(CR_OWNED_TAG_PREFIX):
                tags.remove_tag(key, _REMOVAL_PRIORITY)
                self.removed_tag_keys.append(key)
