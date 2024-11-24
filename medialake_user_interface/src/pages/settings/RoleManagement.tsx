import React, { useState } from 'react';
import {
    Box,
    Typography,
    Paper,
    Alert,
    Snackbar,
    CircularProgress,
} from '@mui/material';
import RoleManagementComponent from '../../features/settings/usermanagement/components/RoleManagement';
import { useGetRoles, useCreateRole, useUpdateRole, useDeleteRole } from '../../api/hooks/useRoles';
import { Role, CreateRoleRequest } from '../../api/types/api.types';

const RoleManagement: React.FC = () => {
    const [error, setError] = useState<string | null>(null);

    const { data: roles, isLoading: isLoadingRoles, error: rolesError } = useGetRoles();
    const createRoleMutation = useCreateRole();
    const updateRoleMutation = useUpdateRole();
    const deleteRoleMutation = useDeleteRole();

    const handleAddRole = async (roleData: Omit<Role, 'id'>) => {
        try {
            const createData: CreateRoleRequest = {
                name: roleData.name,
                description: roleData.description,
                permissions: roleData.permissions
            };
            await createRoleMutation.mutateAsync(createData);
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while creating the role');
            console.error('Error creating role:', error);
        }
    };

    const handleEditRole = async (updatedRole: Role) => {
        try {
            await updateRoleMutation.mutateAsync({
                id: updatedRole.id,
                updates: {
                    name: updatedRole.name,
                    description: updatedRole.description,
                    permissions: updatedRole.permissions
                }
            });
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while updating the role');
            console.error('Error updating role:', error);
        }
    };

    const handleDeleteRole = async (roleId: string) => {
        try {
            await deleteRoleMutation.mutateAsync(roleId);
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while deleting the role');
            console.error('Error deleting role:', error);
        }
    };

    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto', p: 3 }}>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Role Management
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage system roles and their permissions
                </Typography>
            </Box>

            <Paper sx={{ width: '100%', mb: 2 }}>
                <Box sx={{ p: 3 }}>
                    {isLoadingRoles ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                            <CircularProgress />
                        </Box>
                    ) : rolesError ? (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            Failed to load roles: {rolesError instanceof Error ? rolesError.message : 'Unknown error'}
                        </Alert>
                    ) : (
                        <RoleManagementComponent
                            roles={roles || []}
                            onAddRole={handleAddRole}
                            onEditRole={handleEditRole}
                            onDeleteRole={handleDeleteRole}
                        />
                    )}
                </Box>
            </Paper>

            <Snackbar
                open={!!error}
                autoHideDuration={6000}
                onClose={() => setError(null)}
            >
                <Alert
                    severity="error"
                    onClose={() => setError(null)}
                    sx={{ width: '100%' }}
                >
                    {error}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default RoleManagement;
