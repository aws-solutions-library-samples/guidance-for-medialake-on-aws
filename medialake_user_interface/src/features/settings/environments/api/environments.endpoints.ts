export const ENVIRONMENTS_API = {
  endpoints: {
    GET_ENVIRONMENTS: "/environments",
    GET_ENVIRONMENT: (id: string) => `/environments/${id}`,
    CREATE_ENVIRONMENT: "/environments",
    UPDATE_ENVIRONMENT: (id: string) => `/environments/${id}`,
    DELETE_ENVIRONMENT: (id: string) => `/environments/${id}`,
  },
} as const;
