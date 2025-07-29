import { apiClient } from "@/api/apiClient";
import { INTEGRATIONS_API } from "./integrations.endpoints";
import type {
  CreateIntegrationDto,
  UpdateIntegrationDto,
  IntegrationsResponse,
} from "../types/integrations.types";

export const IntegrationsService = {
  createIntegration: async (
    data: CreateIntegrationDto,
  ): Promise<IntegrationsResponse> => {
    console.log(
      "[IntegrationsService] Making create integration API call with data:",
      data,
    );
    try {
      const response = await apiClient.post<IntegrationsResponse>(
        INTEGRATIONS_API.endpoints.CREATE_INTEGRATION,
        data,
      );
      console.log("[IntegrationsService] API call successful:", response.data);
      return response.data;
    } catch (error) {
      console.error("[IntegrationsService] API call failed:", error);
      throw error;
    }
  },
  getIntegrations: async (): Promise<IntegrationsResponse> => {
    const response = await apiClient.get<IntegrationsResponse>(
      INTEGRATIONS_API.endpoints.GET_INTEGRATIONS,
    );
    return response.data;
  },
  getIntegration: async (id: string): Promise<IntegrationsResponse> => {
    const response = await apiClient.get<IntegrationsResponse>(
      INTEGRATIONS_API.endpoints.GET_INTEGRATION(id),
    );
    return response.data;
  },
  updateIntegration: async (
    id: string,
    data: UpdateIntegrationDto,
  ): Promise<IntegrationsResponse> => {
    const response = await apiClient.put<IntegrationsResponse>(
      INTEGRATIONS_API.endpoints.UPDATE_INTEGRATION(id),
      data,
    );
    return response.data;
  },
  updateStatus: async (
    id: string,
    status: { status: string },
  ): Promise<IntegrationsResponse> => {
    const response = await apiClient.patch<IntegrationsResponse>(
      INTEGRATIONS_API.endpoints.UPDATE_STATUS(id),
      status,
    );
    return response.data;
  },
};
