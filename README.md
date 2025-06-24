# MediaLake

MediaLake is a serverless media processing platform built on AWS, designed to handle small to large-scale media ingestion, processing, management, and workflows. MediaLake provides a flexible connector system for various storage sources and customizable processing pipelines.

## 🚀 Features

- S3 Storage Connectors with multiple integration methods (EventBridge/S3 Events)
- FIFO Queue-based media processing
- Serverless architecture using AWS Lambda and Step Functions
- Customizable media processing pipelines
- Real-time event processing and notifications
- Secure asset management with KMS encryption
- IAM-based access control
- REST API with Cognito authentication

## 📋 Prerequisites

- Node.js (v20.x or later)
- Python 3.12 or later
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Docker (for local development)

## 📋 Account preperation for deployment

```bash
cdk bootstrap

or if you are using a specific profile and/or region

cdk bootstrap --profile <profile> --region <region>
```

- Bootstrap the account for CDK deployment, ensure the right region is selected

## 🧹 MediaLake CloudFormation Stack Deletion

For cleaning up MediaLake deployments, you can use the included stack deletion script:

```bash
./delete_medialake_stacks.py --profile your-aws-profile --region us-east-1
```

The script automatically:
1. Lists all CloudFormation stacks with the "MediaLake" prefix
2. Attempts to delete each stack
3. Waits 60 seconds before checking again
4. Repeats until all stacks are deleted, handling dependencies between stacks

### Prerequisites for Stack Deletion

- Python 3.6+
- Required Python packages:
  - boto3
  - aws-lambda-powertools

Install the requirements:
```bash
pip install boto3 aws-lambda-powertools
chmod +x delete_medialake_stacks.py
```

⚠️ **Warning**: This script will permanently delete all CloudFormation stacks that match the criteria. Use with caution in production environments.

## 🛠️ Installation

1. Clone the repository:

```bash
git clone git@github.com:aws-solutions-library-samples/guidance-for-medialake.git
cd guidance-for-medialake
```

2. Create and activate a virtual environment:

**MacOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**

```bash
python3 -m venv .venv
.venv\Scripts\activate.bat
```

3. Install dependencies:

```bash
pip install -r requirements.txt
npm install
```

if you are developing locally, you can install the requirements for development

```bash
pip install -r requirements-dev.txt
```

## 🔧 Configuration

1. Configure your AWS credentials if you haven't already:

```bash
aws configure
```

2. Create a `config.json` file in the project root:

```bash
touch config.json
```

3. Add the following configuration to `config.json` (modify values as needed):

