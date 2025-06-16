import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { User, CreateUserRequest, UpdateUserRequest, CreateUserResponse, UserAttributes } from '../types/api.types';

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

interface UserProfileResponse {
    status: string;
    message: string;
    data: {
        username: string;
        user_status: string;
        enabled: boolean;
        user_created: string;
        last_modified: string;
        attributes: UserAttributes;
    };
}

export const useGetUsers = () => {
    return useQuery<User[], Error>({
        queryKey: [QUERY_KEYS.USERS],
        queryFn: async () => {
            const { data } = await apiClient.get<{ statusCode: number; body: string }>(API_ENDPOINTS.USERS);
            const parsedBody = JSON.parse(data.body) as UsersResponse;
            console.log('Raw user data:', JSON.stringify(parsedBody.data.users[0]));
            // Map API response to include permissions if not present
            return parsedBody.data.users.map(user => ({
                ...user,
                permissions: user.permissions || [] // Ensure permissions is always present
            }));
        },
    });
};

export const useGetUser = (userId: string) => {
    return useQuery<UserProfileResponse, Error>({
        queryKey: QUERY_KEYS.USERS.detail(userId),
        queryFn: async () => {
            const { data } = await apiClient.get<UserProfileResponse>(`${API_ENDPOINTS.USER}/${userId}`);
            // Debug logging to see the raw API response
            console.log('Raw API Response from useGetUser:', JSON.stringify(data, null, 2));
            return data;
        },
        enabled: !!userId,
    });
};

export const useCreateUser = () => {
    const queryClient = useQueryClient();

    return useMutation<CreateUserResponse, Error, CreateUserRequest>({
        mutationFn: async (newUser) => {
            console.log('Sending user creation request with groups:', newUser.groups);
            const { data } = await apiClient.post<{ statusCode: number; body: string }>(API_ENDPOINTS.USER, newUser);
            console.log('Raw API Response:', data);

            // Parse the stringified body
            const parsedBody = JSON.parse(data.body);
            console.log('Parsed body:', parsedBody);

            // Log detailed group assignment results
            if (parsedBody.data) {
                console.log('Group assignment results:', {
                    groupsAdded: parsedBody.data.groupsAdded || [],
                    groupsFailed: parsedBody.data.groupsFailed || [],
                    invalidGroups: parsedBody.data.invalidGroups || [],
                    groupsAddedCount: parsedBody.data.groupsAdded?.length || 0,
                    groupsFailedCount: parsedBody.data.groupsFailedCount || 0,
                    invalidGroupsCount: parsedBody.data.invalidGroupsCount || 0,
                });

                // Log any issues with group assignment
                if (parsedBody.data.groupsFailed && parsedBody.data.groupsFailed.length > 0) {
                    console.warn('Some groups failed to be assigned:', parsedBody.data.groupsFailed);
                }
                if (parsedBody.data.invalidGroups && parsedBody.data.invalidGroups.length > 0) {
                    console.warn('Some groups were invalid:', parsedBody.data.invalidGroups);
                }
            }

            // Return the parsed response with the correct structure
            return {
                status: parsedBody.status,
                message: parsedBody.message,
                data: {
                    username: parsedBody.data.username,
                    userStatus: parsedBody.data.userStatus,
                    groupsAdded: parsedBody.data.groupsAdded || [],
                    groupsFailed: parsedBody.data.groupsFailed,
                    groupsFailedCount: parsedBody.data.groupsFailedCount,
                    invalidGroups: parsedBody.data.invalidGroups,
                    invalidGroupsCount: parsedBody.data.invalidGroupsCount,
                }
            };
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
            const { data } = await apiClient.put<User>(`${API_ENDPOINTS.USER}/${username}`, updates);
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

export const useDisableUser = () => {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (userId) => {
            await apiClient.post(API_ENDPOINTS.DISABLE_USER(userId));
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};

export const useEnableUser = () => {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (userId) => {
            await apiClient.post(API_ENDPOINTS.ENABLE_USER(userId));
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};
