import React, { useState, useMemo } from 'react';
import {
    Box,
    Typography,
    Button,
    Alert,
    Snackbar,
    CircularProgress,
    useTheme,
    alpha,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import UserList from '@/features/settings/usermanagement/components/UserList';
import UserForm from '@/features/settings/usermanagement/components/UserForm';
import { useGetUsers, useCreateUser, useUpdateUser, useDeleteUser, useDisableUser, useEnableUser } from '@/api/hooks/useUsers';
import { User, CreateUserRequest, UpdateUserRequest } from '@/api/types/api.types';

const availableRoles = ['Admin', 'Editor', 'Viewer'];

const UserManagement: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [openUserForm, setOpenUserForm] = useState(false);
    const [editingUser, setEditingUser] = useState<User | undefined>();
    const [error, setError] = useState<string | null>(null);
    const [activeFilters, setActiveFilters] = useState<{ columnId: string; value: string }[]>([]);
    const [activeSorting, setActiveSorting] = useState<{ columnId: string; desc: boolean }[]>([]);

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
                const updateData: UpdateUserRequest = {
                    username: userData.username,
                    email: userData.email,
                    enabled: userData.enabled,
                    groups: userData.groups,
                    roles: userData.roles,
                    given_name: userData.given_name,
                    family_name: userData.family_name,
                };
                const result = await updateUserMutation.mutateAsync({
                    username: editingUser.username,
                    updates: updateData
                });
                setOpenUserForm(false);
                setError(null);
                return result;
            } else {
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
                await enableUserMutation.mutateAsync(username);
            } else {
                await disableUserMutation.mutateAsync(username);
            }
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while updating user status');
            console.error('Error toggling user status:', error);
        }
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flex: 1,
            width: '100%',
            position: 'relative',
            maxWidth: '100%',
            p: 3,
        }}>
            <Box sx={{ mb: 4, flex: 'none', width: '100%' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                        <Typography variant="h4" sx={{
                            fontWeight: 700,
                            mb: 1,
                            color: theme.palette.primary.main,
                        }}>
                            {t('users.title')}
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            {t('users.description')}
                        </Typography>
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAddUser}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            backgroundColor: theme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.dark,
                            },
                        }}
                    >
                        {t('users.actions.addUser')}
                    </Button>
                </Box>
            </Box>

            <Box sx={{
                flex: 1,
                minHeight: 0, // Important for proper flex behavior
                width: '100%',
                overflow: 'hidden', // Let the table container handle scrolling
                position: 'relative',
                maxWidth: '100%',
            }}>
                {isLoadingUsers ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                ) : usersError ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {t('users.errors.loadFailed')}: {usersError instanceof Error ? usersError.message : t('common.unknownError')}
                    </Alert>
                ) : (
                    <UserList
                        users={users || []}
                        onEditUser={handleEditUser}
                        onDeleteUser={handleDeleteUser}
                        onToggleUserStatus={handleToggleUserStatus}
                        activeFilters={activeFilters}
                        activeSorting={activeSorting}
                        onRemoveFilter={(columnId) => {
                            setActiveFilters(filters => filters.filter(f => f.columnId !== columnId));
                        }}
                        onRemoveSort={(columnId) => {
                            setActiveSorting(sorts => sorts.filter(s => s.columnId !== columnId));
                        }}
                        onFilterChange={(columnId, value) => {
                            setActiveFilters(filters => {
                                const newFilters = filters.filter(f => f.columnId !== columnId);
                                if (value) {
                                    newFilters.push({ columnId, value });
                                }
                                return newFilters;
                            });
                        }}
                        onSortChange={(columnId, desc) => {
                            setActiveSorting(sorts => {
                                const newSorts = sorts.filter(s => s.columnId !== columnId);
                                if (desc !== undefined) {
                                    newSorts.push({ columnId, desc });
                                }
                                return newSorts;
                            });
                        }}
                    />
                )}
            </Box>

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
