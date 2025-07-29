import {
  useEnvironments,
  useEnvironment,
} from "@/features/settings/environments/api/environmentsController";
import {
  Environment,
  EnvironmentError,
} from "@/features/settings/environments/types/environments.types";

export class IntegrationsEnvironmentsService {
  public static useEnvironments() {
    const {
      data,
      isLoading,
      error,
      isError,
      isFetching,
      refetch,
      isRefetching,
    } = useEnvironments();

    return {
      environments: data?.data?.environments ?? [],
      isLoading,
      isFetching,
      isRefetching,
      error: error as EnvironmentError | null,
      hasError: isError,
      isEmpty: !data?.data?.environments?.length,
      refetch,
    };
  }

  public static useEnvironment(environmentId: string) {
    const {
      data,
      isLoading,
      error,
      isError,
      isFetching,
      refetch,
      isRefetching,
    } = useEnvironment(environmentId);

    return {
      environment: data?.data,
      isLoading,
      isFetching,
      isRefetching,
      error: error as EnvironmentError | null,
      hasError: isError,
      isEmpty: !data?.data,
      refetch,
    };
  }

  public static getEnvironmentById(
    environments: Environment[],
    environmentId: string,
  ): Environment | undefined {
    return environments.find((env) => env.environment_id === environmentId);
  }

  public static getEnvironmentOptions(environments: Environment[] | undefined) {
    if (!environments) return [];
    return environments.map((env) => ({
      value: env.environment_id,
      label: env.name,
    }));
  }
}
