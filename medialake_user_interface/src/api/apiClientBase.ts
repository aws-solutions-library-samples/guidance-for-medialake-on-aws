import { StorageHelper } from '../common/helpers/storage-helper';

export abstract class ApiClientBase {
    protected async getHeaders() {
        const token = StorageHelper.getToken();
        if (!token) {
            throw new Error('No authentication token available');
        }
        return {
            Authorization: `Bearer ${token}`,
        };
    }

    // You can keep this method for fallback or future use
    protected async getIdToken() {
        const token = StorageHelper.getToken();
        if (token) {
            return token;
        }
    }
}