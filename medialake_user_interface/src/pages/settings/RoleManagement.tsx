import React, { useState } from 'react';
import {
    Box,
    Button,
    Typography,
    CircularProgress,
    Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { Role, CreateRoleRequest } from '../../api/types/api.types';
import { useGetRoles, useCreateRole, useUpdateRole, useDeleteRole } from '../../api/hooks/useRoles';
import RoleList from '../../features/settings/roles/components/RoleList';
import RoleForm from '../../features/settings/roles/components/RoleForm';

const RoleManagement: React.FC = () => {
    const [openRoleForm, setOpenRoleForm] = useState(false);
    const [editingRole, setEditingRole] = useState<Role | undefined>();
    const [error, setError] = useState<string | null>(null);

    // API Hooks
    const { data: roles, isLoading: isLoadingRoles, error: rolesError } = useGetRoles();
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
                    updates: roleData
                });
            } else {
                await createRoleMutation.mutateAsync(roleData);
            }
            setOpenRoleForm(false);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred while saving the role');
        }
    };

    const handleDeleteRole = async (roleId: string) => {
        try {
            await deleteRoleMutation.mutateAsync(roleId);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred while deleting the role');
        }
    };

    if (rolesError) {
        return (
            <Alert severity="error" sx={{ mt: 2 }}>
                {rolesError instanceof Error ? rolesError.message : 'An error occurred while loading roles'}
            </Alert>
        );
    }

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ mb: 3 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Role Management
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Create and manage roles to control user permissions
                </Typography>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAddRole}
                >
                    Add Role
                </Button>
            </Box>

            {isLoadingRoles ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress />
                </Box>
            ) : (
                <RoleList
                    roles={roles || []}
                    onEditRole={handleEditRole}
                    onDeleteRole={handleDeleteRole}
                />
            )}

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
