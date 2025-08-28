import React, { useState } from "react";
import { Box, Button, Stack } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import GroupIcon from "@mui/icons-material/Group";
import GroupsIcon from "@mui/icons-material/Groups";
import { useTranslation } from "react-i18next";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { PageHeader, PageContent } from "@/components/common/layout";
import UserList from "@/features/settings/usermanagement/components/UserList";
import UserForm from "@/features/settings/usermanagement/components/UserForm";
import CreateGroupModal from "@/features/settings/usermanagement/components/CreateGroupModal";
import ManageGroupsModal from "@/features/settings/usermanagement/components/ManageGroupsModal";
import ApiStatusModal from "@/components/ApiStatusModal";
import {
  useGetUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useDisableUser,
  useEnableUser,
} from "@/api/hooks/useUsers";
import { useGetPermissionSets } from "@/api/hooks/usePermissionSets";
import { useGetGroups } from "@/api/hooks/useGroups";
import { useApiMutationHandler } from "@/shared/hooks/useApiMutationHandler";
import {
  User,
  CreateUserRequest,
  UpdateUserRequest,
} from "@/api/types/api.types";

const UserManagement: React.FC = () => {
  const { t } = useTranslation();
  const [openUserForm, setOpenUserForm] = useState(false);
  const [openCreateGroupModal, setOpenCreateGroupModal] = useState(false);
  const [openManageGroupsModal, setOpenManageGroupsModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | undefined>();
  const [activeFilters, setActiveFilters] = useState<
    { columnId: string; value: string }[]
  >([]);
  const [activeSorting, setActiveSorting] = useState<
    { columnId: string; desc: boolean }[]
  >([]);

  // Feature flags
  const advancedPermissionsEnabled = useFeatureFlag(
    "advanced-permissions-enabled",
    false,
  );

  const { apiStatus, handleMutation, closeApiStatus } = useApiMutationHandler();

  const {
    data: users,
    isLoading: isLoadingUsers,
    error: usersError,
  } = useGetUsers();
  const { data: groups, isLoading: isLoadingGroups } = useGetGroups(true); // Always fetch groups when this component loads
  const { data: permissionSets } = useGetPermissionSets(true); // Enable API call when this page is loaded

  // Debug logs
  console.log("Groups data in UserManagement:", groups);
  const createUserMutation = useCreateUser();
  const updateUserMutation = useUpdateUser();
  const deleteUserMutation = useDeleteUser();
  const disableUserMutation = useDisableUser();
  const enableUserMutation = useEnableUser();

  const handleAddUser = () => {
    setEditingUser(undefined);
    setOpenUserForm(true);
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setOpenUserForm(true);
  };

  const handleSaveUser = async (userData: CreateUserRequest) => {
    const isNewUser = !editingUser;
    console.log("handleSaveUser called with:", userData);
    console.log("isNewUser:", isNewUser);
    setOpenUserForm(false);

    if (isNewUser) {
      console.log("Creating new user with groups:", userData.groups);
      const result = await handleMutation(
        {
          mutation: createUserMutation,
          actionMessages: {
            loading: t("users.apiMessages.creating.loading"),
            success: t("users.apiMessages.creating.success"),
            successMessage: t("users.apiMessages.creating.successMessage"),
            error: t("users.apiMessages.creating.error"),
          },
          onSuccess: (data) => {
            // Check for group assignment issues and show additional notifications
            if (data?.data) {
              const {
                groupsAdded = [],
                groupsFailed = [],
                invalidGroups = [],
              } = data.data;

              // Log the results for debugging
              console.log("User creation completed with group results:", {
                groupsAdded,
                groupsFailed,
                invalidGroups,
              });

              // Show warnings for failed group assignments
              if (groupsFailed.length > 0) {
                console.warn(
                  `Failed to assign user to ${groupsFailed.length} groups:`,
                  groupsFailed,
                );
                // You could show a toast notification here about partial group assignment
              }

              if (invalidGroups.length > 0) {
                console.warn(
                  `${invalidGroups.length} groups were invalid:`,
                  invalidGroups,
                );
                // You could show a toast notification here about invalid groups
              }
            }
          },
        },
        userData,
      );
    } else if (editingUser) {
      const updateData: UpdateUserRequest = {
        username: editingUser.username,
        email: userData.email,
        enabled: userData.enabled,
        groups: userData.groups,
        permissions: userData.permissions,
        given_name: userData.given_name,
        family_name: userData.family_name,
      };
      await handleMutation(
        {
          mutation: updateUserMutation,
          actionMessages: {
            loading: t("users.apiMessages.updating.loading"),
            success: t("users.apiMessages.updating.success"),
            successMessage: t("users.apiMessages.updating.successMessage"),
            error: t("users.apiMessages.updating.error"),
          },
        },
        { username: editingUser.username, updates: updateData },
      );
    }
  };

  const handleDeleteUser = async (username: string) => {
    await handleMutation(
      {
        mutation: deleteUserMutation,
        actionMessages: {
          loading: t("users.apiMessages.deleting.loading"),
          success: t("users.apiMessages.deleting.success"),
          successMessage: t("users.apiMessages.deleting.successMessage"),
          error: t("users.apiMessages.deleting.error"),
        },
      },
      username,
    );
  };

  const handleToggleUserStatus = async (
    username: string,
    newEnabled: boolean,
  ) => {
    const mutation = newEnabled ? enableUserMutation : disableUserMutation;
    const actionKey = newEnabled ? "enabling" : "disabling";

    await handleMutation(
      {
        mutation: mutation,
        actionMessages: {
          loading: t(`users.apiMessages.${actionKey}.loading`),
          success: t(`users.apiMessages.${actionKey}.success`),
          successMessage: t(`users.apiMessages.${actionKey}.successMessage`),
          error: t(`users.apiMessages.${actionKey}.error`),
        },
      },
      username,
    );
  };

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flex: 1,
        width: "100%",
        position: "relative",
        maxWidth: "100%",
        p: 3,
      }}
    >
      <PageHeader
        title={t("users.title")}
        description={t("users.description")}
        action={
          <Stack direction="row" spacing={2}>
            {advancedPermissionsEnabled && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<GroupsIcon />}
                  onClick={() => setOpenManageGroupsModal(true)}
                  sx={{
                    borderRadius: "8px",
                    textTransform: "none",
                    px: 3,
                    height: 40,
                  }}
                >
                  {t("groups.actions.manageGroups")}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<GroupIcon />}
                  onClick={() => setOpenCreateGroupModal(true)}
                  sx={{
                    borderRadius: "8px",
                    textTransform: "none",
                    px: 3,
                    height: 40,
                  }}
                >
                  {t("groups.actions.createGroup")}
                </Button>
              </>
            )}
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleAddUser}
              sx={{
                borderRadius: "8px",
                textTransform: "none",
                px: 3,
                height: 40,
              }}
            >
              {t("users.actions.addUser")}
            </Button>
          </Stack>
        }
      />

      <PageContent isLoading={isLoadingUsers} error={usersError as Error}>
        <UserList
          users={users || []}
          onEditUser={handleEditUser}
          onDeleteUser={handleDeleteUser}
          onToggleUserStatus={handleToggleUserStatus}
          activeFilters={activeFilters}
          activeSorting={activeSorting}
          onRemoveFilter={(columnId) => {
            setActiveFilters((filters) =>
              filters.filter((f) => f.columnId !== columnId),
            );
          }}
          onRemoveSort={(columnId) => {
            setActiveSorting((sorts) =>
              sorts.filter((s) => s.columnId !== columnId),
            );
          }}
          onFilterChange={(columnId, value) => {
            setActiveFilters((filters) => {
              const newFilters = filters.filter((f) => f.columnId !== columnId);
              if (value) {
                newFilters.push({ columnId, value });
              }
              return newFilters;
            });
          }}
          onSortChange={(columnId, desc) => {
            setActiveSorting((sorts) => {
              const newSorts = sorts.filter((s) => s.columnId !== columnId);
              if (desc !== undefined) {
                newSorts.push({ columnId, desc });
              }
              return newSorts;
            });
          }}
        />
      </PageContent>

      <UserForm
        open={openUserForm}
        onClose={() => setOpenUserForm(false)}
        onSave={handleSaveUser}
        user={editingUser}
        availableGroups={
          groups?.map((group) => {
            console.log("Mapping group for UserForm:", group);
            return { id: group.id, name: group.name };
          }) || []
        }
        isLoadingGroups={isLoadingGroups}
      />

      {advancedPermissionsEnabled && (
        <>
          <CreateGroupModal
            open={openCreateGroupModal}
            onClose={() => setOpenCreateGroupModal(false)}
          />

          <ManageGroupsModal
            open={openManageGroupsModal}
            onClose={() => setOpenManageGroupsModal(false)}
          />
        </>
      )}

      <ApiStatusModal
        open={apiStatus.show}
        status={apiStatus.status === "idle" ? "loading" : apiStatus.status}
        action={apiStatus.action}
        message={apiStatus.message}
        onClose={closeApiStatus}
      />
    </Box>
  );
};

export default UserManagement;
