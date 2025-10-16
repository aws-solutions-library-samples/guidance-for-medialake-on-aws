"""
Service for managing CodePipeline operations for auto-upgrade system.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class PipelineService:
    """Service for CodePipeline operations."""

    def __init__(self):
        """Initialize the pipeline service."""
        self.codepipeline = boto3.client("codepipeline")
        self.pipeline_name = os.environ.get("CODEPIPELINE_NAME", "")

        if not self.pipeline_name:
            logger.warning("CODEPIPELINE_NAME environment variable not set")

    def get_pipeline_name(self) -> str:
        """
        Get the CodePipeline name from CloudFormation or environment.

        Returns:
            Pipeline name
        """
        if self.pipeline_name:
            return self.pipeline_name

        # Try to discover pipeline name from CloudFormation
        try:
            cfn = boto3.client("cloudformation")
            resource_prefix = os.environ.get("RESOURCE_PREFIX", "medialake")
            os.environ.get("ENVIRONMENT", "prd")

            # List stacks to find the pipeline
            response = cfn.list_stacks(
                StackStatusFilter=["CREATE_COMPLETE", "UPDATE_COMPLETE"]
            )

            for stack in response.get("StackSummaries", []):
                if f"{resource_prefix}" in stack["StackName"].lower():
                    # Get stack resources
                    resources = cfn.list_stack_resources(StackName=stack["StackName"])

                    for resource in resources.get("StackResourceSummaries", []):
                        if resource["ResourceType"] == "AWS::CodePipeline::Pipeline":
                            self.pipeline_name = resource["PhysicalResourceId"]
                            logger.info(
                                f"Discovered pipeline name: {self.pipeline_name}"
                            )
                            return self.pipeline_name

            logger.warning("Could not discover pipeline name from CloudFormation")
            return ""

        except Exception as e:
            logger.error(f"Error discovering pipeline name: {e}")
            return ""

    def trigger_upgrade(
        self, target_version: str, version_type: str, user_email: str
    ) -> Dict[str, Any]:
        """
        Trigger CodePipeline execution with specified version.

        Args:
            target_version: Target version (branch or tag name)
            version_type: Type of version ('branch' or 'tag')
            user_email: Email of user triggering upgrade

        Returns:
            Dictionary with execution details

        Raises:
            Exception: If pipeline trigger fails
        """
        try:
            pipeline_name = self.get_pipeline_name()

            if not pipeline_name:
                raise ValueError("Pipeline name not configured")

            logger.info(
                f"Triggering pipeline {pipeline_name} for version {target_version} ({version_type})"
            )

            # Update pipeline source configuration
            self._update_pipeline_source(pipeline_name, target_version, version_type)

            # Start pipeline execution
            response = self.codepipeline.start_pipeline_execution(
                name=pipeline_name,
                clientRequestToken=f"upgrade-{target_version}-{int(datetime.now(timezone.utc).timestamp())}",
            )

            execution_id = response["pipelineExecutionId"]

            logger.info(f"Successfully triggered pipeline execution: {execution_id}")

            return {
                "pipeline_execution_id": execution_id,
                "pipeline_name": pipeline_name,
                "target_version": target_version,
                "version_type": version_type,
                "triggered_by": user_email,
                "start_time": datetime.now(timezone.utc).isoformat(),
            }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(f"CodePipeline error ({error_code}): {error_message}")
            raise Exception(f"Failed to trigger pipeline: {error_message}")
        except Exception as e:
            logger.error(f"Error triggering upgrade: {e}")
            raise

    def _update_pipeline_source(
        self, pipeline_name: str, target_version: str, version_type: str
    ) -> None:
        """
        Update pipeline source configuration to use specified version.

        Args:
            pipeline_name: Name of the pipeline
            target_version: Target version
            version_type: Type of version ('branch' or 'tag')
        """
        try:
            # Get current pipeline configuration
            response = self.codepipeline.get_pipeline(name=pipeline_name)
            pipeline = response["pipeline"]

            # Find the source stage
            for stage in pipeline["stages"]:
                if stage["name"] == "Source":
                    for action in stage["actions"]:
                        if action["actionTypeId"]["provider"] in [
                            "GitHub",
                            "CodeStarSourceConnection",
                            "S3",
                        ]:
                            # Update the branch/tag configuration
                            if "configuration" in action:
                                config = action["configuration"]

                                # Update based on source type
                                if "Branch" in config:
                                    config["Branch"] = target_version
                                    logger.info(
                                        f"Updated source branch to: {target_version}"
                                    )
                                elif "BranchName" in config:
                                    config["BranchName"] = target_version
                                    logger.info(
                                        f"Updated source branch name to: {target_version}"
                                    )

                                # For tags, we might need to handle differently
                                if version_type == "tag" and "Branch" in config:
                                    # Some source providers support tags through branch parameter
                                    config["Branch"] = f"refs/tags/{target_version}"
                                    logger.info(
                                        f"Updated source to tag: {target_version}"
                                    )

            # Update the pipeline
            self.codepipeline.update_pipeline(pipeline=pipeline)
            logger.info(f"Successfully updated pipeline source configuration")

        except ClientError as e:
            logger.error(f"Failed to update pipeline source: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating pipeline source: {e}")
            raise

    def get_pipeline_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get the status of a pipeline execution.

        Args:
            execution_id: Pipeline execution ID

        Returns:
            Dictionary with execution status details
        """
        try:
            pipeline_name = self.get_pipeline_name()

            if not pipeline_name:
                raise ValueError("Pipeline name not configured")

            response = self.codepipeline.get_pipeline_execution(
                pipelineName=pipeline_name, pipelineExecutionId=execution_id
            )

            execution = response["pipelineExecution"]
            status = execution["status"]

            # Calculate progress based on stage completion
            progress = self._calculate_progress(pipeline_name, execution_id)

            return {
                "status": status,
                "execution_id": execution_id,
                "start_time": execution.get(
                    "startTime", datetime.now(timezone.utc)
                ).isoformat(),
                "progress": progress,
            }

        except ClientError as e:
            logger.error(f"Failed to get pipeline execution status: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting pipeline execution status: {e}")
            raise

    def _calculate_progress(
        self, pipeline_name: str, execution_id: str
    ) -> Dict[str, Any]:
        """
        Calculate progress percentage based on pipeline stages.

        Args:
            pipeline_name: Name of the pipeline
            execution_id: Pipeline execution ID

        Returns:
            Progress information dictionary
        """
        try:
            # Get pipeline state
            response = self.codepipeline.get_pipeline_state(name=pipeline_name)

            stages = response.get("stageStates", [])
            total_stages = len(stages)
            completed_stages = 0
            current_stage = "Unknown"
            current_action = "Processing"

            for stage in stages:
                stage_status = stage.get("latestExecution", {}).get("status", "Unknown")

                if stage_status == "Succeeded":
                    completed_stages += 1
                elif stage_status == "InProgress":
                    current_stage = stage["stageName"]
                    # Get current action
                    for action in stage.get("actionStates", []):
                        if (
                            action.get("latestExecution", {}).get("status")
                            == "InProgress"
                        ):
                            current_action = action["actionName"]
                            break
                    break
                elif stage_status in ["Failed", "Stopped"]:
                    current_stage = stage["stageName"]
                    current_action = f"Failed at {stage['stageName']}"
                    break

            percentage = (
                int((completed_stages / total_stages) * 100) if total_stages > 0 else 0
            )

            return {
                "stage": current_stage,
                "percentage": percentage,
                "current_action": current_action,
            }

        except Exception as e:
            logger.warning(f"Could not calculate progress: {e}")
            return {"stage": "Unknown", "percentage": 0, "current_action": "Processing"}

    def list_recent_executions(self, max_results: int = 10) -> list:
        """
        List recent pipeline executions.

        Args:
            max_results: Maximum number of results to return

        Returns:
            List of pipeline executions
        """
        try:
            pipeline_name = self.get_pipeline_name()

            if not pipeline_name:
                return []

            response = self.codepipeline.list_pipeline_executions(
                pipelineName=pipeline_name, maxResults=max_results
            )

            return response.get("pipelineExecutionSummaries", [])

        except Exception as e:
            logger.error(f"Error listing pipeline executions: {e}")
            return []
