"""
Pytest configuration for pipeline tests.
"""


def pytest_addoption(parser):
    """Add custom pytest options for pipeline tests."""
    try:
        parser.addoption(
            "--update-snapshots",
            action="store_true",
            default=False,
            help="Update snapshot files instead of comparing against them",
        )
    except ValueError:
        # Option already added
        pass
