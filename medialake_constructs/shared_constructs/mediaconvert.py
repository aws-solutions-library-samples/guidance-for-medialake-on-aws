from typing import List, Optional, Union

from aws_cdk import CfnTag
from aws_cdk import aws_mediaconvert as mediaconvert
from constructs import Construct


class MediaConvertProps:
    def __init__(
        self,
        *,
        description: Optional[str] = None,
        name: Optional[str] = None,
        pricing_plan: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[Union[CfnTag, dict]]] = None,
    ) -> None:
        """
        Properties for configuring a MediaConvert Queue.

        :param description: A description of the queue you are creating.
        :param name: The name of the queue you are creating.
        :param pricing_plan: Must be 'ON_DEMAND' when creating queues via CloudFormation.
                            (The console is required for 'RESERVED'.)
        :param status: Initial state of the queue. Valid values: 'ACTIVE' or 'PAUSED'.
        :param tags: A list of key-value pairs (tags) to apply to this queue.
                     Each item can be a dict: {'key': '...', 'value': '...'} or a CfnTag object.
        """
        self.description = description
        self.name = name
        self.pricing_plan = pricing_plan
        self.status = status
        self.tags = tags


class MediaConvert(Construct):
    """
    A custom L2 construct that creates an AWS MediaConvert queue.
    You can extend this construct to manage additional MediaConvert resources
    such as job templates, presets, etc.
    """

    def __init__(
        self, scope: Construct, construct_id: str, *, props: MediaConvertProps
    ) -> None:
        super().__init__(scope, construct_id)

        # Convert tags to the format expected by CDK
        tag_dict: Dict[str, str] = {}
        if props.tags:
            for tag in props.tags:
                if isinstance(tag, dict):
                    if len(tag) == 1:
                        key, value = next(iter(tag.items()))
                        tag_dict[key] = str(value)
                    elif "key" in tag and "value" in tag:
                        tag_dict[tag["key"]] = str(tag["value"])
                    else:
                        raise ValueError(f"Invalid tag format: {tag}")
                elif isinstance(tag, CfnTag):
                    tag_dict[tag.key] = tag.value
                else:
                    raise ValueError(f"Invalid tag type: {type(tag)}")

        # Create the underlying L1 resource
        self._queue = mediaconvert.CfnQueue(
            self,
            "Queue",
            description=props.description,
            name=props.name,
            pricing_plan=props.pricing_plan,
            status=props.status,
            tags=tag_dict,
        )

    @property
    def queue_arn(self) -> str:
        """Returns the ARN of the MediaConvert queue."""
        return self._queue.attr_arn

    @property
    def queue_id(self) -> str:
        """
        Returns the ID of the MediaConvert queue.
        Note: This is the internal MediaConvert queue ID,
        not the CloudFormation resource ID.
        """
        return self._queue.attr_id

    @property
    def queue_name(self) -> str:
        """
        Returns the name of the MediaConvert queue.
        If not provided, you can retrieve this after deployment
        (CloudFormation auto-generates a name if none is specified).
        """
        # The L1 property might be None if name wasn't provided.
        # The attr_name provides the actual name used by MediaConvert.
        return self._queue.attr_name

    @classmethod
    def create_queue(
        cls, scope: Construct, construct_id: str, *, props: MediaConvertProps
    ) -> "MediaConvert":
        """
        Factory method to create a MediaConvert queue.

        :param scope: The scope in which to define this construct.
        :param construct_id: The construct ID.
        :param props: The properties for configuring the MediaConvert queue.
        :return: An instance of the MediaConvert class.
        """
        return cls(scope, construct_id, props=props)
