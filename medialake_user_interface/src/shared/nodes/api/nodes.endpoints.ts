export const NODES_API = {
    BASE: `/nodes`,
    endpoints: {
        GET_NODES: `/nodes`,
        GET_NODE: (nodeId: string) => `/nodes/${nodeId}`,
        CREATE_NODE: `/nodes`,
        UPDATE_NODE: (nodeId: string) => `/nodes/${nodeId}`,
        DELETE_NODE: (nodeId: string) => `/nodes/${nodeId}`,
    }
} as const; 