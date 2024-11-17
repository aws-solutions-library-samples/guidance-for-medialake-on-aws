# MediaLake

MediaLake is a serverless media processing platform built on AWS, designed to handle large-scale media ingestion, processing, and delivery workflows. It provides a flexible connector system for various storage sources and customizable processing pipelines.

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

- Node.js (v16.x or later)
- Python 3.12 or later
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Docker (for local development)

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/medialake.git
cd medialake
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

## 🔧 Configuration

1. Configure your AWS credentials:
```bash
aws configure
```

2. Set up configuration variables:
```bash
cdk_config
```

## 🚀 Deployment

1. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

2. Deploy the stack:
```bash
cdk deploy
```

## 🏗️ Project Structure

```
medialake/
├── medialake_constructs/     # CDK construct definitions
│   ├── shared_constructs/    # Shared AWS constructs
│   └── api_gateway_connectors.py
├── lambdas/                  # Lambda functions
│   ├── api/                  # API handlers
│   │   ├── connectors/      # Storage connector handlers
│   │   └── pipelines/       # Pipeline handlers
│   └── pipelines/           # Pipeline processors
├── tests/                    # Test files
├── app.py                    # Main CDK app
├── requirements.txt          # Python dependencies
└── cdk.json                 # CDK configuration
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

## 🧪 Testing

Run the test suite:
```bash
pytest
```

## 📚 API Documentation

The API includes the following main endpoints:

- `POST /connectors/s3`: Create new S3 storage connector
- `GET /connectors`: List all storage connectors
- `DELETE /connectors/{id}`: Remove a storage connector
- `GET /connectors/s3/explorer/{connector_id}`: Browse S3 bucket contents
- `POST /pipelines`: Create processing pipeline
- `DELETE /pipelines/{id}`: Remove pipeline

## 🔒 Security

- AWS Cognito authentication
- KMS encryption for sensitive data
- IAM role-based access control
- CORS-enabled API endpoints

## 👥 Authors

- Robert Raver
- Lior Berezinski
- Karthik Rengasamy

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## 🙏 Acknowledgments

- AWS CDK team for the excellent infrastructure as code framework
- AWS Lambda Powertools for Python
- The open-source community for various tools and libraries used in this project
