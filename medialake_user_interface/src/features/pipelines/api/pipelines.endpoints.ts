export const PIPELINES_API = {
  BASE: "/pipelines",
  endpoints: {
    GET_PIPELINES: "/pipelines",
    GET_PIPELINE: (id: string) => `/pipelines/${id}`,
    CREATE_PIPELINE: "/pipelines",
    UPDATE_PIPELINE: (id: string) => `/pipelines/${id}`,
    DELETE_PIPELINE: (id: string) => `/pipelines/${id}`,
    UPDATE_STATUS: (id: string) => `/pipelines/${id}/status`,
    GET_PIPELINE_RUNS: (id: string) => `/pipelines/${id}/runs`,
    START_PIPELINE: (id: string) => `/pipelines/${id}/start`,
    STOP_PIPELINE: (id: string) => `/pipelines/${id}/stop`,
  },
} as const;