```json
{
  "environment": "dev",
  "deployment_size": "medium",
  "resource_prefix": "examplePrefix",
  "account_id": "123456789012",
  "global_prefix": "exampleGlobal",
  "resource_application_tag": "exampleTag",
  "api_path": "prod",
  "primary_region": "us-east-1",
  "initial_user": {
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "logging": {
    "retention_days": 90,
    "s3_retention_days": 90,
    "cloudwatch_retention_days": 90,
    "waf_retention_days": 90,
    "api_gateway_retention_days": 90
  },
  "authZ": {
    "identity_providers": [
      {
        "identity_provider_method": "saml",
        "identity_provider_name": "ExampleIDP",
        "identity_provider_metadata_url": "https://example.com/metadata"
      },
      {
        "identity_provider_method": "cognito"
      }
    ]
  },
  "vpc": {
    "use_existing_vpc": false,
    "existing_vpc": {
      "vpc_id": "vpc-xxxxxxxx",
      "vpc_cidr": "10.0.0.0/16",
      "subnet_ids": {
        "public": [
          "subnet-aaaaaaa",
          "subnet-bbbbbbb",
          "subnet-ccccccc"
        ],
        "private": [
          "subnet-ddddddd",
          "subnet-eeeeeee",
          "subnet-fffffff"
        ]
      }
    },
    "new_vpc": {
      "vpc_name": "ExampleVPC",
      "max_azs": 3,
      "cidr": "10.0.0.0/16",
      "enable_dns_hostnames": true,
      "enable_dns_support": true
    },
    "security_groups": {
      "use_existing_groups": false,
      "existing_groups": {
        "media_lake_sg": "sg-xxxxxxxx",
        "opensearch_sg": "sg-yyyyyyyy"
      },
      "new_groups": {
        "media_lake_sg": {
          "name": "ExampleMediaLakeSecurityGroup",
          "description": "Example MediaLake Security Group"
        },
        "opensearch_sg": {
          "name": "ExampleOpenSearchSG",
          "description": "Example OpenSearch Security Group"
        }
      }
    }
  },
  "db": {
    "use_existing_tables": false,
    "pipelines_executions_arn": "arn:aws:dynamodb:us-east-1:123456789012:table/example-pipelines_executions_prod",
    "pipeline_nodes_table_arn": "arn:aws:dynamodb:us-east-1:123456789012:table/example_pipeline_nodes_table",
    "asset_table_arn": "arn:aws:dynamodb:us-east-1:123456789012:table/example-asset-table",
    "assetv2_table_arn": "arn:aws:dynamodb:us-east-1:123456789012:table/example-asset-table-v2"
  },
  "s3": {
    "use_existing_buckets": false,
    "access_logs_bucket": {
      "bucket_name": "example-access-logs-123456789012-us-east-1-prod",
      "bucket_arn": "arn:aws:s3:::example-access-logs-123456789012-us-east-1-prod"
    },
    "asset_bucket": {
      "bucket_name": "example-asset-bucket-123456789012-us-east-1-prod",
      "bucket_arn": "arn:aws:s3:::example-asset-bucket-123456789012-us-east-1-prod",
      "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/example-key-id"
    }
  }
}
```

3. Config changes 

1. environment - Choose between dev or prod, currently use dev
2. resource_prefix - This will be a prefix string added to all AWS resources created, choose what you want to be added
3. account_id - This is the account that you will be deploying to, this should be the same account that the aws credentials or profile is configured for that you will be using.
4. global_prefix - Make this the same as the resource prefix, this is retiring in the near future
5. resource_application_tag - This is the application tag that is used across resources
6. api_path - Don't modify this 
7. 

## 📚 Configuration Parameters

- environment - Environment name, used in resource naming and configuration
- deployment_size - OpenSearch deployment size ("small", "medium", "large")
- account_id - AWS Account ID that will be deployed to
- resource_prefix - Prefix for resources being previsioned
- api_path - API path, used in resource naming and configuration
- primary_region - Primary region for deployment - tested in us-east-1
- initial_user_email - Initial user email, used in Cognito
- logging - Retention for specific logs generated by this solution
- authZ - Identity provider configuration
- vpc - VPC configuration settings

## 🔧 OpenSearch Deployment Sizes

MediaLake now supports three predefined OpenSearch deployment configurations that automatically configure cluster settings based on your use case:

### Small (Development)
**Use Case**: Development and testing environments
**Cost**: Minimal
**Configuration**:
- 1 master node (t3.small.search)
- 1 data node (t3.small.search)
- 10GB storage with 3000 IOPS
- Multi-AZ deployment (2 AZs)
- Off-peak window enabled

```json
{
  "deployment_size": "small"
}
```

### Medium (Staging)
**Use Case**: Staging, UAT, or small production workloads
**Cost**: Moderate
**Configuration**:
- 3 master nodes (t3.medium.search)
- 2 data nodes (t3.medium.search)
- 50GB storage with 3000 IOPS
- Multi-AZ deployment (2 AZs)
- Off-peak window enabled

```json
{
  "deployment_size": "medium"
}
```

