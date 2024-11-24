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
} from '@mui/material';
import { User } from '../../../../api/types/api.types';

interface UserFormProps {
    open: boolean;
    onClose: () => void;
    onSave: (user: Partial<User>) => void;
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
    const [formData, setFormData] = useState<Partial<User>>({
        username: '',
        email: '',
        roles: [],
        enabled: true,
        groups: []
    });

    useEffect(() => {
        if (user) {
            setFormData({
                ...user,
            });
        } else {
            setFormData({
                username: '',
                email: '',
                roles: [],
                enabled: true,
                groups: []
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

    const handleGroupChange = (event: SelectChangeEvent<string[]>) => {
        const {
            target: { value },
        } = event;
        setFormData({
            ...formData,
            groups: typeof value === 'string' ? value.split(',') : value,
        });
    };

    const handleEnabledChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            enabled: event.target.checked,
        });
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSave(formData);
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <form onSubmit={handleSubmit}>
                <DialogTitle>{user ? 'Edit User' : 'Add New User'}</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                        <TextField
                            name="username"
                            label="Username"
                            value={formData.username}
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
                        <FormControl fullWidth>
                            <InputLabel id="roles-label">Roles</InputLabel>
                            <Select
                                labelId="roles-label"
                                multiple
                                value={formData.roles || []}
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
                        <FormControl fullWidth>
                            <InputLabel id="groups-label">Groups</InputLabel>
                            <Select
                                labelId="groups-label"
                                multiple
                                value={formData.groups || []}
                                onChange={handleGroupChange}
                                input={<OutlinedInput label="Groups" />}
                                renderValue={(selected) => (
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {selected.map((value) => (
                                            <Chip key={value} label={value} />
                                        ))}
                                    </Box>
                                )}
                                MenuProps={MenuProps}
                            >
                                {/* TODO: Replace with actual groups from API */}
                                <MenuItem value="default">Default</MenuItem>
                            </Select>
                        </FormControl>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={formData.enabled}
                                    onChange={handleEnabledChange}
                                    name="enabled"
                                />
                            }
                            label="User Enabled"
                        />
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
    );
};

export default UserForm;
