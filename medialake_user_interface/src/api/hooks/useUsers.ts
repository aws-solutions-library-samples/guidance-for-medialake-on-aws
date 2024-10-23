// src/api/hooks/useUsers.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axiosClient from '../axiosClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';

interface User {
    id: string;
    name: string;
    email: string;
}

export const useGetUsers = () => {
    return useQuery<User[], Error>({
        queryKey: [QUERY_KEYS.USERS],
        queryFn: async () => {
            const { data } = await axiosClient.get<User[]>(API_ENDPOINTS.USERS);
            return data;
        },
    });
};

export const useGetUser = (userId: string) => {
    return useQuery<User, Error>({
        queryKey: [QUERY_KEYS.USERS, userId],
        queryFn: async () => {
            const { data } = await axiosClient.get<User>(`${API_ENDPOINTS.USERS}/${userId}`);
            return data;
        },
    });
};

export const useCreateUser = () => {
    const queryClient = useQueryClient();

    return useMutation<User, Error, Omit<User, 'id'>>({
        mutationFn: async (newUser) => {
            const { data } = await axiosClient.post<User>(API_ENDPOINTS.USERS, newUser);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};

export const useUpdateUser = () => {
    const queryClient = useQueryClient();

    return useMutation<User, Error, User>({
        mutationFn: async (updatedUser) => {
            const { data } = await axiosClient.put<User>(`${API_ENDPOINTS.USERS}/${updatedUser.id}`, updatedUser);
            return data;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS, data.id] });
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};

export const useDeleteUser = () => {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (userId) => {
            await axiosClient.delete(`${API_ENDPOINTS.USERS}/${userId}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.USERS] });
        },
    });
};