### Large (Production)
**Use Case**: Production-scale deployments
**Cost**: High performance
**Configuration**:
- 3 master nodes (r7g.medium.search)
- 2 data nodes (r7g.medium.search)
- 10GB storage with 3000 IOPS
- Multi-AZ deployment (2 AZs)
- Off-peak window enabled

```json
{
  "deployment_size": "large"
}
```

### Custom Configuration Override
You can still override specific OpenSearch settings while using a deployment size preset:

```json
{
  "deployment_size": "large",
  "opensearch_cluster_settings": {
    "data_node_count": 4,
    "data_node_volume_size": 100
  }
}
```

The system will use the "large" preset as a base and override only the specified settings.

### Production Environment Behavior

When `config.environment` is set to "prod" in config.json, it triggers several important retention behaviors:

1. **DynamoDB Tables Retention**
   - Asset tables (both v1 and v2) are retained with `RemovalPolicy.RETAIN` instead of being destroyed on stack deletion
   - This includes all Global Secondary Indexes (GSIs) on these tables
   - For Asset Table v1: Retains AssetIDIndex and FileHashIndex
   - For Asset Table v2: Retains GSI1 through GSI6

2. **S3 Buckets**
   The following S3 buckets are retained in production mode:
   - Access Logs Bucket (`{global_prefix}-access-logs-{account_id}-{region}-{environment}`)
   - Media Assets Bucket (`{global_prefix}-asset-bucket-{account_id}-{region}-{environment}`)
   
   The following buckets are always set to destroy, regardless of environment:
   - DynamoDB Export Bucket (`{global_prefix}-ddb-export-{account_id}-{region}-{environment}`)
   - IAC Assets Bucket (`{global_prefix}-iac-assets-{account_id}-{region}-{environment}`)

3. **Infrastructure Resources**
   - Security Groups are retained when in prod mode
   - VPC and associated networking components are preserved
   - OpenSearch cluster and its configurations are preserved

4. **KMS Keys**
   - KMS keys used for S3 bucket encryption are retained in prod mode (specifically for Access Logs and Media Assets buckets)
   - Key rotation remains enabled for these retained keys
   - When importing existing buckets, their associated KMS keys are also preserved

5. **CloudFormation Outputs**
   In production mode, the system automatically creates CloudFormation outputs for all retained resources, including:
   - VPC ID and CIDR
   - Security Group IDs
   - DynamoDB table names and ARNs (including GSIs)
   - OpenSearch cluster endpoint and ARN
   - S3 bucket names and ARNs (access logs, assets, IAC assets)

6. **Existing Resources**
   - When in prod mode, the system is configured to use existing tables (`should_use_existing_tables` property returns true)
   - This allows for preserving data and maintaining continuity across deployments

### VPC Configuration

The VPC configuration allows you to either use an existing VPC or create a new one. This is controlled by the `use_existing_vpc` flag in the `vpc` section of the configuration.

When using an existing VPC (`use_existing_vpc: true`):
- Provide the `vpc_id`, `vpc_cidr`, and `subnet_ids` in the `existing_vpc` section.
- `subnet_ids` should include both `public` and `private` subnets.

When creating a new VPC (`use_existing_vpc: false`):
- Specify the VPC settings in the `new_vpc` section, including `vpc_name`, `max_azs`, `cidr`, `enable_dns_hostnames`, and `enable_dns_support`.

### OpenSearch Cluster Settings

OpenSearch cluster settings are now automatically configured based on the `deployment_size` parameter. The system provides three predefined configurations (small, medium, large) that are optimized for different use cases.

You can still manually override specific settings by including an `opensearch_cluster_settings` section in your configuration. When provided, these settings will override the preset values while keeping the rest of the preset configuration intact.

Key settings that can be overridden include:
- `master_node_count` and `master_node_instance_type`
- `data_node_count` and `data_node_instance_type`
- `data_node_volume_size`, `data_node_volume_type`, and `data_node_volume_iops`
- `availability_zone_count`
- `multi_az_with_standby_enabled`
- `off_peak_window_enabled` and `off_peak_window_start`
- `domain_endpoint` (for importing existing domains)

