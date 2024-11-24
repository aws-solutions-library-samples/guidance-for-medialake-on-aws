// import { useMutation, useQuery } from '@tanstack/react-query';
// import queryClient from '../queryClient';
// import { apiClient } from '../apiClient';
// import { API_ENDPOINTS } from '../endpoints';
// import { QUERY_KEYS } from '../queryKeys';
// import { logger } from '../../common/helpers/logger';
// import { useErrorModal } from '../../hooks/useErrorModal';
// import type {
//     User,
//     UserListResponse,
//     UserResponse,
//     CreateUserRequest,
//     UpdateUserRequest,
//     ApiResponse
// } from '../types/api.types';

// const validateUserRequest = (data: any) => {
//     if (!data) {
//         throw new Error('User data is required');
//     }
//     if (!data.username) {
//         throw new Error('Username is required');
//     }
//     if (!data.email) {
//         throw new Error('Email is required');
//     }
//     if (!data.roles || !Array.isArray(data.roles) || data.roles.length === 0) {
//         throw new Error('At least one role is required');
//     }
// };

// export const useGetUsers = () => {
//     const { showError } = useErrorModal();

//     return useQuery<UserListResponse, Error>({
//         queryKey: QUERY_KEYS.USERS.all,
//         queryFn: async ({ signal }) => {
//             try {
//                 const response = await apiClient.get<UserListResponse>(
//                     API_ENDPOINTS.USERS,
//                     { signal }
//                 );
//                 return response.data;
//             } catch (error) {
//                 logger.error('Fetch users error:', error);
//                 showError('Failed to fetch users');
//                 throw error;
//             }
//         },
//     });
// };

// export const useCreateUser = () => {
//     const { showError } = useErrorModal();

//     return useMutation<UserResponse, Error, CreateUserRequest>({
//         mutationFn: async (data) => {
//             validateUserRequest(data);
//             const response = await apiClient.post<UserResponse>(
//                 `${API_ENDPOINTS.USERS}/user`,
//                 data
//             );
//             return response.data;
//         },
//         onError: (error) => {
//             logger.error('Create user error:', error);
//             if (error.message === 'Network Error') {
//                 showError('Unable to save user - API is not available');
//             } else {
//                 showError(`Failed to create user: ${error.message}`);
//             }
//         },
//         onSuccess: (newUser) => {
//             queryClient.setQueryData<UserListResponse>(
//                 QUERY_KEYS.USERS.all,
//                 (old) => {
//                     if (!old) return {
//                         status: 'success',
//                         message: 'Users retrieved successfully',
//                         data: { users: [newUser.data] }
//                     };
//                     return {
//                         status: old.status,
//                         message: old.message,
//                         data: {
//                             ...old.data,
//                             users: [...old.data.users, newUser.data]
//                         }
//                     };
//                 }
//             );
//         },
//     });
// };

// export const useUpdateUser = () => {
//     const { showError } = useErrorModal();

//     return useMutation<UserResponse, Error, { id: string; data: UpdateUserRequest }>({
//         mutationFn: async ({ id, data }) => {
//             validateUserRequest(data);
//             const response = await apiClient.put<UserResponse>(
//                 `${API_ENDPOINTS.USERS}/${id}`,
//                 data
//             );
//             return response.data;
//         },
//         onMutate: async ({ id, data }) => {
//             await queryClient.cancelQueries({ queryKey: QUERY_KEYS.USERS.all });

//             const previousUsers = queryClient.getQueryData<UserListResponse>(
//                 QUERY_KEYS.USERS.all
//             );

//             queryClient.setQueryData<UserListResponse>(
//                 QUERY_KEYS.USERS.all,
//                 (old) => {
//                     if (!old) return previousUsers;
//                     return {
//                         status: old.status,
//                         message: old.message,
//                         data: {
//                             ...old.data,
//                             users: old.data.users.map(user =>
//                                 user.id === id
//                                     ? { ...user, ...data }
//                                     : user
//                             )
//                         }
//                     };
//                 }
//             );

//             return { previousUsers };
//         },
//         onError: (error, variables, context: { previousUsers?: UserListResponse }) => {
//             if (context?.previousUsers) {
//                 queryClient.setQueryData(
//                     QUERY_KEYS.USERS.all,
//                     context.previousUsers
//                 );
//             }
//             logger.error('Update user error:', error);
//             if (error.message === 'Network Error') {
//                 showError('Unable to save user - API is not available');
//             } else {
//                 showError(`Failed to update user: ${error.message}`);
//             }
//         }
//     });
// };

// export const useDeleteUser = () => {
//     const { showError } = useErrorModal();

//     return useMutation<ApiResponse<void>, Error, string>({
//         mutationFn: async (id) => {
//             const response = await apiClient.delete<ApiResponse<void>>(
//                 `${API_ENDPOINTS.USERS}/${id}`
//             );
//             return response.data;
//         },
//         onError: (error) => {
//             logger.error('Delete user error:', error);
//             if (error.message === 'Network Error') {
//                 showError('Unable to delete user - API is not available');
//             } else {
//                 showError(`Failed to delete user: ${error.message}`);
//             }
//         },
//         onSuccess: () => {
//             queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
//         },
//     });
// };

// export const useToggleUserStatus = () => {
//     const { showError } = useErrorModal();

//     return useMutation<UserResponse, Error, { id: string; status: 'active' | 'inactive' }>({
//         mutationFn: async ({ id, status }) => {
//             const response = await apiClient.put<UserResponse>(
//                 `${API_ENDPOINTS.USERS}/${id}`,
//                 { status }
//             );
//             return response.data;
//         },
//         onError: (error) => {
//             logger.error('Toggle user status error:', error);
//             if (error.message === 'Network Error') {
//                 showError('Unable to update user status - API is not available');
//             } else {
//                 showError(`Failed to update user status: ${error.message}`);
//             }
//         },
//         onSuccess: () => {
//             queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
//         },
//     });
// };
