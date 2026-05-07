import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  User,
  CreateUserRequest,
  UpdateUserRequest,
  CreateUserResponse,
  UserAttributes,
} from "../types/api.types";

interface UsersResponse {
  status: string;
  message: string;
  data: {
    users: User[];
    count: number;
    paginationToken?: string;
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

export const useGetUsers = (enabled = true) => {
  return useQuery<User[], Error>({
    queryKey: QUERY_KEYS.USERS.all,
    enabled: enabled,
    queryFn: async () => {
      const { data } = await apiClient.get<UsersResponse>(API_ENDPOINTS.USERS);
      return data.data.users.map((user) => ({
        ...user,
        permissions: user.permissions || [],
      }));
    },
  });
};

export const useGetUser = (userId: string) => {
  return useQuery<UserProfileResponse, Error>({
    queryKey: QUERY_KEYS.USERS.detail(userId),
    queryFn: async () => {
      const { data } = await apiClient.get<UserProfileResponse>(`${API_ENDPOINTS.USER}/${userId}`);

      let responseData = data;

      if (
        typeof responseData === "object" &&
        "statusCode" in responseData &&
        "body" in responseData
      ) {
        const wrappedResponse = responseData as {
          statusCode: number;
          body: string;
        };
        if (typeof wrappedResponse.body === "string") {
          responseData = JSON.parse(wrappedResponse.body);
        }
      }

      return responseData as UserProfileResponse;
    },
    enabled: !!userId,
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateUserResponse, Error, CreateUserRequest>({
    mutationFn: async (newUser) => {
      const response = await apiClient.post<CreateUserResponse>(API_ENDPOINTS.USER, newUser);

      let responseData = response.data;

      if (
        typeof responseData === "object" &&
        "statusCode" in responseData &&
        "body" in responseData
      ) {
        const wrappedResponse = responseData as {
          statusCode: number;
          body: string;
        };
        if (typeof wrappedResponse.body === "string") {
          responseData = JSON.parse(wrappedResponse.body);
        }
      }

      return {
        status: responseData.status,
        message: responseData.message,
        data: {
          username: responseData.data?.username,
          userStatus: responseData.data?.userStatus,
          groupsAdded: responseData.data?.groupsAdded || [],
          groupsFailed: responseData.data?.groupsFailed,
          groupsFailedCount: responseData.data?.groupsFailedCount,
          invalidGroups: responseData.data?.invalidGroups,
          invalidGroupsCount: responseData.data?.invalidGroupsCount,
        },
      };
    },
    onSuccess: () => {
      queryClient.refetchQueries({ queryKey: QUERY_KEYS.USERS.all });
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
      queryClient.refetchQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (username) => {
      await apiClient.delete(`${API_ENDPOINTS.USER}/${username}`);
    },
    onSuccess: () => {
      queryClient.refetchQueries({ queryKey: QUERY_KEYS.USERS.all });
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
      queryClient.refetchQueries({ queryKey: QUERY_KEYS.USERS.all });
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
      queryClient.refetchQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};