### Relationship and Limitations

1. VPC and OpenSearch Integration:
   - The OpenSearch cluster is deployed within the VPC specified in the configuration.
   - The number of private subnets in the VPC must be at least equal to the `availability_zone_count` specified in the OpenSearch cluster settings.

2. Availability Zones:
   - The `availability_zone_count` in OpenSearch settings must not exceed the number of available AZs in the region or the number of private subnets in the VPC.
   - When using an existing VPC, ensure that the private subnets are distributed across different AZs.

3. Subnet Selection:
   - For OpenSearch deployment, the system automatically selects private subnets from the VPC, up to the number specified by `availability_zone_count`.
   - Each selected subnet must be in a different Availability Zone.

4. Validation:
   - The configuration system validates that there are enough private subnets in different AZs to meet the OpenSearch cluster requirements.
   - If using an existing VPC, it checks that the number of private subnets meets or exceeds the `availability_zone_count`.

5. Multi-AZ Deployment:
   - Setting `multi_az_with_standby_enabled` to true requires at least three dedicated master nodes (`master_node_count >= 3`).

6. Instance Types:
   - The configuration validates that the specified instance types for master and data nodes are valid for OpenSearch.

These configurations and their relationships ensure that the OpenSearch cluster is properly deployed within the VPC, with the correct number of nodes distributed across the specified number of Availability Zones.

### SAML Configuration

- identity_provider_method - Method for identity provider (saml or cognito)
- identity_provider_name - Name of identity provider
- identity_provider_metadata_url - Metadata URL for identity provider

## 🚀 Deployment

1. Bootstrap CDK (first time only):

```bash
cdk bootstrap
```

2. OpenSearch - Provisioned

This service is highly sensitive to VPC subnet Availability Zone selection. When using an external VPC, ensure that:

When using instances smaller than r7g.medium.search, you cannot configure dedicated master nodes. Instead, your data nodes must also serve as master nodes.  Due to this we recommend using r7g.medium.search or larger.

1. The number of private subnets is at least equal to the `availability_zone_count` specified in OpenSearch cluster settings.
2. Each subnet is in a distinct Availability Zone.

OpenSearch Provisioned CDK creates service-linked roles, but these may not be immediately recognized during a first-time deployment. You might encounter the following error:

"Invalid request provided: Before you can proceed, you must enable a service-linked role to give Amazon OpenSearch Service permissions to access your VPC."

If this occurs:

1. Wait 5 minutes after your initial deployment attempt.
2. Clear any previous stack in CloudFormation.
3. Attempt the deployment again.

If issues persist, manually create the required roles using the following AWS CLI commands:

```bash
aws iam create-service-linked-role --aws-service-name es.amazonaws.com
aws iam create-service-linked-role --aws-service-name opensearchservice.amazonaws.com
aws iam create-service-linked-role --aws-service-name osis.amazonaws.com
```

3. Deploy the stack:

```bash
cdk deploy --all

or if you are using a specific profile and/or region

cdk deploy --profile <profile> --region <region> --all
```

## 🏗️ Project Structure

```
medialake/
├── medialake_constructs/     # CDK construct definitions
│   ├── shared_constructs/    # Shared AWS constructs
│   └── api_gateway_connectors.py
├── medialake_stacks/         # CDK stack definitions
│   ├── base_infrastructure.py # Base infrastructure stack
│   └── api_gateway.py         # API Gateway stack
├── lambdas/                  # Lambda functions
│   ├── api/                  # API handlers
│   └── pipelines/           # Pipeline processors
├── tests/                    # Test files
├── app.py                    # Main CDK app
├── requirements.txt          # Python dependencies
├── cdk.json                 # CDK configuration
├── config.py                # Configuration interpertor and validator
├── config.json              # Configuration file
├── requirements-dev.txt     # Development dependencies
├── README.md                # This file
└── LICENSE                  # License
```

