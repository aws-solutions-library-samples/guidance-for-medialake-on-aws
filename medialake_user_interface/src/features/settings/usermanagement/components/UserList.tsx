import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    IconButton,
    Chip,
    Tooltip,
    Box,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';

export interface User {
    id: string;
    username: string;
    email: string;
    roles: string[];
    status: 'active' | 'inactive';
    lastLogin?: string;
}

interface UserListProps {
    users: User[];
    onEditUser: (user: User) => void;
    onDeleteUser: (userId: string) => void;
    onToggleUserStatus: (userId: string, newStatus: 'active' | 'inactive') => void;
}

const UserList: React.FC<UserListProps> = ({
    users,
    onEditUser,
    onDeleteUser,
    onToggleUserStatus,
}) => {
    return (
        <TableContainer component={Paper}>
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Username</TableCell>
                        <TableCell>Email</TableCell>
                        <TableCell>Roles</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Last Login</TableCell>
                        <TableCell align="right">Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {users.map((user) => (
                        <TableRow key={user.id}>
                            <TableCell>{user.username}</TableCell>
                            <TableCell>{user.email}</TableCell>
                            <TableCell>
                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    {user.roles.map((role) => (
                                        <Chip
                                            key={role}
                                            label={role}
                                            size="small"
                                            color="primary"
                                            variant="outlined"
                                        />
                                    ))}
                                </Box>
                            </TableCell>
                            <TableCell>
                                <Chip
                                    label={user.status}
                                    color={user.status === 'active' ? 'success' : 'default'}
                                    size="small"
                                />
                            </TableCell>
                            <TableCell>{user.lastLogin || 'Never'}</TableCell>
                            <TableCell align="right">
                                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                                    <Tooltip title="Edit User">
                                        <IconButton
                                            size="small"
                                            onClick={() => onEditUser(user)}
                                            color="primary"
                                        >
                                            <EditIcon />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title={user.status === 'active' ? 'Deactivate User' : 'Activate User'}>
                                        <IconButton
                                            size="small"
                                            onClick={() => onToggleUserStatus(user.id, user.status === 'active' ? 'inactive' : 'active')}
                                            color={user.status === 'active' ? 'success' : 'default'}
                                        >
                                            {user.status === 'active' ? <LockOpenIcon /> : <LockIcon />}
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Delete User">
                                        <IconButton
                                            size="small"
                                            onClick={() => onDeleteUser(user.id)}
                                            color="error"
                                        >
                                            <DeleteIcon />
                                        </IconButton>
                                    </Tooltip>
                                </Box>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

export default UserList;
