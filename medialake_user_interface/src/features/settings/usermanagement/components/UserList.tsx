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
    useTheme,
    alpha,
    Typography,
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
    const theme = useTheme();

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    return (
        <Paper elevation={0} sx={{
            borderRadius: '12px',
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            overflow: 'hidden',
            backgroundColor: theme.palette.background.paper,
        }}>
            <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)' }}>
                <Table stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Username
                                </Typography>
                            </TableCell>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Email
                                </Typography>
                            </TableCell>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Status
                                </Typography>
                            </TableCell>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Groups
                                </Typography>
                            </TableCell>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Created
                                </Typography>
                            </TableCell>
                            <TableCell sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Modified
                                </Typography>
                            </TableCell>
                            <TableCell align="right" sx={{
                                backgroundColor: theme.palette.background.paper,
                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                py: 2,
                            }}>
                                <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                                    Actions
                                </Typography>
                            </TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {users.map((user) => (
                            <TableRow
                                key={user.username}
                                sx={{
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                    },
                                    transition: 'background-color 0.2s ease',
                                }}
                            >
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Typography variant="body2" sx={{ fontWeight: 500, color: theme.palette.primary.main }}>
                                        {user.username}
                                    </Typography>
                                </TableCell>
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                        {user.email}
                                    </Typography>
                                </TableCell>
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Chip
                                        label={user.enabled ? 'Active' : 'Inactive'}
                                        size="small"
                                        sx={{
                                            backgroundColor: user.enabled
                                                ? alpha(theme.palette.success.main, 0.1)
                                                : alpha(theme.palette.grey[500], 0.1),
                                            color: user.enabled
                                                ? theme.palette.success.main
                                                : theme.palette.grey[500],
                                            fontWeight: 600,
                                            borderRadius: '6px',
                                            height: '24px',
                                            '& .MuiChip-label': {
                                                px: 1.5,
                                            },
                                        }}
                                    />
                                </TableCell>
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                        {user.groups.length > 0 ? (
                                            user.groups.map((group) => (
                                                <Chip
                                                    key={group}
                                                    label={group}
                                                    size="small"
                                                    sx={{
                                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                        color: theme.palette.primary.main,
                                                        fontWeight: 600,
                                                        borderRadius: '6px',
                                                        height: '24px',
                                                        '& .MuiChip-label': {
                                                            px: 1.5,
                                                        },
                                                    }}
                                                />
                                            ))
                                        ) : (
                                            <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                                No groups
                                            </Typography>
                                        )}
                                    </Box>
                                </TableCell>
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                        {formatDate(user.created)}
                                    </Typography>
                                </TableCell>
                                <TableCell sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                        {formatDate(user.modified)}
                                    </Typography>
                                </TableCell>
                                <TableCell align="right" sx={{
                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    py: 2,
                                }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                                        <Tooltip title="Edit User">
                                            <IconButton
                                                size="small"
                                                onClick={() => onEditUser(user)}
                                                sx={{
                                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                    '&:hover': {
                                                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                                    },
                                                }}
                                            >
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={user.enabled ? 'Deactivate User' : 'Activate User'}>
                                            <IconButton
                                                size="small"
                                                onClick={() => onToggleUserStatus(user.username, !user.enabled)}
                                                sx={{
                                                    backgroundColor: user.enabled
                                                        ? alpha(theme.palette.success.main, 0.1)
                                                        : alpha(theme.palette.grey[500], 0.1),
                                                    '&:hover': {
                                                        backgroundColor: user.enabled
                                                            ? alpha(theme.palette.success.main, 0.2)
                                                            : alpha(theme.palette.grey[500], 0.2),
                                                    },
                                                }}
                                            >
                                                {user.enabled ? <LockOpenIcon fontSize="small" /> : <LockIcon fontSize="small" />}
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Delete User">
                                            <IconButton
                                                size="small"
                                                onClick={() => onDeleteUser(user.username)}
                                                sx={{
                                                    backgroundColor: alpha(theme.palette.error.main, 0.1),
                                                    '&:hover': {
                                                        backgroundColor: alpha(theme.palette.error.main, 0.2),
                                                    },
                                                }}
                                            >
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
};

export default UserList;
