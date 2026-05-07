import os
import shutil
import sys
import tempfile
from dataclasses import dataclass

import boto3
import yaml
from botocore.exceptions import ClientError


@dataclass
class ExternalNodeDescriptor:
    node_id: str
    node_type: str
    handler_path: str
    construct_id: str
    parent_folder: str
    local_staging_path: str


class ExternalNodesSynthHelper:
    def __init__(
        self, bucket_name: str, built_in_node_ids: set, built_in_construct_ids: set
    ):
        self.bucket_name = bucket_name
        self.built_in_node_ids = built_in_node_ids
        self.built_in_construct_ids = built_in_construct_ids
        self._templates_staging_path = os.path.join(
            tempfile.gettempdir(), "medialake_external_templates", bucket_name
        )

    @property
    def templates_staging_path(self) -> str:
        """Local directory where external YAML templates are staged during synth."""
        return self._templates_staging_path

    def stage_templates(self) -> None:
        """Download external node_templates/*.yaml from S3 to a local temp directory."""
        if os.path.exists(self._templates_staging_path):
            shutil.rmtree(self._templates_staging_path)
        os.makedirs(self._templates_staging_path, exist_ok=True)

        s3 = boto3.client("s3")
        prefix = "node_templates/"
        all_keys = []
        continuation_token = None
        try:
            while True:
                kwargs = {"Bucket": self.bucket_name, "Prefix": prefix}
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token
                resp = s3.list_objects_v2(**kwargs)
                all_keys.extend(obj["Key"] for obj in resp.get("Contents", []))
                if not resp.get("IsTruncated"):
                    break
                continuation_token = resp["NextContinuationToken"]
        except ClientError as e:
            err = e.response["Error"]
            print(
                f"Failed to list templates in bucket '{self.bucket_name}': {err['Code']} - {err['Message']}",
                file=sys.stderr,
            )
            sys.exit(1)

        all_keys = [
            k for k in all_keys if k.endswith((".yaml", ".yml")) and not k.endswith("/")
        ]

        for obj_key in all_keys:
            relative = obj_key
            if not relative:
                continue
            local_path = os.path.join(self._templates_staging_path, relative)
            try:
                body = s3.get_object(Bucket=self.bucket_name, Key=obj_key)[
                    "Body"
                ].read()
            except ClientError as e:
                err = e.response["Error"]
                print(
                    f"Failed to fetch template '{obj_key}' from bucket '{self.bucket_name}': {err['Code']} - {err['Message']}",
                    file=sys.stderr,
                )
                sys.exit(1)
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(body)
            except OSError as e:
                print(
                    f"Filesystem error staging '{obj_key}' to '{local_path}': {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

    @staticmethod
    def _get_nested(data, *keys):
        for key in keys:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
            if data is None:
                return None
        return data

    def run(self) -> list:
        # a. Bucket access + YAML discovery
        s3 = boto3.client("s3")
        try:
            response = s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix="node_templates/"
            )
        except ClientError as e:
            err = e.response["Error"]
            print(
                f"Failed to access bucket '{self.bucket_name}': {err['Code']} - {err['Message']}",
                file=sys.stderr,
            )
            sys.exit(1)

        contents = response.get("Contents", [])
        yaml_keys = [
            obj["Key"] for obj in contents if obj["Key"].endswith((".yaml", ".yml"))
        ]
        if not yaml_keys:
            print(
                f"No node templates (.yaml/.yml) found in bucket '{self.bucket_name}' under 'node_templates/'",
                file=sys.stderr,
            )
            sys.exit(1)

        # b. YAML fetch + schema validation
        required_fields = [
            (("node", "id"), "node.id"),
            (("node", "title"), "node.title"),
            (("node", "type"), "node.type"),
            (
                ("node", "integration", "config", "lambda", "handler"),
                "node.integration.config.lambda.handler",
            ),
            (
                ("node", "integration", "config", "lambda", "lambda_source_path"),
                "node.integration.config.lambda.lambda_source_path",
            ),
        ]

        parsed_nodes = []
        for key in yaml_keys:
            try:
                body = s3.get_object(Bucket=self.bucket_name, Key=key)["Body"].read()
            except ClientError as e:
                err = e.response["Error"]
                print(
                    f"Failed to fetch template '{key}' from bucket '{self.bucket_name}': {err['Code']} - {err['Message']}",
                    file=sys.stderr,
                )
                sys.exit(1)

            try:
                data = yaml.safe_load(body)
                if not isinstance(data, dict):
                    raise TypeError(
                        f"Expected a YAML mapping, got {type(data).__name__}"
                    )
            except (yaml.YAMLError, TypeError) as e:
                print(
                    f"Failed to parse template '{key}' from bucket '{self.bucket_name}': {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

            for field_keys, dotted_path in required_fields:
                value = self._get_nested(data, *field_keys)
                if not value or not isinstance(value, str) or not value.strip():
                    print(
                        f"Missing or empty required field '{dotted_path}' in '{key}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            parsed_nodes.append((key, data))

        # c. Duplicate node.id check
        node_ids = [self._get_nested(d, "node", "id") for _, d in parsed_nodes]
        seen_ids = set()
        for nid in node_ids:
            if nid in seen_ids:
                print(f"Duplicate external node.id '{nid}'", file=sys.stderr)
                sys.exit(1)
            seen_ids.add(nid)

        for nid in node_ids:
            if nid in self.built_in_node_ids:
                print(
                    f"External node.id '{nid}' collides with a built-in node",
                    file=sys.stderr,
                )
                sys.exit(1)

        # d. Construct ID derivation + collision check
        descriptors_info = []
        seen_construct_ids = set()
        for key, data in parsed_nodes:
            node_id = self._get_nested(data, "node", "id")
            node_type = self._get_nested(data, "node", "type")
            handler = self._get_nested(
                data, "node", "integration", "config", "lambda", "handler"
            )
            lambda_source_path = self._get_nested(
                data, "node", "integration", "config", "lambda", "lambda_source_path"
            )

            parts = handler.split("/")
            construct_id = parts[-1]
            parent_folder = (
                "nodes/" + "/".join(parts[:-1]) if len(parts) > 1 else "nodes"
            )

            if construct_id in seen_construct_ids:
                print(
                    f"Duplicate construct_id '{construct_id}' derived from external nodes",
                    file=sys.stderr,
                )
                sys.exit(1)
            seen_construct_ids.add(construct_id)

            if construct_id in self.built_in_construct_ids:
                print(
                    f"External construct_id '{construct_id}' collides with a built-in construct",
                    file=sys.stderr,
                )
                sys.exit(1)

            descriptors_info.append(
                (
                    node_id,
                    node_type,
                    handler,
                    construct_id,
                    parent_folder,
                    lambda_source_path,
                )
            )

        # e. Lambda source staging
        descriptors = []
        for (
            node_id,
            node_type,
            handler,
            construct_id,
            parent_folder,
            lambda_source_path,
        ) in descriptors_info:
            staging_root = os.path.join(
                tempfile.gettempdir(), "medialake_external_nodes", node_id
            )

            # Comment 3: Clean up any existing staging directory to avoid stale files
            if os.path.exists(staging_root):
                shutil.rmtree(staging_root)
            os.makedirs(staging_root, exist_ok=True)

            # Comment 4: Normalize lambda_source_path to a folder prefix with trailing /
            normalized_prefix = lambda_source_path.rstrip("/") + "/"

            try:
                # Paginate through all objects under lambda_source_path
                all_keys = []
                continuation_token = None
                while True:
                    list_kwargs = {
                        "Bucket": self.bucket_name,
                        "Prefix": normalized_prefix,
                    }
                    if continuation_token:
                        list_kwargs["ContinuationToken"] = continuation_token
                    resp = s3.list_objects_v2(**list_kwargs)
                    all_keys.extend(obj["Key"] for obj in resp.get("Contents", []))
                    if not resp.get("IsTruncated"):
                        break
                    continuation_token = resp["NextContinuationToken"]

                # Comment 4: Guard keys to only those within the normalized folder boundary
                downloadable = [
                    k
                    for k in all_keys
                    if k.startswith(normalized_prefix) and k != normalized_prefix
                ]

                # Comment 2: Fail if no downloadable files found
                if not downloadable:
                    print(
                        f"No source files found for node '{node_id}' at lambda_source_path '{lambda_source_path}'",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                for obj_key in downloadable:
                    relative = obj_key[len(normalized_prefix) :]
                    if not relative:
                        continue
                    local_path = os.path.join(staging_root, relative)
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    file_body = s3.get_object(Bucket=self.bucket_name, Key=obj_key)[
                        "Body"
                    ].read()
                    with open(local_path, "wb") as f:
                        f.write(file_body)
            except Exception as e:
                print(
                    f"Failed to download source for node '{node_id}': {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

            descriptors.append(
                ExternalNodeDescriptor(
                    node_id=node_id,
                    node_type=node_type,
                    handler_path=handler,
                    construct_id=construct_id,
                    parent_folder=parent_folder,
                    local_staging_path=staging_root,
                )
            )

        # f. Return descriptors
        return descriptors
