"""Unit tests for auth seeder Lambda.

Tests verify that the default permission sets include the correct permissions,
particularly the defaultDashboard:edit permission for Super Administrators.

Validates: Requirements 2.1, 2.2
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock dependencies before importing the auth_seeder module
sys.modules["crhelper"] = MagicMock()
sys.modules["boto3"] = MagicMock()
sys.modules["aws_lambda_powertools"] = MagicMock()

# Add the auth_seeder to the path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent / "lambdas" / "auth" / "auth_seeder"
    ),
)

# Now import the module after mocking
from index import DEFAULT_GROUPS, DEFAULT_PERMISSION_SETS


class TestSuperAdministratorPermissionSet:
    """Tests for Super Administrator permission set configuration."""

    def test_super_administrator_has_default_dashboard_edit_permission(self):
        """
        Test that Super Administrator permission set includes defaultDashboard:edit.

        **Validates: Requirements 2.1, 2.2**

        Requirement 2.1: WHEN the Auth_Seeder runs during deployment,
        THE System SHALL assign the `defaultDashboard:edit` permission to the
        Super_Administrators_Group

        Requirement 2.2: THE Super_Administrators_Group permission set
        SHALL include `defaultDashboard:edit` with effect "Allow"
        """
        # Find the superAdministrator permission set
        super_admin_ps = None
        for ps in DEFAULT_PERMISSION_SETS:
            if ps["id"] == "superAdministrator":
                super_admin_ps = ps
                break

        assert (
            super_admin_ps is not None
        ), "Super Administrator permission set not found"

        # Verify defaultDashboard permissions exist
        permissions = super_admin_ps.get("permissions", {})
        assert (
            "defaultDashboard" in permissions
        ), "defaultDashboard permissions not found in Super Administrator permission set"

        # Verify defaultDashboard:edit is True (Allow effect)
        default_dashboard_perms = permissions["defaultDashboard"]
        assert (
            "edit" in default_dashboard_perms
        ), "edit permission not found in defaultDashboard permissions"
        assert (
            default_dashboard_perms["edit"] is True
        ), "defaultDashboard:edit should be True (Allow effect)"

    def test_super_administrator_permission_set_is_system(self):
        """Test that Super Administrator permission set is marked as a system permission set."""
        super_admin_ps = None
        for ps in DEFAULT_PERMISSION_SETS:
            if ps["id"] == "superAdministrator":
                super_admin_ps = ps
                break

        assert (
            super_admin_ps is not None
        ), "Super Administrator permission set not found"
        assert (
            super_admin_ps.get("isSystem") is True
        ), "Super Administrator should be a system permission set"

    def test_super_administrator_has_required_base_permissions(self):
        """Test that Super Administrator has all required base permissions."""
        super_admin_ps = None
        for ps in DEFAULT_PERMISSION_SETS:
            if ps["id"] == "superAdministrator":
                super_admin_ps = ps
                break

        assert (
            super_admin_ps is not None
        ), "Super Administrator permission set not found"

        permissions = super_admin_ps.get("permissions", {})

        # Verify essential permission categories exist
        assert "assets" in permissions, "assets permissions should exist"
        assert "settings" in permissions, "settings permissions should exist"
        assert (
            "defaultDashboard" in permissions
        ), "defaultDashboard permissions should exist"


class TestEditorPermissionSet:
    """Tests for Editor permission set configuration."""

    def test_editor_does_not_have_default_dashboard_edit_permission(self):
        """
        Test that Editor permission set does NOT include defaultDashboard:edit.

        Only Super Administrators should have dashboard admin permissions.
        """
        editor_ps = None
        for ps in DEFAULT_PERMISSION_SETS:
            if ps["id"] == "editor":
                editor_ps = ps
                break

        assert editor_ps is not None, "Editor permission set not found"

        permissions = editor_ps.get("permissions", {})

        # Editor should not have defaultDashboard permissions at all, or if they do,
        # they should not have edit permission
        if "defaultDashboard" in permissions:
            default_dashboard_perms = permissions["defaultDashboard"]
            assert (
                default_dashboard_perms.get("edit") is not True
            ), "Editor should not have defaultDashboard:edit permission"


class TestViewerPermissionSet:
    """Tests for Viewer permission set configuration."""

    def test_viewer_does_not_have_default_dashboard_edit_permission(self):
        """
        Test that Viewer permission set does NOT include defaultDashboard:edit.

        Only Super Administrators should have dashboard admin permissions.
        """
        viewer_ps = None
        for ps in DEFAULT_PERMISSION_SETS:
            if ps["id"] == "viewer":
                viewer_ps = ps
                break

        assert viewer_ps is not None, "Viewer permission set not found"

        permissions = viewer_ps.get("permissions", {})

        # Viewer should not have defaultDashboard permissions at all, or if they do,
        # they should not have edit permission
        if "defaultDashboard" in permissions:
            default_dashboard_perms = permissions["defaultDashboard"]
            assert (
                default_dashboard_perms.get("edit") is not True
            ), "Viewer should not have defaultDashboard:edit permission"


class TestDefaultGroups:
    """Tests for default groups configuration."""

    def test_super_administrators_group_has_super_administrator_permission_set(self):
        """
        Test that Super Administrators group is assigned the superAdministrator permission set.

        **Validates: Requirement 2.1**

        This ensures that when users are added to the Super Administrators group,
        they will inherit the defaultDashboard:edit permission.
        """
        super_admin_group = None
        for group in DEFAULT_GROUPS:
            if group["id"] == "superAdministrators":
                super_admin_group = group
                break

        assert super_admin_group is not None, "Super Administrators group not found"

        assigned_ps = super_admin_group.get("assignedPermissionSets", [])
        assert (
            "superAdministrator" in assigned_ps
        ), "Super Administrators group should have superAdministrator permission set assigned"
