"""Persistent build cache for the Docker-bundled binary Lambda layers.

The binary layers (ffmpeg, ffprobe, resvg, numpy, OpenEXR, zipmerge) are
built inside a container during ``cdk synth``. Two things made every synth
pay for all of them again:

* The asset source was the repository root (``path="."``) with CDK's default
  ``SOURCE`` hash, so CDK fingerprinted the entire checkout -- including
  ``node_modules``, ``.venv`` and old ``cdk.out`` directories -- once per
  layer before bundling. That alone took minutes per layer.
* CDK only reuses a bundle inside the same output directory, and every deploy
  starts with a fresh one, so each layer was rebuilt from scratch.

``bundled_layer_code`` fixes both. The asset hash is taken from the bundled
output (``AssetHashType.OUTPUT``), which needs no source fingerprint and only
changes -- publishing a new layer version -- when the layer's contents do. The
build itself goes through ``CachedDockerBundling``, which keeps each result in
a cache outside the CDK output directory, keyed by the build recipe (image,
command, user), and reuses it on later synths.

Cached builds expire after ``MEDIALAKE_LAYER_CACHE_MAX_AGE_DAYS`` (default 7),
because several recipes install whatever is current (e.g. ``cargo install
resvg``, unpinned ``numpy``) and should keep picking up new releases.

Environment:
  MEDIALAKE_LAYER_CACHE=off            always build in Docker, as before
  MEDIALAKE_LAYER_CACHE_DIR=<path>     cache location
                                       (default ~/.cache/medialake/lambda-layers)
  MEDIALAKE_LAYER_CACHE_MAX_AGE_DAYS=N rebuild entries older than N days
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional

import jsii
from aws_cdk import AssetHashType, BundlingOptions, DockerImage, ILocalBundling
from aws_cdk import aws_lambda as lambda_

# Bump to invalidate every cached layer build, e.g. if the cache layout changes.
CACHE_SCHEMA_VERSION = 1
DEFAULT_MAX_AGE_DAYS = 7
_COMPLETE_MARKER = ".medialake-layer-cache-complete"


def _log(message: str) -> None:
    print(f"[layer-cache] {message}", file=sys.stderr, flush=True)


def cache_enabled() -> bool:
    return os.environ.get("MEDIALAKE_LAYER_CACHE", "on").strip().lower() not in (
        "0",
        "off",
        "false",
        "no",
    )


def cache_dir() -> Path:
    configured = os.environ.get("MEDIALAKE_LAYER_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "medialake" / "lambda-layers"


def max_age_seconds() -> float:
    raw = os.environ.get("MEDIALAKE_LAYER_CACHE_MAX_AGE_DAYS", "")
    try:
        days = float(raw) if raw else DEFAULT_MAX_AGE_DAYS
    except ValueError:
        days = DEFAULT_MAX_AGE_DAYS
    return days * 86400


def recipe_key(name: str, image: str, command: List[str], user: Optional[str]) -> str:
    """Cache key for a build recipe; any change to it means a fresh build."""
    payload = json.dumps(
        {
            "schema": CACHE_SCHEMA_VERSION,
            "name": name,
            "image": image,
            "command": command,
            "user": user,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@jsii.implements(ILocalBundling)
class CachedDockerBundling:
    """Serve a layer build from the cache, or build it in Docker and cache it.

    Returning False from ``try_bundle`` hands the build back to CDK's own
    Docker bundling (used when the cache is disabled or Docker isn't on the
    PATH, so the failure CDK reports is its usual one).
    """

    def __init__(
        self, name: str, image: str, command: List[str], user: Optional[str] = None
    ):
        self.name = name
        self.image = image
        self.command = list(command)
        self.user = user
        self.key = recipe_key(name, image, self.command, user)

    # -- cache entries --------------------------------------------------

    @property
    def entry(self) -> Path:
        return cache_dir() / self.name / self.key

    def _fresh_entry(self) -> Optional[Path]:
        entry = self.entry
        marker = entry / _COMPLETE_MARKER
        if not marker.is_file():
            return None
        age = time.time() - marker.stat().st_mtime
        if age > max_age_seconds():
            _log(f"{self.name}: cached build is {age / 86400:.1f} days old, rebuilding")
            return None
        return entry

    def _store(self, built: Path) -> Path:
        """Move a finished build into place; concurrent synths may race here."""
        (built / _COMPLETE_MARKER).write_text(f"{self.name} {self.key}\n")
        entry = self.entry
        entry.parent.mkdir(parents=True, exist_ok=True)
        if entry.exists():
            stale = entry.with_name(f"{entry.name}.stale-{uuid.uuid4().hex[:8]}")
            try:
                entry.rename(stale)
                shutil.rmtree(stale, ignore_errors=True)
            except OSError:
                pass
        try:
            built.rename(entry)
        except OSError:
            # Another synth stored the same recipe first; its build is as good.
            shutil.rmtree(built, ignore_errors=True)
        return entry

    # -- building -------------------------------------------------------

    def _docker_build(self, output: Path) -> None:
        # Keep the (empty) input mount beside the output, under the cache
        # directory, which Docker Desktop / OrbStack share like cdk.out.
        with tempfile.TemporaryDirectory(
            prefix="layer-input-", dir=output.parent
        ) as asset_input:
            args = ["docker", "run", "--rm"]
            if self.user:
                args += ["-u", self.user]
            args += [
                "-v",
                f"{asset_input}:/asset-input:delegated",
                "-v",
                f"{output}:/asset-output:delegated",
                "-w",
                "/asset-input",
                self.image,
                *self.command,
            ]
            subprocess.run(args, check=True, stdout=sys.stderr, stderr=sys.stderr)

    def try_bundle(self, output_dir: str, *args, **kwargs) -> bool:
        if not cache_enabled():
            return False

        entry = self._fresh_entry()
        if entry is None:
            if shutil.which("docker") is None:
                return False
            root = cache_dir() / self.name
            root.mkdir(parents=True, exist_ok=True)
            building = Path(tempfile.mkdtemp(prefix=f"{self.key[:12]}-", dir=root))
            os.chmod(building, 0o777)
            _log(f"{self.name}: no cached build, building in {self.image}")
            started = time.time()
            try:
                self._docker_build(building)
            except subprocess.CalledProcessError as error:
                shutil.rmtree(building, ignore_errors=True)
                raise RuntimeError(
                    f"Building the {self.name} layer failed (docker exited "
                    f"{error.returncode}). Set MEDIALAKE_LAYER_CACHE=off to use "
                    "CDK's own Docker bundling instead."
                ) from error
            entry = self._store(building)
            _log(f"{self.name}: built and cached in {time.time() - started:.0f}s")
        else:
            _log(f"{self.name}: using cached build {self.key[:12]}")

        shutil.copytree(
            entry,
            output_dir,
            symlinks=True,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(_COMPLETE_MARKER),
        )
        return True


def bundled_layer_code(
    name: str, image: str, command: List[str], user: Optional[str] = "root"
) -> lambda_.Code:
    """Lambda layer code built in Docker, cached across synths.

    ``name`` identifies the layer in the cache; the recipe itself (image,
    command, user) decides when a cached build is reused.
    """
    return lambda_.Code.from_asset(
        # The build commands never read /asset-input. The repository root is
        # kept as the source so CDK's own Docker fallback runs exactly as it
        # did before; with OUTPUT hashing CDK doesn't fingerprint it.
        path=".",
        asset_hash_type=AssetHashType.OUTPUT,
        bundling=BundlingOptions(
            image=DockerImage.from_registry(image),
            command=command,
            user=user,
            local=CachedDockerBundling(name, image, command, user),
        ),
    )
