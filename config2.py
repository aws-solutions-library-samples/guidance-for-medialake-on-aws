from goodconf import GoodConf
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
import os
import click


def generate_small_uid() -> str:
    return str(uuid.uuid4())[:16]


class S3BucketConfig(BaseModel):
    """Configuration for S3 buckets"""
    partner_templates: str = "aws-mne-partner-templates"
    partner_lambda: str = "aws-mne-partner-lambda"
    eventbus_largeitems: str = "aws-mne-eventbus-largitems"


class RegionConfig(BaseModel):
    """Configuration for AWS regions"""
    primary: str = "us-east-1"
    secondary: Optional[str] = None
    enable_ha: bool = False

    @property
    def regions(self) -> List[str]:
        regions = [self.primary]
        if self.enable_ha and self.secondary:
            regions.append(self.secondary)
        return regions


class MediaLakeConfig(GoodConf):
    """Main application configuration"""
    small_uid: str = ""
    region_config: RegionConfig = RegionConfig()
    s3_config: S3BucketConfig = S3BucketConfig()

    class Config:
        default_files = ['cdk_config.json']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.small_uid:
            self.small_uid = generate_small_uid()

    @property
    def regions(self) -> List[str]:
        return self.region_config.regions

    @property
    def access_logs_bucket(self) -> str:
        return f"medialake-access-logs-{self.small_uid}"

    def save_to_file(self, filename='cdk_config.json'):
        """Save current configuration to file"""
        config_dict = {
            'small_uid': self.small_uid,
            'region_config': self.region_config.dict(),
            's3_config': self.s3_config.dict()
        }
        with open(filename, 'w') as f:
            json.dump(config_dict, f, indent=2)

    @classmethod
    def load_from_file(cls, filename='cdk_config.json'):
        """Load configuration from file"""
        try:
            with open(filename, 'r') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            return cls()


def get_config():
    """Get configuration from environment or file"""
    config = MediaLakeConfig()
    
    # Try to load from file first
    try:
        config = MediaLakeConfig.load_from_file()
    except Exception:
        pass

    # Override with environment variables if present
    if os.environ.get('SMALL_UID'):
        config.small_uid = os.environ['SMALL_UID']
    
    if os.environ.get('PRIMARY_REGION'):
        config.region_config.primary = os.environ['PRIMARY_REGION']
    
    if os.environ.get('SECONDARY_REGION'):
        config.region_config.secondary = os.environ['SECONDARY_REGION']
        
    if os.environ.get('ENABLE_HA'):
        config.region_config.enable_ha = os.environ['ENABLE_HA'].lower() == 'true'

    # Save updated config to file
    config.save_to_file()
    
    return config


@click.group()
def cli():
    """MediaLake configuration CLI"""
    pass


@cli.command()
@click.option('--primary-region', help='Primary AWS region')
@click.option('--secondary-region', help='Secondary AWS region for HA')
@click.option('--enable-ha', is_flag=True, help='Enable high availability')
@click.option('--partner-templates', help='Partner templates bucket name')
@click.option('--partner-lambda', help='Partner lambda bucket name')
@click.option('--eventbus-largeitems', help='EventBus large items bucket name')
def configure(primary_region, secondary_region, enable_ha, 
             partner_templates, partner_lambda, eventbus_largeitems):
    """Configure MediaLake settings"""
    config = get_config()
    
    if primary_region:
        config.region_config.primary = primary_region
    if secondary_region:
        config.region_config.secondary = secondary_region
    if enable_ha is not None:
        config.region_config.enable_ha = enable_ha
    if partner_templates:
        config.s3_config.partner_templates = partner_templates
    if partner_lambda:
        config.s3_config.partner_lambda = partner_lambda
    if eventbus_largeitems:
        config.s3_config.eventbus_largeitems = eventbus_largeitems
    
    config.save_to_file()
    click.echo("Configuration updated successfully")


@cli.command()
def show():
    """Show current configuration"""
    config = get_config()
    click.echo(json.dumps({
        'small_uid': config.small_uid,
        'region_config': config.region_config.dict(),
        's3_config': config.s3_config.dict()
    }, indent=2))


if __name__ == '__main__':
    cli()

# Create a global config instance
config = get_config()
