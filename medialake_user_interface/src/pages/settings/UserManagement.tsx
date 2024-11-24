import React, { useState } from 'react';
import {
    Box,
    Typography,
    Button,
    Paper,
    Alert,
    Snackbar,
    Tab,
    Tabs,
    CircularProgress,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import UserList from '../../features/settings/usermanagement/components/UserList';
import UserForm from '../../features/settings/usermanagement/components/UserForm';
import RoleManagement, { Role } from '../../features/settings/usermanagement/components/RoleManagement';
import { useGetUsers, useCreateUser, useUpdateUser, useDeleteUser } from '../../api/hooks/useUsers';
import { User, CreateUserRequest, UpdateUserRequest } from '../../api/types/api.types';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
    return (
        <Box
            role="tabpanel"
            hidden={value !== index}
            id={`user-management-tabpanel-${index}`}
            aria-labelledby={`user-management-tab-${index}`}
            sx={{ mt: 3 }}
        >
            {value === index && children}
        </Box>
    );
};

const mockRoles: Role[] = [
    {
        id: '1',
        name: 'Admin',
        description: 'Full system access',
        permissions: ['create_user', 'edit_user', 'delete_user', 'manage_roles'],
    },
    {
        id: '2',
        name: 'Editor',
        description: 'Can edit content',
        permissions: ['edit_content', 'view_content'],
    },
];

const availableRoles = ['Admin', 'Editor', 'Viewer'];

const UserManagement: React.FC = () => {
    const [roles] = useState<Role[]>(mockRoles);
    const [openUserForm, setOpenUserForm] = useState(false);
    const [editingUser, setEditingUser] = useState<User | undefined>();
    const [tabValue, setTabValue] = useState(0);
    const [error, setError] = useState<string | null>(null);

    // API Hooks
    const { data: users, isLoading: isLoadingUsers, error: usersError } = useGetUsers();
    const createUserMutation = useCreateUser();
    const updateUserMutation = useUpdateUser();
    const deleteUserMutation = useDeleteUser();

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
    };

    const handleAddUser = () => {
        setEditingUser(undefined);
        setOpenUserForm(true);
    };

    const handleEditUser = (user: User) => {
        setEditingUser(user);
        setOpenUserForm(true);
    };

    const handleSaveUser = async (userData: Partial<User>) => {
        try {
            if (editingUser) {
                // For updating existing user
                const updateData: UpdateUserRequest = {
                    username: userData.username!,
                    email: userData.email,
                    enabled: userData.enabled,
                    groups: userData.groups,
                    roles: userData.roles
                };
                await updateUserMutation.mutateAsync({
                    username: editingUser.username,
                    updates: updateData
                });
            } else {
                // For creating new user
                if (!userData.username || !userData.email) {
                    throw new Error('Missing required fields');
                }
                const createData: CreateUserRequest = {
                    username: userData.username,
                    email: userData.email,
                    enabled: userData.enabled,
                    groups: userData.groups,
                    roles: userData.roles
                };
                await createUserMutation.mutateAsync(createData);
            }
            setOpenUserForm(false);
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while saving the user');
            console.error('Error saving user:', error);
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
            const updateData: UpdateUserRequest = {
                username,
                enabled: newEnabled
            };
            await updateUserMutation.mutateAsync({
                username,
                updates: updateData
            });
            setError(null);
        } catch (error) {
            setError(error instanceof Error ? error.message : 'An error occurred while updating user status');
            console.error('Error toggling user status:', error);
        }
    };

    const handleAddRole = (roleData: Omit<Role, 'id'>) => {
        // TODO: Implement role management API
        console.log('Add role:', roleData);
    };

    const handleEditRole = (updatedRole: Role) => {
        // TODO: Implement role management API
        console.log('Edit role:', updatedRole);
    };

    const handleDeleteRole = (roleId: string) => {
        // TODO: Implement role management API
        console.log('Delete role:', roleId);
    };

    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto', p: 3 }}>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    User Management
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage users and roles in the system
                </Typography>
            </Box>

            <Paper sx={{ width: '100%', mb: 2 }}>
                <Tabs
                    value={tabValue}
                    onChange={handleTabChange}
                    aria-label="user management tabs"
                    sx={{ borderBottom: 1, borderColor: 'divider' }}
                >
                    <Tab label="Users" id="user-management-tab-0" />
                    <Tab label="Roles" id="user-management-tab-1" />
                </Tabs>

                <TabPanel value={tabValue} index={0}>
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
                </TabPanel>

                <TabPanel value={tabValue} index={1}>
                    <Box sx={{ p: 3 }}>
                        <RoleManagement
                            roles={roles}
                            onAddRole={handleAddRole}
                            onEditRole={handleEditRole}
                            onDeleteRole={handleDeleteRole}
                        />
                    </Box>
                </TabPanel>
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
