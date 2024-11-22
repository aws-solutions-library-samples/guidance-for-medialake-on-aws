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
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import UserList, { User } from '../../features/settings/usermanagement/components/UserList';
import UserForm from '../../features/settings/usermanagement/components/UserForm';
import RoleManagement, { Role } from '../../features/settings/usermanagement/components/RoleManagement';

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

// Mock data
const mockUsers: User[] = [
    {
        id: '1',
        username: 'admin',
        email: 'admin@example.com',
        roles: ['Admin'],
        status: 'active',
        lastLogin: '2024-01-20 10:30:00',
    },
    {
        id: '2',
        username: 'user1',
        email: 'user1@example.com',
        roles: ['Editor'],
        status: 'active',
        lastLogin: '2024-01-19 15:45:00',
    },
];

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
    const [users, setUsers] = useState<User[]>(mockUsers);
    const [roles, setRoles] = useState<Role[]>(mockRoles);
    const [openUserForm, setOpenUserForm] = useState(false);
    const [editingUser, setEditingUser] = useState<User | undefined>();
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
        open: false,
        message: '',
        severity: 'success',
    });
    const [tabValue, setTabValue] = useState(0);

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

    const handleSaveUser = (userData: Partial<User>) => {
        try {
            if (editingUser) {
                setUsers(users.map(user =>
                    user.id === editingUser.id ? { ...user, ...userData } : user
                ));
                showSnackbar('User updated successfully', 'success');
            } else {
                const newUser: User = {
                    id: String(Date.now()),
                    username: userData.username!,
                    email: userData.email!,
                    roles: userData.roles || [],
                    status: userData.status || 'active',
                    lastLogin: '-',
                };
                setUsers([...users, newUser]);
                showSnackbar('User added successfully', 'success');
            }
            setOpenUserForm(false);
        } catch (error) {
            showSnackbar('Error saving user', 'error');
        }
    };

    const handleDeleteUser = (userId: string) => {
        try {
            setUsers(users.filter(user => user.id !== userId));
            showSnackbar('User deleted successfully', 'success');
        } catch (error) {
            showSnackbar('Error deleting user', 'error');
        }
    };

    const handleToggleUserStatus = (userId: string, newStatus: 'active' | 'inactive') => {
        try {
            setUsers(users.map(user =>
                user.id === userId ? { ...user, status: newStatus } : user
            ));
            showSnackbar(`User ${newStatus === 'active' ? 'activated' : 'deactivated'} successfully`, 'success');
        } catch (error) {
            showSnackbar('Error updating user status', 'error');
        }
    };

    const handleAddRole = (roleData: Omit<Role, 'id'>) => {
        try {
            const newRole: Role = {
                id: String(Date.now()),
                ...roleData,
            };
            setRoles([...roles, newRole]);
            showSnackbar('Role added successfully', 'success');
        } catch (error) {
            showSnackbar('Error adding role', 'error');
        }
    };

    const handleEditRole = (updatedRole: Role) => {
        try {
            setRoles(roles.map(role =>
                role.id === updatedRole.id ? updatedRole : role
            ));
            showSnackbar('Role updated successfully', 'success');
        } catch (error) {
            showSnackbar('Error updating role', 'error');
        }
    };

    const handleDeleteRole = (roleId: string) => {
        try {
            setRoles(roles.filter(role => role.id !== roleId));
            showSnackbar('Role deleted successfully', 'success');
        } catch (error) {
            showSnackbar('Error deleting role', 'error');
        }
    };

    const showSnackbar = (message: string, severity: 'success' | 'error') => {
        setSnackbar({ open: true, message, severity });
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
                        <UserList
                            users={users}
                            onEditUser={handleEditUser}
                            onDeleteUser={handleDeleteUser}
                            onToggleUserStatus={handleToggleUserStatus}
                        />
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
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
            >
                <Alert
                    onClose={() => setSnackbar({ ...snackbar, open: false })}
                    severity={snackbar.severity}
                    sx={{ width: '100%' }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default UserManagement;
