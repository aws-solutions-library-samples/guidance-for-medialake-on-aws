import { apiClient } from "@/api/apiClient";
import {
  EnvironmentsResponse,
  EnvironmentResponse,
  Environment,
} from "../types/environments.types";
import { ENVIRONMENTS_API } from "./environments.endpoints";

export class EnvironmentsService {
  public static async getEnvironments(): Promise<EnvironmentsResponse> {
    const response = await apiClient.get<EnvironmentsResponse>(
      ENVIRONMENTS_API.endpoints.GET_ENVIRONMENTS,
    );
    return response.data;
  }

  public static async getEnvironment(id: string): Promise<EnvironmentResponse> {
    const response = await apiClient.get<EnvironmentResponse>(
      ENVIRONMENTS_API.endpoints.GET_ENVIRONMENT(id),
    );
    return response.data;
  }

  public static async createEnvironment(
    environment: Omit<Environment, "id" | "createdAt" | "updatedAt">,
  ): Promise<EnvironmentResponse> {
    const response = await apiClient.post<EnvironmentResponse>(
      ENVIRONMENTS_API.endpoints.CREATE_ENVIRONMENT,
      environment,
    );
    return response.data;
  }

  public static async updateEnvironment(
    id: string,
    environment: Partial<Environment>,
  ): Promise<EnvironmentResponse> {
    const response = await apiClient.put<EnvironmentResponse>(
      ENVIRONMENTS_API.endpoints.UPDATE_ENVIRONMENT(id),
      environment,
    );
    return response.data;
  }

  public static async deleteEnvironment(id: string): Promise<void> {
    await apiClient.delete(ENVIRONMENTS_API.endpoints.DELETE_ENVIRONMENT(id));
  }
}
