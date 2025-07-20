import React, { useState } from "react";
import { Box, Button } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useTranslation } from "react-i18next";
import { PageHeader, PageContent } from "@/components/common/layout";
import { Role, CreateRoleRequest } from "../../api/types/api.types";
import {
  useGetRoles,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
} from "../../api/hooks/useRoles";
import RoleList from "../../features/settings/roles/components/RoleList";
import RoleForm from "../../features/settings/roles/components/RoleForm";

const RoleManagement: React.FC = () => {
  const { t } = useTranslation();
  const [openRoleForm, setOpenRoleForm] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | undefined>();
  const [error, setError] = useState<string | null>(null);

  // API Hooks
  const {
    data: roles,
    isLoading: isLoadingRoles,
    error: rolesError,
  } = useGetRoles();
  const createRoleMutation = useCreateRole();
  const updateRoleMutation = useUpdateRole();
  const deleteRoleMutation = useDeleteRole();

  const handleAddRole = () => {
    setEditingRole(undefined);
    setOpenRoleForm(true);
  };

  const handleEditRole = (role: Role) => {
    setEditingRole(role);
    setOpenRoleForm(true);
  };

  const handleSaveRole = async (roleData: CreateRoleRequest) => {
    try {
      if (editingRole) {
        await updateRoleMutation.mutateAsync({
          id: editingRole.id,
          updates: roleData,
        });
      } else {
        await createRoleMutation.mutateAsync(roleData);
      }
      setOpenRoleForm(false);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred while saving the role",
      );
    }
  };

  const handleDeleteRole = async (roleId: string) => {
    try {
      await deleteRoleMutation.mutateAsync(roleId);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred while deleting the role",
      );
    }
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
        title={t("roles.title")}
        description={t("roles.description")}
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddRole}
            sx={{
              borderRadius: "8px",
              textTransform: "none",
              px: 3,
              height: 40,
            }}
          >
            {t("roles.actions.addRole")}
          </Button>
        }
      />

      <PageContent isLoading={isLoadingRoles} error={rolesError as Error}>
        <RoleList
          roles={roles || []}
          onEditRole={handleEditRole}
          onDeleteRole={handleDeleteRole}
        />
      </PageContent>

      <RoleForm
        open={openRoleForm}
        onClose={() => setOpenRoleForm(false)}
        onSave={handleSaveRole}
        role={editingRole}
      />
    </Box>
  );
};

export default RoleManagement;
