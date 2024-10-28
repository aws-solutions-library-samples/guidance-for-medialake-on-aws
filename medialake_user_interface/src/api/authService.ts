// src/services/authService.ts
import { CognitoUserPool, CognitoRefreshToken, CognitoUser } from 'amazon-cognito-identity-js';
import { StorageHelper } from '../common/helpers/storage-helper';
import { fetchAuthSession } from 'aws-amplify/auth';

class AuthService {
    private userPool: CognitoUserPool | null = null;

    private initializeUserPool() {
        console.log('Initializing user pool...');
        const config = StorageHelper.getAwsConfig();
        if (config?.Auth?.Cognito?.userPoolId && config?.Auth?.Cognito?.userPoolClientId) {
            this.userPool = new CognitoUserPool({
                UserPoolId: config.Auth.Cognito.userPoolId,
                ClientId: config.Auth.Cognito.userPoolClientId,
            });
            console.log('User pool initialized successfully');
        } else {
            console.error('Missing Cognito configuration');
        }
    }

    private getCurrentUser(): CognitoUser | null {
        if (!this.userPool) {
            this.initializeUserPool();
        }
        const user = this.userPool?.getCurrentUser();
        console.log('Current user:', user ? 'Found' : 'Not found');
        return user;
    }

    async refreshToken(): Promise<string | null> {
        console.log('Starting token refresh process...');
        
        const user = this.getCurrentUser();
        if (!user) {
            console.error('No current user found during token refresh');
            return null;
        }

        const refreshToken = StorageHelper.getRefreshToken();
        if (!refreshToken) {
            console.error('No refresh token available during token refresh');
            return null;
        }

        console.log('Found refresh token, attempting to refresh session...');

        return new Promise((resolve, reject) => {
            const cognitoRefreshToken = new CognitoRefreshToken({ RefreshToken: refreshToken });

            user.refreshSession(cognitoRefreshToken, (err, session) => {
                if (err) {
                    console.error('Failed to refresh token:', err);
                    this.clearTokens();
                    reject(err);
                    return;
                }

                try {
                    console.log('Session refresh successful');
                    const newIdToken = session.getIdToken().getJwtToken();
                    const newRefreshToken = session.getRefreshToken().getToken();

                    // Update stored tokens
                    StorageHelper.setToken(newIdToken);
                    StorageHelper.setRefreshToken(newRefreshToken);

                    console.log('New tokens stored successfully');
                    resolve(newIdToken);
                } catch (error) {
                    console.error('Error processing refresh session:', error);
                    this.clearTokens();
                    reject(error);
                }
            });
        });
    }

    getToken(): string | null {
        const token = StorageHelper.getToken();
        console.log('Retrieved token:', token ? 'Present' : 'Not found');
        return token;
    }

    clearTokens(): void {
        console.log('Clearing all tokens...');
        StorageHelper.clearToken();
        StorageHelper.clearRefreshToken();
        StorageHelper.clearUsername();
    }

    async getCredentials() {
        try {
            const session = await fetchAuthSession();
            return session.credentials;
        } catch (error) {
            console.error('Error getting credentials:', error);
            return null;
        }
    }
}

export const authService = new AuthService();
