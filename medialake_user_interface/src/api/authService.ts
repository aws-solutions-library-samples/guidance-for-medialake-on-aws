// src/services/authService.ts
import { CognitoUserPool, CognitoRefreshToken } from 'amazon-cognito-identity-js';
import { StorageHelper } from '../common/helpers/storage-helper';
import { fetchAuthSession } from 'aws-amplify/auth';

class AuthService {
    private userPool: CognitoUserPool | null = null;

    private initializeUserPool() {
        const config = StorageHelper.getAwsConfig();
        if (config?.Auth?.Cognito?.userPoolId && config?.Auth?.Cognito?.userPoolClientId) {
            this.userPool = new CognitoUserPool({
                UserPoolId: config.Auth.Cognito.userPoolId,
                ClientId: config.Auth.Cognito.userPoolClientId,
            });
        }
    }

    async refreshToken(): Promise<string | null> {
        if (!this.userPool) {
            this.initializeUserPool();
        }

        return new Promise((resolve, reject) => {
            const user = this.userPool?.getCurrentUser();
            if (!user) {
                reject(new Error('No current user'));
                return;
            }

            const refreshToken = StorageHelper.getRefreshToken();
            if (!refreshToken) {
                reject(new Error('No refresh token available'));
                return;
            }

            const token = new CognitoRefreshToken({ RefreshToken: refreshToken });

            user.refreshSession(token, (err, session) => {
                if (err) {
                    console.error('Failed to refresh token:', err);
                    // Clear tokens if refresh fails
                    StorageHelper.clearToken();
                    StorageHelper.clearRefreshToken();
                    reject(err);
                } else {
                    const newIdToken = session.getIdToken().getJwtToken();
                    const newRefreshToken = session.getRefreshToken().getToken();

                    // Update stored tokens
                    StorageHelper.setToken(newIdToken);
                    StorageHelper.setRefreshToken(newRefreshToken);

                    resolve(newIdToken);
                }
            });
        });
    }

    getToken(): string | null {
        return StorageHelper.getToken();
    }

    clearTokens(): void {
        StorageHelper.clearToken();
        StorageHelper.clearRefreshToken();
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
