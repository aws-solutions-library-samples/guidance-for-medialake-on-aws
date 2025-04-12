import React, { useState } from 'react';
import { Box, Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import { PageHeader, PageContent } from '@/components/common/layout';
import UserList from '@/features/settings/usermanagement/components/UserList';
import UserForm from '@/features/settings/usermanagement/components/UserForm';
import ApiStatusModal from '@/components/ApiStatusModal';
import { useGetUsers, useCreateUser, useUpdateUser, useDeleteUser, useDisableUser, useEnableUser } from '@/api/hooks/useUsers';
import { User, CreateUserRequest, UpdateUserRequest } from '@/api/types/api.types';

const availableRoles = ['Admin', 'Editor', 'Viewer'];

const UserManagement: React.FC = () => {
    const { t } = useTranslation();
    const [openUserForm, setOpenUserForm] = useState(false);
    const [editingUser, setEditingUser] = useState<User | undefined>();
    const [error, setError] = useState<string | null>(null);
    const [activeFilters, setActiveFilters] = useState<{ columnId: string; value: string }[]>([]);
    const [activeSorting, setActiveSorting] = useState<{ columnId: string; desc: boolean }[]>([]);
    const [apiStatus, setApiStatus] = useState<{
        show: boolean;
        status: 'loading' | 'success' | 'error';
        action: string;
        message?: string;
    }>({
        show: false,
        status: 'loading',
        action: '',
    });

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
        console.log('Edit user data:', user);
        const normalizedUser = {
            ...user,
            given_name: user.given_name || '',
        };
        setEditingUser(normalizedUser);
        setOpenUserForm(true);
    };

    const handleSaveUser = async (userData: CreateUserRequest) => {
        const isNewUser = !editingUser;
        const action = isNewUser ? 'Creating user...' : 'Updating user...';

        setApiStatus({
            show: true,
            status: 'loading',
            action,
        });
        setOpenUserForm(false);

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

                setApiStatus({
                    show: true,
                    status: 'success',
                    action: 'User Updated',
                    message: 'User has been successfully updated',
                });

                return result;
            } else {
                const result = await createUserMutation.mutateAsync(userData);

                setApiStatus({
                    show: true,
                    status: 'success',
                    action: 'User Created',
                    message: 'New user has been successfully created',
                });

                return result;
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'An error occurred while saving the user';
            setApiStatus({
                show: true,
                status: 'error',
                action: isNewUser ? 'User Creation Failed' : 'User Update Failed',
                message: errorMessage,
            });
            console.error('Error saving user:', error);
            throw error;
        }
    };

    const handleDeleteUser = async (username: string) => {
        setApiStatus({
            show: true,
            status: 'loading',
            action: 'Deleting user...',
        });

        try {
            await deleteUserMutation.mutateAsync(username);
            setApiStatus({
                show: true,
                status: 'success',
                action: 'User Deleted',
                message: 'User has been successfully deleted',
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'An error occurred while deleting the user';
            setApiStatus({
                show: true,
                status: 'error',
                action: 'User Deletion Failed',
                message: errorMessage,
            });
            console.error('Error deleting user:', error);
        }
    };

    const handleToggleUserStatus = async (username: string, newEnabled: boolean) => {
        const action = newEnabled ? 'Enabling user...' : 'Disabling user...';
        setApiStatus({
            show: true,
            status: 'loading',
            action,
        });

        try {
            if (newEnabled) {
                await enableUserMutation.mutateAsync(username);
            } else {
                await disableUserMutation.mutateAsync(username);
            }
            setApiStatus({
                show: true,
                status: 'success',
                action: newEnabled ? 'User Enabled' : 'User Disabled',
                message: `User has been successfully ${newEnabled ? 'enabled' : 'disabled'}`,
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'An error occurred while updating user status';
            setApiStatus({
                show: true,
                status: 'error',
                action: 'Status Update Failed',
                message: errorMessage,
            });
            console.error('Error toggling user status:', error);
        }
    };

    const handleCloseApiStatus = () => {
        setApiStatus(prev => ({ ...prev, show: false }));
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
            <PageHeader
                title={t('users.title')}
                description={t('users.description')}
                action={
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAddUser}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            height: 40
                        }}
                    >
                        {t('users.actions.addUser')}
                    </Button>
                }
            />

            <PageContent
                isLoading={isLoadingUsers}
                error={usersError as Error}
            >
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
            </PageContent>

            <UserForm
                open={openUserForm}
                onClose={() => setOpenUserForm(false)}
                onSave={handleSaveUser}
                user={editingUser}
                availableRoles={availableRoles}
            />

            <ApiStatusModal
                open={apiStatus.show}
                status={apiStatus.status}
                action={apiStatus.action}
                message={apiStatus.message}
                onClose={handleCloseApiStatus}
            />
        </Box>
    );
};

export default UserManagement;
