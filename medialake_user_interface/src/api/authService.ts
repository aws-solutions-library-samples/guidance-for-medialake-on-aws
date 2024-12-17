// src/services/authService.ts
import { fetchAuthSession, getCurrentUser, fetchUserAttributes } from 'aws-amplify/auth';
import { StorageHelper } from '../common/helpers/storage-helper';

class AuthService {
    async refreshToken(): Promise<string | null> {
        console.log('Starting token refresh process...');
        try {
            const session = await fetchAuthSession();
            const token = session.tokens?.idToken?.toString();

            if (token) {
                console.log('Session refresh successful');
                StorageHelper.setToken(token);
                return token;
            }

            console.error('No token in refreshed session');
            return null;
        } catch (error) {
            console.error('Failed to refresh token:', error);
            this.clearTokens();
            return null;
        }
    }

    async getToken(): Promise<string | null> {
        try {
            // First try to get from storage for performance
            const storedToken = StorageHelper.getToken();
            if (storedToken) {
                return storedToken;
            }

            // If no stored token, get from current session
            const session = await fetchAuthSession();
            const token = session.tokens?.idToken?.toString();

            if (token) {
                StorageHelper.setToken(token);
                return token;
            }

            return null;
        } catch (error) {
            console.error('Error getting token:', error);
            return null;
        }
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

    async isAuthenticated(): Promise<boolean> {
        try {
            const user = await getCurrentUser();
            return !!user;
        } catch {
            return false;
        }
    }

    async getUserInitial(): Promise<string> {
        try {
            const attributes = await fetchUserAttributes();
            const firstName = attributes.given_name || attributes.name?.split(' ')[0] || '';
            return firstName.charAt(0).toUpperCase() || 'A';
        } catch (error) {
            console.error('Error getting user attributes:', error);
            return 'A';
        }
    }
}

export const authService = new AuthService();
