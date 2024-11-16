from aws_cdk import Stack
from constructs import Construct
from medialake_config import MediaLakeConfig, Environment
from medialake_constructs.opensearch import MediaLakeOpenSearch

class MediaLakeStack(Stack):
    def __init__(self, scope: Construct, id: str, env: Environment, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Load configuration for the specified environment
        self.config = MediaLakeConfig.load(env)
        
        # Create VPC (simplified for example)
        vpc = ec2.Vpc(self, "MediaLakeVPC")
        
        # Create OpenSearch domain with environment-specific configuration
        self.opensearch = MediaLakeOpenSearch(
            self,
            "MediaLakeOpenSearch",
            config=self.config,
            vpc=vpc
        ) 