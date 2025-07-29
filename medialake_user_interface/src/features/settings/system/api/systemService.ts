import { apiClient } from "@/api/apiClient";
import {
  SystemSettingsResponse,
  SearchProviderCreate,
  SearchProviderUpdate,
} from "../types/system.types";
import { SYSTEM_API } from "./system.endpoints";

export class SystemService {
  public static async getSystemSettings(): Promise<SystemSettingsResponse> {
    const response = await apiClient.get<SystemSettingsResponse>(
      SYSTEM_API.endpoints.GET_SYSTEM_SETTINGS,
    );
    return response.data;
  }

  public static async getSearchProvider(): Promise<SystemSettingsResponse> {
    const response = await apiClient.get<SystemSettingsResponse>(
      SYSTEM_API.endpoints.GET_SEARCH_PROVIDER,
    );
    return response.data;
  }

  public static async createSearchProvider(
    provider: SearchProviderCreate,
  ): Promise<SystemSettingsResponse> {
    const response = await apiClient.post<SystemSettingsResponse>(
      SYSTEM_API.endpoints.CREATE_SEARCH_PROVIDER,
      provider,
    );
    return response.data;
  }

  public static async updateSearchProvider(
    provider: SearchProviderUpdate,
  ): Promise<SystemSettingsResponse> {
    const response = await apiClient.put<SystemSettingsResponse>(
      SYSTEM_API.endpoints.UPDATE_SEARCH_PROVIDER,
      provider,
    );
    return response.data;
  }
}
