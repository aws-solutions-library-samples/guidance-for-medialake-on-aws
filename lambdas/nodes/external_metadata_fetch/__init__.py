# External Metadata Fetch Node
# Pipeline node for fetching metadata from external source systems

# This __init__.py provides convenience exports for the package.
# It uses try/except to handle different import contexts:
# - Lambda runtime: modules are at the root level (absolute imports without package prefix)
# - Test/development: modules are accessed via package path (nodes.external_metadata_fetch.*)

try:
    # Try package-qualified imports first (for tests/development)
    pass
except ImportError:
    # Fall back to absolute imports (for Lambda runtime)
    pass
