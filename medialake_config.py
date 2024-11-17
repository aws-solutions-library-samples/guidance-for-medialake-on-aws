import json
from pathlib import Path
from typing import Optional
import hashlib
from config.base_config import BaseConfig
from config.environment_config import EnvironmentConfig, Environment
from config.ha_config import HAConfig
from pydantic import BaseModel

class MediaLakeConfig(BaseModel):
    """Main configuration class that combines all config types"""
    
    base: BaseConfig
    environment: EnvironmentConfig
    ha: Optional[HAConfig] = None
    
    @classmethod
    def load(cls, env: Environment, config_dir: str = "config") -> "MediaLakeConfig":
        """Load configuration for specified environment"""
        config_path = Path(config_dir)
        
        # Load environment-specific config file
        env_file = config_path / f"{env.value}.json"
        if not env_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {env_file}")
        
        with open(env_file) as f:
            env_config = json.load(f)
            
        # Create base configuration
        base_config = BaseConfig()
        
        # Create environment configuration
        environment_config = EnvironmentConfig(
            environment=env,
            **env_config
        )
        
        # Load HA configuration if enabled
        ha_config = None
        if environment_config.enable_ha:
            ha_file = config_path / "ha.json"
            if ha_file.exists():
                with open(ha_file) as f:
                    ha_config = HAConfig(**json.load(f))
        
        return cls(
            base=base_config,
            environment=environment_config,
            ha=ha_config
        )
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """Generate consistent resource names"""
        parts = [
            self.base.project_name,
            self.environment.environment.value,
            resource_type,
            suffix
        ]
        name = "-".join(filter(None, parts))
        
        if len(name) > self.base.max_name_length:
            # Generate a shorter unique identifier if name is too long
            hash_part = hashlib.md5(name.encode()).hexdigest()[:self.base.unique_id_length]
            name = f"{self.base.project_name}-{self.environment.environment.value}-{hash_part}"
        
        return name
