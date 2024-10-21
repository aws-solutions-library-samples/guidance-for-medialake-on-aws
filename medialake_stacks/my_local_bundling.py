import os
import subprocess
import shutil
import sys
from aws_cdk import ILocalBundling


class MyLocalBundling(ILocalBundling):
    def __init__(self, app_path: str, build_path: str):
        self.app_path = app_path
        self.build_path = build_path

    def try_bundle(self, output_dir: str, image) -> bool:
        try:
            # Define options for subprocess
            options = {"cwd": self.app_path, "env": os.environ.copy(), "shell": True}

            subprocess.check_call("npm install", **options)
            subprocess.check_call("npm run build", **options)

            # Copy the build output to the expected location
            # Check if the 'build' directory exists
            build_path = os.path.join(self.app_path, "build")
            if os.path.exists(build_path):
                dist_path = build_path
                print(f"Using 'build' directory at: {dist_path}")
            else:
                # Check if the 'dist' directory exists
                dist_path = os.path.join(self.app_path, "dist")
                if os.path.exists(dist_path):
                    print(f"Using 'dist' directory at: {dist_path}")
                else:
                    print("Neither 'build' nor 'dist' directory exists.")
                    sys.exit()

            for item in os.listdir(dist_path):
                s = os.path.join(dist_path, item)
                d = os.path.join(output_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            return True
        except subprocess.CalledProcessError as e:
            print(f"Bundling failed: {e}")
            return False
