import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    Box,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Chip,
    OutlinedInput,
    SelectChangeEvent,
    Switch,
    FormControlLabel,
    Snackbar,
    Alert,
} from '@mui/material';
import { v4 as uuidv4 } from 'uuid';
import { User, CreateUserRequest } from '../../../../api/types/api.types';

interface UserFormProps {
    open: boolean;
    onClose: () => void;
    onSave: (user: CreateUserRequest) => Promise<any>;
    user?: User;
    availableRoles: string[];
}

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
    PaperProps: {
        style: {
            maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
            width: 250,
        },
    },
};

const UserForm: React.FC<UserFormProps> = ({
    open,
    onClose,
    onSave,
    user,
    availableRoles,
}) => {
    const [formData, setFormData] = useState({
        given_name: '',
        family_name: '',
        email: '',
        email_verified: '',
        roles: [] as string[],
    });

    const [snackbar, setSnackbar] = useState<{
        open: boolean;
        message: string;
        severity: 'success' | 'error';
    }>({
        open: false,
        message: '',
        severity: 'success',
    });

    useEffect(() => {
        if (user) {
            setFormData({
                given_name: user.given_name || '',
                family_name: user.family_name || '',
                email: user.email || '',
                email_verified: user.email_verified || '',
                roles: user.roles || [],
            });
        } else {
            setFormData({
                given_name: '',
                family_name: '',
                email: '',
                email_verified: '',
                roles: [],
            });
        }
    }, [user]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleRoleChange = (event: SelectChangeEvent<string[]>) => {
        const {
            target: { value },
        } = event;
        setFormData({
            ...formData,
            roles: typeof value === 'string' ? value.split(',') : value,
        });
    };

    const handleEmailVerifiedChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            email_verified: event.target.checked ? 'true' : 'false',
        });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            // Create the request object with the email as username
            const requestData: CreateUserRequest = {
                username: formData.email,
                email: formData.email,
                roles: formData.roles,
            };

            console.log('Submitting user data:', requestData);
            const response = await onSave(requestData);
            console.log('Response from onSave:', response);

            // Check if response exists and has the correct status
            if (response?.status === 201) {
                setSnackbar({
                    open: true,
                    message: response.message || 'User Created Successfully',
                    severity: 'success',
                });
                onClose();
            } else {
                console.log('Status check failed:', response?.status);
                throw new Error(response?.message || 'Unknown error occurred');
            }
        } catch (error) {
            console.error('Error in handleSubmit:', error);
            setSnackbar({
                open: true,
                message: `Unable to create user, error message: ${error instanceof Error ? error.message : 'Unknown error'}`,
                severity: 'error',
            });
        }
    };

    const handleSnackbarClose = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    return (
        <>
            <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
                <form onSubmit={handleSubmit}>
                    <DialogTitle>{user ? 'Edit User' : 'Add New User'}</DialogTitle>
                    <DialogContent>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                            <TextField
                                name="given_name"
                                label="First Name"
                                value={formData.given_name}
                                onChange={handleChange}
                                required
                                fullWidth
                            />
                            <TextField
                                name="family_name"
                                label="Last Name"
                                value={formData.family_name}
                                onChange={handleChange}
                                required
                                fullWidth
                            />
                            <TextField
                                name="email"
                                label="Email"
                                type="email"
                                value={formData.email}
                                onChange={handleChange}
                                required
                                fullWidth
                            />
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={formData.email_verified === 'true'}
                                        onChange={handleEmailVerifiedChange}
                                        name="email_verified"
                                    />
                                }
                                label="Email Verified"
                            />
                            <FormControl fullWidth>
                                <InputLabel id="roles-label">Roles</InputLabel>
                                <Select
                                    labelId="roles-label"
                                    multiple
                                    value={formData.roles}
                                    onChange={handleRoleChange}
                                    input={<OutlinedInput label="Roles" />}
                                    renderValue={(selected) => (
                                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                            {selected.map((value) => (
                                                <Chip key={value} label={value} />
                                            ))}
                                        </Box>
                                    )}
                                    MenuProps={MenuProps}
                                >
                                    {availableRoles.map((role) => (
                                        <MenuItem key={role} value={role}>
                                            {role}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={onClose}>Cancel</Button>
                        <Button type="submit" variant="contained" color="primary">
                            {user ? 'Save Changes' : 'Add User'}
                        </Button>
                    </DialogActions>
                </form>
            </Dialog>
            <Snackbar
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={handleSnackbarClose}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert onClose={handleSnackbarClose} severity={snackbar.severity}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </>
    );
};

export default UserForm;
