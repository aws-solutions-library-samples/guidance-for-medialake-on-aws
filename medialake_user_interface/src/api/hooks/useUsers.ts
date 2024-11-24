import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { User, CreateUserRequest, UpdateUserRequest } from '../types/api.types';

interface UsersResponse {
    status: string;
    message: string;
    data: {
        users: User[];
        searchMetadata: {
            totalResults: number;
            page: number;
            pageSize: number;
        };
    };
}

export const useGetUsers = () => {
    return useQuery<User[], Error>({
        queryKey: [QUERY_KEYS.USERS],
        queryFn: async () => {
            const { data } = await apiClient.get<{ statusCode: number; body: string }>(API_ENDPOINTS.USERS);
            const parsedBody = JSON.parse(data.body) as UsersResponse;
            // Map API response to include roles if not present
            return parsedBody.data.users.map(user => ({
                ...user,
                roles: user.roles || [] // Ensure roles is always present
            }));
        },
    });
};

export const useCreateUser = () => {
    const queryClient = useQueryClient();

    return useMutation<User, Error, CreateUserRequest>({
        mutationFn: async (newUser) => {
            const { data } = await apiClient.post<User>(API_ENDPOINTS.USERS, newUser);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};

export const useUpdateUser = () => {
    const queryClient = useQueryClient();

    return useMutation<User, Error, { username: string; updates: UpdateUserRequest }>({
        mutationFn: async ({ username, updates }) => {
            const { data } = await apiClient.put<User>(`${API_ENDPOINTS.USERS}/${username}`, updates);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};

export const useDeleteUser = () => {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (username) => {
            await apiClient.delete(`${API_ENDPOINTS.USERS}/${username}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};
