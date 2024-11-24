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
import { User as ApiUser } from '../../../../api/types/api.types';

export type User = ApiUser;

interface UserListProps {
    users: User[];
    onEditUser: (user: User) => void;
    onDeleteUser: (username: string) => void;
    onToggleUserStatus: (username: string, newStatus: boolean) => void;
}

const UserList: React.FC<UserListProps> = ({
    users,
    onEditUser,
    onDeleteUser,
    onToggleUserStatus,
}) => {
    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString();
    };

    return (
        <TableContainer component={Paper}>
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Username</TableCell>
                        <TableCell>Email</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Groups</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Modified</TableCell>
                        <TableCell align="right">Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {users.map((user) => (
                        <TableRow key={user.username}>
                            <TableCell>{user.username}</TableCell>
                            <TableCell>{user.email}</TableCell>
                            <TableCell>
                                <Chip
                                    label={user.enabled ? 'Active' : 'Inactive'}
                                    color={user.enabled ? 'success' : 'default'}
                                    size="small"
                                />
                            </TableCell>
                            <TableCell>
                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    {user.groups.length > 0 ? (
                                        user.groups.map((group) => (
                                            <Chip
                                                key={group}
                                                label={group}
                                                size="small"
                                                color="primary"
                                                variant="outlined"
                                            />
                                        ))
                                    ) : (
                                        <span>No groups</span>
                                    )}
                                </Box>
                            </TableCell>
                            <TableCell>{formatDate(user.created)}</TableCell>
                            <TableCell>{formatDate(user.modified)}</TableCell>
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
                                    <Tooltip title={user.enabled ? 'Deactivate User' : 'Activate User'}>
                                        <IconButton
                                            size="small"
                                            onClick={() => onToggleUserStatus(user.username, !user.enabled)}
                                            color={user.enabled ? 'success' : 'default'}
                                        >
                                            {user.enabled ? <LockOpenIcon /> : <LockIcon />}
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Delete User">
                                        <IconButton
                                            size="small"
                                            onClick={() => onDeleteUser(user.username)}
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
