import React, { useState } from 'react';
import {
    Box,
    Typography,
    Button,
    Paper,
    Alert,
    Snackbar,
    CircularProgress,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import UserList from '@/features/settings/usermanagement/components/UserList';
import UserForm from '@/features/settings/usermanagement/components/UserForm';
import { useGetUsers, useCreateUser, useUpdateUser, useDeleteUser, useDisableUser, useEnableUser } from '@/api/hooks/useUsers';
import { User, CreateUserRequest, UpdateUserRequest } from '@/api/types/api.types';

const availableRoles = ['Admin', 'Editor', 'Viewer'];

const UserManagement: React.FC = () => {
    const [openUserForm, setOpenUserForm] = useState(false);
    const [editingUser, setEditingUser] = useState<User | undefined>();
    const [error, setError] = useState<string | null>(null);

    // API Hooks
    const { data: users, isLoading: isLoadingUsers, error: usersError } = useGetUsers();
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
        try {
            if (editingUser) {
                // For updating existing user
                const updateData: UpdateUserRequest = {
                    username: userData.username,
                    email: userData.email,
                    enabled: userData.enabled,
                    groups: userData.groups,
                    roles: userData.roles
                };
                const result = await updateUserMutation.mutateAsync({
                    username: editingUser.username,
                    updates: updateData
                });
                setOpenUserForm(false);
                setError(null);
                return result;
            } else {
                // For creating new user
                const result = await createUserMutation.mutateAsync(userData);
                if (result.status === 201) {
                    setOpenUserForm(false);
                    setError(null);
                }
                return result;
            }
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while saving the user');
            console.error('Error saving user:', error);
            throw error;
        }
    };

    const handleDeleteUser = async (username: string) => {
        try {
            await deleteUserMutation.mutateAsync(username);
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while deleting the user');
            console.error('Error deleting user:', error);
        }
    };

    const handleToggleUserStatus = async (username: string, newEnabled: boolean) => {
        try {
            if (newEnabled) {
                // Enable user
                await enableUserMutation.mutateAsync(username);
            } else {
                // Disable user
                await disableUserMutation.mutateAsync(username);
            }
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while updating user status');
            console.error('Error toggling user status:', error);
        }
    };

    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto', p: 3 }}>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    User Management
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage system users and their access
                </Typography>
            </Box>

            <Paper sx={{ width: '100%', mb: 2 }}>
                <Box sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                        <Button
                            variant="contained"
                            color="primary"
                            startIcon={<AddIcon />}
                            onClick={handleAddUser}
                        >
                            Add User
                        </Button>
                    </Box>
                    {isLoadingUsers ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                            <CircularProgress />
                        </Box>
                    ) : usersError ? (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            Failed to load users: {usersError instanceof Error ? usersError.message : 'Unknown error'}
                        </Alert>
                    ) : (
                        <UserList
                            users={users || []}
                            onEditUser={handleEditUser}
                            onDeleteUser={handleDeleteUser}
                            onToggleUserStatus={handleToggleUserStatus}
                        />
                    )}
                </Box>
            </Paper>

            <UserForm
                open={openUserForm}
                onClose={() => setOpenUserForm(false)}
                onSave={handleSaveUser}
                user={editingUser}
                availableRoles={availableRoles}
            />

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

export default UserManagement;
