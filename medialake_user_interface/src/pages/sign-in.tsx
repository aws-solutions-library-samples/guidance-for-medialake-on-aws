import React, { useState, FormEvent } from 'react';
import {
    Container,
    Box,
    Typography,
    TextField,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Paper
} from '@mui/material';
import { CognitoUser } from 'amazon-cognito-identity-js';

interface SignInPageProps {
    onSignIn: (email: string, password: string) => Promise<{ success: boolean, user?: CognitoUser, type?: string }>;
    onChangePassword?: (user: CognitoUser, newPassword: string, userAttributes: any) => Promise<any>;
    loginError: string;
}

const SignInPage: React.FC<SignInPageProps> = ({ onSignIn, onChangePassword, loginError }) => {
    const [email, setEmail] = useState<string>('');
    const [password, setPassword] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);

    const [showChangePasswordModal, setShowChangePasswordModal] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [changePasswordError, setChangePasswordError] = useState('');
    const [cognitoUser, setCognitoUser] = useState<CognitoUser | null>(null);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setLoading(true);
        try {
            const result = await onSignIn(email, password);
            if (result.success) {
                // Handle successful sign-in
                console.log('Sign-in successful');
            } else if (result.user) {
                // Handle the case where sign-in failed but we have a user object
                console.log('Sign-in failed, but we have a user object:', result.user);
                setCognitoUser(result.user);
                console.log(result.type)
                // Check if we need to show the change password modal
                if (result.type === 'NEW_PASSWORD_REQUIRED') {
                    setShowChangePasswordModal(true);
                }
            } else {
                // Handle sign-in failure without a user object
                console.error('Sign-in failed');
            }
        } catch (error) {
            console.error('Login error:', error);
        } finally {
            setLoading(false);
        }
    };


    const handleChangePassword = async () => {
        if (onChangePassword && cognitoUser && newPassword) {
            try {
                await onChangePassword(cognitoUser, newPassword, {});
                setShowChangePasswordModal(false);
                setChangePasswordError('');
                // Optionally, you can sign in the user automatically after password change
                // or redirect them to the login page
            } catch (error) {
                setChangePasswordError('Failed to change password. Please try again.');
            }
        }
    };

    return (
        <Container maxWidth="sm">
            <Box
                sx={{
                    marginTop: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center'
                }}
            >
                <Paper elevation={3} sx={{ p: 4, width: '100%' }}>
                    <Typography component="h1" variant="h4" align="center" gutterBottom>
                        MediaLake
                    </Typography>
                    <Typography component="h2" variant="h6" align="center" gutterBottom>
                        DataLake for Media
                    </Typography>

                    <form onSubmit={handleSubmit}>
                        <Box sx={{ mt: 2 }}>
                            {loginError && (
                                <Typography color="error" variant="body2" sx={{ mb: 2 }}>
                                    {loginError}
                                </Typography>
                            )}

                            <TextField
                                margin="normal"
                                required
                                fullWidth
                                id="email"
                                label="Email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                disabled={loading}
                            />

                            <TextField
                                margin="normal"
                                required
                                fullWidth
                                id="password"
                                label="Password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                disabled={loading}
                            />

                            <Button
                                type="submit"
                                fullWidth
                                variant="contained"
                                sx={{ mt: 3, mb: 2 }}
                                disabled={loading}
                            >
                                {loading ? 'Signing in...' : 'Sign In'}
                            </Button>
                        </Box>
                    </form>
                </Paper>
            </Box>

            <Dialog
                open={showChangePasswordModal}
                onClose={() => setShowChangePasswordModal(false)}
            >
                <DialogTitle>Change Password</DialogTitle>
                <DialogContent>
                    {changePasswordError && (
                        <Typography color="error" variant="body2" sx={{ mb: 2 }}>
                            {changePasswordError}
                        </Typography>
                    )}
                    <TextField
                        autoFocus
                        margin="dense"
                        label="New Password"
                        type="password"
                        fullWidth
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowChangePasswordModal(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleChangePassword} variant="contained">
                        Change Password
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default SignInPage;
