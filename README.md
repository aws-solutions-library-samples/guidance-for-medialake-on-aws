# MediaLake

Brief description of your project and its main purpose.

## 🚀 Features

- Feature 1
- Feature 2
- Feature 3

## 📋 Prerequisites

- Node.js (v14.x or later)
- Python 3.8 or later
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)

## 🛠️ Installation

1. Clone the repository:
```bash
git clone TBD
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
```

## 🔧 Configuration

1. Configure your AWS credentials:
```bash
aws configure
```

2. Update the configuration in `cdk.json` (if necessary):
```json
{
  "app": "python3 app.py"
}
```

## 🚀 Deployment

1. Synthesize the CloudFormation template:
```bash
cdk synth
```

2. Deploy the stack:
```bash
cdk deploy
```

## 🛠️ Useful CDK Commands

| Command | Description |
|---------|-------------|
| `cdk ls` | List all stacks in the app |
| `cdk synth` | Emit synthesized CloudFormation template |
| `cdk deploy` | Deploy stack to AWS |
| `cdk diff` | Compare deployed stack with current state |
| `cdk docs` | Open CDK documentation |

## 🏗️ Project Structure

```
medialake/
├── .venv/                 # Virtual environment
├── app.py                 # Main CDK app file
├── requirements.txt       # Python dependencies
├── cdk.json              # CDK configuration
├── setup.py              # Project setup file
└── medialake_stacks/     # CDK stack definitions
└── medialake_constructs/ # CDK constructs
└── lambdas/               # Lambda functions
```

## 🧪 Testing

```bash
pytest
```


## 📄 License

This project is licensed under the [LICENSE NAME] - see the [LICENSE.md](LICENSE.md) file for details

## 👥 Authors

- Robert Raver
- Lior Berezinski
- Karthik Rengasamy


## 🙏 Acknowledgments

- Hat tip to anyone whose code was used
- Inspiration
- References