## 🔑 Key Components

### Storage Connectors

- S3 Connector with EventBridge/S3 event integration
- Automatic resource provisioning (SQS, Lambda, IAM roles)
- Bucket exploration and management capabilities

### Processing Pipelines

- FIFO queue-based media processing
- Step Functions workflow orchestration
- Customizable processing steps
- Event-driven architecture

## ☁️ AWS Services

### Core Services

- **AWS Lambda** - Serverless compute for API handlers and media processing
- **Amazon S3** - Object storage for media assets, metadata, and temporary processing files
- **AWS Step Functions** - Orchestration of media processing workflows
- **Amazon SQS** - queues for ordered media processing and flow control
- **Amazon EventBridge** - Event routing and processing pipeline triggers
- **Amazon API Gateway** - REST API endpoint management
- **Amazon DynamoDB** - Database for asset metadata, storage connector configuration, pipeline configuration, resource state, and pipeline execution history

### Security & Authentication

- **AWS Cognito** - User authentication and authorization
- **AWS KMS** - Encryption key management
- **AWS IAM** - Resource access control and permissions
- **AWS Secrets Manager** - Secret management
- **AWS Amplify** - Frontend development framework
- **AWS WAF** - Web application firewall

### Monitoring & Logging

- **Amazon CloudWatch** - Metrics, logging, and alerting
- **AWS X-Ray** - Distributed tracing and performance monitoring
- **Amazon CloudTrail** - API activity and resource change tracking

### Others

- **MediaConvert** - Video & Audio for transcoding.

### Development & Deployment

- **AWS CDK** - Infrastructure as code
- **AWS CloudFormation** - Resource provisioning

## 📚 API Documentation

The API includes the following main endpoints:

- `POST /connectors/s3`: Create new S3 storage connector
- `GET /connectors`: List all storage connectors
- `DELETE /connectors/{id}`: Remove a storage connector
- `GET /connectors/s3/explorer/{connector_id}`: Browse S3 bucket contents
- `POST /pipelines`: Create processing pipeline
- `DELETE /pipelines/{id}`: Remove pipeline

## 🔒 Security

- AWS Cognito authentication and authorization including support for local username and password as well as federated authentication via SAML.
- KMS encryption for sensitive data
- IAM role-based access control
- CORS-enabled API endpoints

## 🙏 Acknowledgments

- AWS CDK team for the excellent infrastructure as code framework
- AWS Lambda Powertools for Python
- The open-source community for various tools and libraries used in this project

LICENSE

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. You may obtain a copy of the License at

<http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

# MediaLake CloudFormation Stack Deletion Script

This script automates the deletion of all CloudFormation stacks with the prefix "MediaLake" in a specified AWS region. It handles stack dependencies by repeatedly attempting deletion until all stacks are removed.

## Prerequisites

- Python 3.6+
- AWS CLI configured with appropriate credentials
- Required Python packages:
  - boto3
  - aws-lambda-powertools

## Installation

1. Install required packages:

```bash
pip install boto3 aws-lambda-powertools
```

2. Make the script executable:

```bash
chmod +x delete_medialake_stacks.py
```

## Usage

Run the script specifying your AWS profile and region:

```bash
./delete_medialake_stacks.py --profile your-aws-profile --region us-east-1
```

### Parameters

- `--profile`: Required. The AWS profile name to use.
- `--region`: Required. The AWS region where the stacks are deployed.

## How It Works

1. The script lists all CloudFormation stacks with the "MediaLake" prefix in the specified region.
2. It attempts to delete each stack.
3. Then it waits for 60 seconds before checking again.
4. This process repeats until all "MediaLake" stacks are deleted.
5. Since some stacks may depend on others, the script will retry deletion until all stacks are gone.

## Security Warning

This script will permanently delete all CloudFormation stacks that match the criteria. Use with caution in production environments.
