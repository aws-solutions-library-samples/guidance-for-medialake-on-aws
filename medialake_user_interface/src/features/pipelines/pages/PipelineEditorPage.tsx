import React, {
  useCallback,
  useRef,
  useState,
  useMemo,
  useEffect,
} from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  ReactFlowProvider,
  useReactFlow,
  ReactFlowInstance,
  BackgroundVariant,
  Connection,
  Node,
  reconnectEdge,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  Box,
  Modal,
  Typography,
  TextField,
  Stack,
  Dialog,
  DialogTitle,
  DialogContent,
  Button,
  CircularProgress,
  Backdrop,
} from "@mui/material";
import ApiStatusModal from "@/components/ApiStatusModal";
import {
  FaFileVideo,
  FaBolt,
  FaCodeBranch,
  FaTools,
  FaPlug,
  FaCogs,
} from "react-icons/fa";
import { PipelineDeleteDialog } from "../components";
import { PipelineUpdateConfirmationDialog } from "../components/PipelineUpdateConfirmationDialog";
import {
  useGetPipeline,
  useCreatePipeline,
  useUpdatePipeline,
  useGetPipelineStatus,
} from "../api/pipelinesController";
import queryClient from "@/api/queryClient";
import { useGetNode } from "@/shared/nodes/api/nodesController";
import type {
  Pipeline,
  CreatePipelineDto,
  PipelineEdge,
  PipelineNode,
} from "../types/pipelines.types";
import type { NodesResponse } from "@/shared/nodes/types/nodes.types";
import { IntegrationValidationService } from "../services/integrationValidation.service";
import type {
  InvalidNodeInfo,
  IntegrationMapping,
} from "../services/integrationValidation.service";
import type { Integration } from "@/features/settings/integrations/types/integrations.types";
import {
  CustomNode,
  CustomEdge,
  Sidebar,
  NodeConfigurationForm,
  PipelineToolbar,
  // JobStatusNode
} from "../components/PipelineEditor";
import type { PipelineToolbarProps } from "../components/PipelineEditor/PipelineToolbar";
import IntegrationValidationDialog from "../components/IntegrationValidationDialog";
import { Node as NodeType, NodeConfiguration, NodeMethod } from "../types";
import {
  RightSidebarProvider,
  useRightSidebar,
} from "@/components/common/RightSidebar/SidebarContext";
// import { JOB_STATUS_NODE_TYPE } from '../components/PipelineEditor/jobStatusNodeUtils';

// Define the custom node data type
interface CustomNodeData {
  label: string;
  icon: React.ReactNode;
  inputTypes: string[];
  outputTypes: string[] | { name: string; description: string }[];
  nodeId: string;
  id?: string; // Add id property for backward compatibility
  description: string;
  configuration?: any;
  onDelete?: (id: string) => void;
  onConfigure?: (id: string) => void;
  type?: string; // Node type (e.g., 'TRIGGER', 'INTEGRATION', 'FLOW')
}

const nodeTypes = {
  custom: CustomNode,
  // jobStatusNode: JobStatusNode
};

const edgeTypes = {
  custom: CustomEdge,
};

// Track the highest node ID to ensure we generate unique IDs
let id = 0;
const getId = () => {
  // Generate a new unique ID
  return `dndnode_${id++}`;
};

// Function to update the ID counter based on existing nodes
const updateIdCounter = (existingNodes) => {
  if (!existingNodes || existingNodes.length === 0) return;

  // Find the highest numeric ID from existing dndnodes
  existingNodes.forEach((node) => {
    if (node.id && node.id.startsWith("dndnode_")) {
      const nodeIdNum = parseInt(node.id.replace("dndnode_", ""), 10);
      if (!isNaN(nodeIdNum) && nodeIdNum >= id) {
        id = nodeIdNum + 1;
      }
    }
  });

  // Also check for any numeric IDs that might conflict with future dndnode IDs
  // This handles imported nodes that might have numeric IDs
  existingNodes.forEach((node) => {
    if (node.id) {
      // Extract any trailing numbers from the ID
      const match = node.id.match(/(\d+)$/);
      if (match) {
        const nodeIdNum = parseInt(match[1], 10);
        if (!isNaN(nodeIdNum) && nodeIdNum >= id) {
          id = nodeIdNum + 1;
        }
      }
    }
  });

  console.log(`[PipelineEditorPage] Updated ID counter to ${id}`);
};

const convertToPipelineNode = (node: Node<CustomNodeData>): PipelineNode => ({
  id: node.id,
  type: node.type || "custom",
  position: {
    x: node.position.x.toString(),
    y: node.position.y.toString(),
  },
  width: node.width?.toString() || "180",
  height: node.height?.toString() || "40",
  data: {
    id: node.data.id || node.data.nodeId, // Use id if available, otherwise use nodeId
    nodeId: node.data.nodeId || node.data.id, // Use nodeId if available, otherwise use id
    type: node.data.type,
    label: node.data.label,
    description: node.data.description || "",
    icon: {
      props: {
        size: 20,
      },
    },
    inputTypes: node.data.inputTypes,
    outputTypes: node.data.outputTypes,
    configuration: node.data.configuration,
  },
  positionAbsolute: node.positionAbsolute
    ? {
        x: node.positionAbsolute.x.toString(),
        y: node.positionAbsolute.y.toString(),
      }
    : undefined,
  selected: node.selected,
  dragging: node.dragging,
});

const convertApiResponseToNode = (response: NodesResponse): NodeType | null => {
  console.log(
    "[PipelineEditorPage] convertApiResponseToNode called with:",
    response,
  );
  if (!response || !response.data || !response.data[0]) {
    console.log("[PipelineEditorPage] Invalid response structure");
    return null;
  }

  const nodeData = response.data[0];
  console.log("[PipelineEditorPage] Node data from response:", nodeData);

  // Create a methods object with the config property
  const methods = nodeData.methods?.reduce(
    (acc, method) => {
      console.log("[PipelineEditorPage] Processing method:", method);

      // Convert parameters to Record format
      // Handle both array format and single object format
      let parameters = {};

      if (Array.isArray(method.parameters)) {
        // Standard array format
        parameters = method.parameters.reduce((paramAcc, param) => {
          const parameterData: any = {
            name: param.name,
            label: param.label,
            type:
              param.schema.type === "string"
                ? "text"
                : (param.schema.type as "number" | "boolean" | "select"),
            required: param.required || false,
            description: param.description,
          };

          // Add options if they exist in the schema
          if (param.schema.options) {
            parameterData.options = param.schema.options;
          }

          // Preserve default value if it exists (API uses 'default', but our type uses 'defaultValue')
          if ((param as any).default !== undefined) {
            parameterData.defaultValue = (param as any).default;
            console.log(
              `[PipelineEditorPage] Found default value for ${param.name}:`,
              (param as any).default,
            );
          }

          return {
            ...paramAcc,
            [param.name]: parameterData,
          };
        }, {});
      } else if (method.parameters && typeof method.parameters === "object") {
        // Single object format (like S3 Vector Store)
        const param = method.parameters as any;
        const paramName = param.name || "parameter";

        // Handle object type parameters with nested properties
        if (
          param.schema &&
          param.schema.type === "object" &&
          param.schema.properties
        ) {
          // For object parameters, create individual fields for each property
          Object.entries(param.schema.properties).forEach(
            ([propName, propSchema]: [string, any]) => {
              const parameterData: any = {
                name: propName,
                label: propName.charAt(0).toUpperCase() + propName.slice(1),
                type:
                  propSchema.type === "string"
                    ? "text"
                    : (propSchema.type as "number" | "boolean" | "select"),
                required: param.schema.required?.includes(propName) || false,
                description: propSchema.description || "",
              };

              // Add options if they exist in the schema
              if (propSchema.options) {
                parameterData.options = propSchema.options;
              }

              parameters[propName] = parameterData;
            },
          );
        } else {
          // Single parameter
          const parameterData: any = {
            name: paramName,
            label: param.label || paramName,
            type:
              param.schema?.type === "string"
                ? "text"
                : (param.schema?.type as "number" | "boolean" | "select"),
            required: param.required || false,
            description: param.description || param.schema?.description || "",
          };

          // Add options if they exist in the schema
          if (param.schema?.options) {
            parameterData.options = param.schema.options;
          }

          // Preserve default value if it exists
          if (param.default !== undefined) {
            parameterData.defaultValue = param.default;
            console.log(
              `[PipelineEditorPage] Found default value for ${paramName}:`,
              param.default,
            );
          }

          parameters[paramName] = parameterData;
        }
      }

      // Extract config from method using type assertion
      // Different node types have different config structures
      const nodeType = nodeData.info?.nodeType;
      let config;

      if (nodeType === "TRIGGER") {
        // For trigger nodes, use the method name as the operationId
        config = {
          path: "",
          operationId: method.name,
          parameters: (method as any).parameters || [],
          requestMapping: (method as any).requestMapping || null,
          responseMapping: (method as any).responseMapping || null,
        };
        // } else if (nodeType === 'FLOW') {
        //     // For flow nodes, get parameters from the actions section
        //     const actionName = method.name;
        //     console.log('[PipelineEditorPage] Flow node action name:', actionName);
        //     console.log('[PipelineEditorPage] Node data:', nodeData);
        //     console.log('[PipelineEditorPage] Actions:', (nodeData as any).actions);

        //     const actionParams = (nodeData as any).actions?.[actionName]?.parameters || [];
        //     console.log('[PipelineEditorPage] Action parameters:', actionParams);

        //     // Convert action parameters to Record format
        //     const flowParameters = actionParams.reduce((paramAcc: Record<string, any>, param: any) => {
        //         console.log('[PipelineEditorPage] Processing parameter:', param);
        //         return {
        //             ...paramAcc,
        //             [param.name]: {
        //                 name: param.name,
        //                 label: param.name,
        //                 type: param.schema?.type === 'string' ? 'text' : param.schema?.type as 'number' | 'boolean' | 'select',
        //                 required: param.required || false,
        //                 description: param.description
        //             }
        //         };
        //     }, {});

        //     console.log('[PipelineEditorPage] Converted flow parameters:', flowParameters);

        //     config = {
        //         path: '',
        //         operationId: method.name,
        //         parameters: actionParams.map(param => ({
        //             in: 'body',
        //             name: param.name,
        //             required: param.required || false,
        //             schema: param.schema || { type: 'string' }
        //         })),
        //         requestMapping: (method as any).requestMapping || null,
        //         responseMapping: (method as any).responseMapping || null
        //     };

        //     console.log('[PipelineEditorPage] Flow node config:', config);

        //     // Add method with flow parameters
        //     return {
        //         ...acc,
        //         [method.name]: {
        //             name: method.name,
        //             description: method.description || '',
        //             parameters: flowParameters,
        //             config: config
        //         }
        //     };
      } else if (nodeType === "FLOW") {
        // For FLOW nodes, use the parameters from the method object directly
        console.log("[PipelineEditorPage] Flow node action name:", method.name);

        // Use the same parameter processing logic as above
        let flowParameters = {};

        if (Array.isArray(method.parameters)) {
          flowParameters = method.parameters.reduce((paramAcc, param) => {
            console.log("[PipelineEditorPage] Processing parameter:", param);
            const parameterData: any = {
              name: param.name,
              label: param.label || param.name,
              type:
                param.schema?.type === "string"
                  ? "text"
                  : (param.schema?.type as "number" | "boolean" | "select"),
              required: param.required || false,
              description: param.description,
            };

            // Preserve default value if it exists
            if ((param as any).default !== undefined) {
              parameterData.defaultValue = (param as any).default;
              console.log(
                `[PipelineEditorPage] Found default value for ${param.name}:`,
                (param as any).default,
              );
            }
            return { ...paramAcc, [param.name]: parameterData };
          }, {});
        } else if (method.parameters && typeof method.parameters === "object") {
          // Handle single object format for FLOW nodes too
          const param = method.parameters as any;
          const paramName = param.name || "parameter";

          if (
            param.schema &&
            param.schema.type === "object" &&
            param.schema.properties
          ) {
            Object.entries(param.schema.properties).forEach(
              ([propName, propSchema]: [string, any]) => {
                const parameterData: any = {
                  name: propName,
                  label: propName.charAt(0).toUpperCase() + propName.slice(1),
                  type:
                    propSchema.type === "string"
                      ? "text"
                      : (propSchema.type as "number" | "boolean" | "select"),
                  required: param.schema.required?.includes(propName) || false,
                  description: propSchema.description || "",
                };

                if (propSchema.options) {
                  parameterData.options = propSchema.options;
                }

                flowParameters[propName] = parameterData;
              },
            );
          } else {
            const parameterData: any = {
              name: paramName,
              label: param.label || paramName,
              type:
                param.schema?.type === "string"
                  ? "text"
                  : (param.schema?.type as "number" | "boolean" | "select"),
              required: param.required || false,
              description: param.description || param.schema?.description || "",
            };

            if (param.schema?.options) {
              parameterData.options = param.schema.options;
            }

            if (param.default !== undefined) {
              parameterData.defaultValue = param.default;
            }

            flowParameters[paramName] = parameterData;
          }
        }

        console.log(
          "[PipelineEditorPage] Converted flow parameters:",
          flowParameters,
        );

        const config = {
          path: "",
          operationId: method.name,
          parameters: Array.isArray(method.parameters)
            ? method.parameters
            : method.parameters
              ? [method.parameters]
              : [],
          requestMapping: (method as any).requestMapping || null,
          responseMapping: (method as any).responseMapping || null,
        };

        console.log("[PipelineEditorPage] Flow node config:", config);

        // Return the method entry with the converted parameters record.
        return {
          ...acc,
          [method.name]: {
            name: method.name,
            description: method.description || "",
            parameters: flowParameters,
            config: config,
          },
        };
      } else {
        // For integration nodes, extract from config property
        config = {
          path: (method as any).config?.path || "",
          operationId: (method as any).config?.operationId || "",
          parameters: (method as any).config?.parameters || [],
          requestMapping:
            (method as any).requestMapping ||
            (method as any).config?.requestMapping ||
            null,
          responseMapping:
            (method as any).responseMapping ||
            (method as any).config?.responseMapping ||
            null,
        };
      }

      console.log("[PipelineEditorPage] Method config:", config);
      console.log("[PipelineEditorPage] Method:", method);

      // If method already exists, merge parameters
      if (acc[method.name]) {
        return {
          ...acc,
          [method.name]: {
            ...acc[method.name],
            parameters: { ...acc[method.name].parameters, ...parameters },
            config: config, // Add config property
          },
        };
      }

      // Add new method with config
      return {
        ...acc,
        [method.name]: {
          name: method.name,
          description: method.description || "",
          parameters,
          config: config, // Add config property
        },
      };
    },
    {} as Record<string, any>,
  );

  // Determine inputTypes:
  // If the API provided inputTypes in info, use those;
  // Otherwise, if there are incoming connections, extract the types from connectionConfig.
  let inputTypes: string[] = [];
  if (nodeData.info?.inputTypes && nodeData.info.inputTypes.length > 0) {
    inputTypes = nodeData.info.inputTypes.map((item) => String(item));
  } else if (nodeData.connections && nodeData.connections.incoming) {
    // Flatten all types found in all incoming connections

    const typesFromConnections = Object.values(
      nodeData.connections.incoming,
    ).flatMap((conns: any) =>
      conns.flatMap((conn: any) => conn.connectionConfig?.type || []),
    );
    inputTypes = Array.from(new Set(typesFromConnections));
  }

  // Determine outputTypes:
  // If the API provided outputTypes in info, use those;
  // Otherwise, if there are outgoing connections, extract the types from connectionConfig.
  let outputTypes: string[] = [];
  if (nodeData.info?.outputTypes && nodeData.info.outputTypes.length > 0) {
    outputTypes = nodeData.info.outputTypes.map((item) => String(item));
  } else if (nodeData.connections && nodeData.connections.outgoing) {
    // Flatten all types found in all outgoing connections

    const typesFromConnections = Object.values(
      nodeData.connections.outgoing,
    ).flatMap((conns: any) =>
      conns.flatMap((conn: any) => conn.connectionConfig?.type || []),
    );
    outputTypes = Array.from(new Set(typesFromConnections));
  }

  const result = {
    nodeId: nodeData.nodeId,
    info: {
      enabled: nodeData.info?.enabled || false,
      categories: nodeData.info?.categories || [],
      updatedAt: nodeData.info?.updatedAt || new Date().toISOString(),
      nodeType: nodeData.info?.nodeType || "default",
      iconUrl: nodeData.info?.iconUrl || "",
      description: nodeData.info?.description || "",
      tags: nodeData.info?.tags || [],
      title: nodeData.info?.title || "",
      inputTypes: inputTypes,
      // outputTypes: nodeData.info?.outputTypes || [],
      outputTypes: outputTypes,

      createdAt: nodeData.info?.createdAt || new Date().toISOString(),
    },
    methods: methods,
  };

  console.log("[PipelineEditorPage] Converted node:", result);
  return result;
};

const PipelineEditorContent = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { id: pipelineId } = useParams();
  const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  // Track whether the pipeline has been initialized
  const pipelineInitialized = useRef(false);
  // Track whether edge reconnection was successful
  const edgeReconnectSuccessful = useRef(true);

  // Custom handler for node changes to update the pipeline configuration
  const handleNodesChange = useCallback(
    (changes) => {
      // First apply the changes to the nodes state
      onNodesChange(changes);

      // Then update the pipeline configuration with the new node positions
      changes.forEach((change) => {
        if (change.type === "position" && change.positionAbsolute) {
          console.log("[PipelineEditorPage] Node position changed:", change);

          // Update the form data with the new node position
          setFormData((prev) => {
            const updatedNodes = prev.configuration.nodes.map((node) => {
              if (node.id === change.id) {
                console.log(
                  "[PipelineEditorPage] Updating node position in form data:",
                  node.id,
                );
                return {
                  ...node,
                  position: {
                    x: change.positionAbsolute.x.toString(),
                    y: change.positionAbsolute.y.toString(),
                  },
                  positionAbsolute: {
                    x: change.positionAbsolute.x.toString(),
                    y: change.positionAbsolute.y.toString(),
                  },
                };
              }
              return node;
            });

            return {
              ...prev,
              configuration: {
                ...prev.configuration,
                nodes: updatedNodes,
              },
            };
          });
        }
      });
    },
    [onNodesChange],
  );
  const { screenToFlowPosition } = useReactFlow();
  const reactFlowInstance = useReactFlow();
  const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);
  const [errorType, setErrorType] = useState<"trigger" | "compatibility">(
    "compatibility",
  );
  const [selectedNode, setSelectedNode] = useState<Node<CustomNodeData> | null>(
    null,
  );
  const [isNodeConfigOpen, setIsNodeConfigOpen] = useState(false);
  const { isExpanded } = useRightSidebar();

  // State for API status modal
  const [apiStatusModalOpen, setApiStatusModalOpen] = useState(false);
  const [apiStatusModalState, setApiStatusModalState] = useState<
    "loading" | "success" | "error"
  >("loading");
  const [apiStatusModalMessage, setApiStatusModalMessage] = useState("");
  const [apiStatusModalAction, setApiStatusModalAction] = useState("");
  // Delete dialog state
  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    pipelineName: "",
    pipelineId: "",
    userInput: "",
  });

  // Update confirmation dialog state
  const [updateConfirmationOpen, setUpdateConfirmationOpen] = useState(false);

  // State for pipeline creation status tracking
  const [creatingPipelineId, setCreatingPipelineId] = useState<string | null>(
    null,
  );
  const [executionArn, setExecutionArn] = useState<string | null>(null);
  const [shouldPollStatus, setShouldPollStatus] = useState(false);

  const [formData, setFormData] = React.useState<CreatePipelineDto>({
    name: "",
    description: "",
    active: true, // Default to active
    configuration: {
      nodes: [],
      edges: [],
      settings: {
        autoStart: false,
        retryAttempts: 3,
        timeout: 3600,
      },
    },
  });

  // Fetch all pipelines when the component mounts

  const { data: pipeline } = useGetPipeline(pipelineId || "", {
    enabled: !!pipelineId && pipelineId !== "new",
  });

  // Only fetch node details when the dialog is open and we have a selected node
  // Store the nodeId in a ref to prevent unnecessary re-renders
  const nodeIdRef = React.useRef<string>("");

  // Only update the nodeId when the dialog opens or closes
  React.useEffect(() => {
    if (isNodeConfigOpen && selectedNode?.data?.nodeId) {
      nodeIdRef.current = selectedNode.data.nodeId;
    } else if (!isNodeConfigOpen) {
      nodeIdRef.current = "";
    }
  }, [isNodeConfigOpen, selectedNode]);

  const { data: nodeDetails, isLoading: isNodeDetailsLoading } = useGetNode(
    nodeIdRef.current,
    {
      enabled: isNodeConfigOpen && !!nodeIdRef.current,
    },
  );

  // Add debug logging for node details
  React.useEffect(() => {
    if (nodeDetails) {
      console.log("[PipelineEditorPage] Node details from API:", nodeDetails);
      console.log(
        "[PipelineEditorPage] Node type:",
        nodeDetails.data?.[0]?.info?.nodeType,
      );
      console.log(
        "[PipelineEditorPage] Node methods:",
        nodeDetails.data?.[0]?.methods,
      );
    }
  }, [nodeDetails]);

  // Memoize the converted node data to prevent unnecessary recalculations
  const convertedNodeData = React.useMemo(() => {
    if (!nodeDetails) return {} as NodeType;
    const converted = convertApiResponseToNode(nodeDetails);
    console.log("[PipelineEditorPage] Converted node data:", converted);
    return converted || ({} as NodeType);
  }, [nodeDetails]);

  const createPipeline = useCreatePipeline({
    onSuccess: (data) => {
      console.log("[PipelineEditorPage] Pipeline creation started:", data);
      // Show success message in ApiStatusModal
      setApiStatusModalState("success");
      setApiStatusModalAction("Pipeline Creation Started");
      setApiStatusModalMessage(
        "Pipeline creation started. This might take a while. You can monitor the status in the pipeline page.",
      );
      setApiStatusModalOpen(true);

      // Store the pipeline ID and execution ARN for status polling
      setCreatingPipelineId(data.pipeline_id);
      setExecutionArn(data.execution_arn);
    },
    onError: (error) => {
      console.error("[PipelineEditorPage] Pipeline creation error:", error);
      // Show error message in ApiStatusModal
      setApiStatusModalState("error");
      setApiStatusModalAction("Pipeline Creation Failed");
      setApiStatusModalMessage(
        error.message || "An error occurred while creating the pipeline.",
      );
      setApiStatusModalOpen(true);
    },
  });

  const updatePipeline = useUpdatePipeline({
    onSuccess: () => {
      navigate("/pipelines");
    },
  });

  // Set up the pipeline status polling
  const { data: pipelineStatus, refetch: refetchPipelineStatus } =
    useGetPipelineStatus(executionArn || "", {
      enabled: !!executionArn && shouldPollStatus,
      refetchInterval: 5000, // Poll every 5 seconds
    });

  // Handle pipeline status changes
  useEffect(() => {
    if (pipelineStatus && shouldPollStatus) {
      console.log("[PipelineEditorPage] Pipeline status:", pipelineStatus);
      console.log(
        "[PipelineEditorPage] Step function status:",
        pipelineStatus.step_function_status,
      );
      console.log(
        "[PipelineEditorPage] Pipeline record:",
        pipelineStatus.pipeline,
      );

      if (pipelineStatus.pipeline) {
        console.log(
          "[PipelineEditorPage] Pipeline deploymentStatus:",
          pipelineStatus.pipeline.deploymentStatus,
        );
      }

      // Check if the pipeline creation is complete
      if (pipelineStatus.step_function_status === "SUCCEEDED") {
        // Pipeline creation completed successfully
        console.log(
          "[PipelineEditorPage] Pipeline creation completed successfully",
        );
        setShouldPollStatus(false);
        queryClient.invalidateQueries({ queryKey: ["pipelines", "list"] });

        // Force a refetch of the pipeline status to ensure we have the latest data
        refetchPipelineStatus();
      } else if (
        ["FAILED", "TIMED_OUT", "ABORTED"].includes(
          pipelineStatus.step_function_status,
        )
      ) {
        // Pipeline creation failed
        console.error(
          "[PipelineEditorPage] Pipeline creation failed:",
          pipelineStatus.step_function_status,
        );
        setShouldPollStatus(false);

        // Force a refetch of the pipeline status to ensure we have the latest data
        refetchPipelineStatus();

        // Show error message
        setApiStatusModalState("error");
        setApiStatusModalAction("Pipeline Creation Failed");
        setApiStatusModalMessage(
          `Pipeline creation failed with status: ${pipelineStatus.step_function_status}`,
        );
        setApiStatusModalOpen(true);
      }
    }
  }, [pipelineStatus, shouldPollStatus]);

  // Start polling when the modal is closed after successful creation
  const handleApiStatusModalClose = useCallback(() => {
    setApiStatusModalOpen(false);

    // If we have an execution ARN and the status was success, start polling
    if (executionArn && apiStatusModalState === "success") {
      setShouldPollStatus(true);
    }

    // Always navigate back to pipelines page when modal closes
    navigate("/pipelines");
  }, [executionArn, apiStatusModalState, navigate]);

  // Set form data when pipeline data is loaded
  React.useEffect(() => {
    if (pipeline) {
      console.log(
        "[PipelineEditorPage] Setting form data from pipeline:",
        pipeline,
      );
      setFormData({
        name: pipeline.name,
        description: pipeline.description || "",
        active: pipeline.active !== false, // Use pipeline active state or default to true
        configuration: pipeline.configuration || {
          nodes: [],
          edges: [],
          settings: {
            autoStart: false,
            retryAttempts: 3,
            timeout: 3600,
          },
        },
      });
    }
  }, [pipeline]);

  // Add handler for active state change
  const handleActiveChange = (active: boolean) => {
    setFormData((prev) => ({
      ...prev,
      active,
    }));
  };

  const handleSave = async () => {
    console.log(
      "[PipelineEditorPage] Saving pipeline with form data:",
      formData,
    );
    console.log(
      "[PipelineEditorPage] Number of nodes:",
      formData.configuration.nodes.length,
    );
    console.log(
      "[PipelineEditorPage] Number of edges:",
      formData.configuration.edges.length,
    );
    console.log(
      "[PipelineEditorPage] Node positions:",
      formData.configuration.nodes.map((node) => ({
        id: node.id,
        position: node.position,
        positionAbsolute: node.positionAbsolute,
      })),
    );

    // If we're updating an existing pipeline, show confirmation dialog
    if (pipelineId && pipelineId !== "new") {
      setUpdateConfirmationOpen(true);
    } else {
      // For new pipelines, proceed directly
      proceedWithSave();
    }
  };

  // Function to proceed with saving after confirmation
  const proceedWithSave = () => {
    // Show the ApiStatusModal in loading state
    setApiStatusModalState("loading");
    setApiStatusModalAction(
      pipelineId && pipelineId !== "new"
        ? "Updating Pipeline"
        : "Creating Pipeline",
    );
    setApiStatusModalMessage("Please wait...");
    setApiStatusModalOpen(true);

    if (pipelineId && pipelineId !== "new") {
      // Add updateDeployed flag for deployed pipelines
      updatePipeline.mutate({
        id: pipelineId,
        data: {
          ...formData,
          updateDeployed: true, // Flag to indicate updating a deployed pipeline
        },
      });
    } else {
      createPipeline.mutate(formData);
    }
  };

  const onDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((node) => node.id !== nodeId));
      setEdges((eds) =>
        eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
      );

      // Update pipeline configuration
      setFormData((prev) => ({
        ...prev,
        configuration: {
          ...prev.configuration,
          nodes: prev.configuration.nodes.filter((node) => node.id !== nodeId),
          edges: prev.configuration.edges.filter(
            (edge) => edge.source !== nodeId && edge.target !== nodeId,
          ),
          settings: prev.configuration.settings || {
            autoStart: false,
            retryAttempts: 3,
            timeout: 3600,
          },
        },
      }));
    },
    [setNodes, setEdges],
  );

  const onConfigureNode = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        setSelectedNode(node);
        setIsNodeConfigOpen(true);
      }
    },
    [nodes],
  );

  // Debug pipeline object
  React.useEffect(() => {
    if (pipeline) {
      console.log("[PipelineEditorPage] Pipeline object:", pipeline);
      console.log(
        "[PipelineEditorPage] Pipeline deploymentStatus:",
        pipeline.deploymentStatus,
      );
    }
  }, [pipeline]);

  // State for integration validation
  const [validationDialogOpen, setValidationDialogOpen] = useState(false);
  const [invalidNodes, setInvalidNodes] = useState<InvalidNodeInfo[]>([]);
  const [availableIntegrations, setAvailableIntegrations] = useState<
    Integration[]
  >([]);
  const [importedFlowData, setImportedFlowData] = useState<any>(null);
  const [isImporting, setIsImporting] = useState(false);

  // Check for imported flow from location state
  React.useEffect(() => {
    const loadImportedFlow = async () => {
      const state = location.state as {
        importedFlow?: any;
        pipelineName?: string;
        showImporting?: boolean;
      };
      if (state?.importedFlow) {
        // Set pipeline name if provided in state
        if (state.pipelineName) {
          setFormData((prev) => ({
            ...prev,
            name: state.pipelineName,
            // Ensure active property is set from imported flow or default to true
            active:
              state.importedFlow.active !== undefined
                ? state.importedFlow.active
                : true,
          }));
        } else {
          // If no pipeline name, still set the active property
          setFormData((prev) => ({
            ...prev,
            active:
              state.importedFlow.active !== undefined
                ? state.importedFlow.active
                : true,
          }));
        }
        console.log(
          "[PipelineEditorPage] Initializing from imported flow:",
          state.importedFlow,
        );

        // Set importing state based on the flag from navigation state or default to true
        setIsImporting(
          state.showImporting !== undefined ? state.showImporting : true,
        );

        try {
          // Check if nodes and edges are under a configuration property
          const importedFlow = { ...state.importedFlow };
          if (
            importedFlow.configuration &&
            importedFlow.configuration.nodes &&
            importedFlow.configuration.edges
          ) {
            console.log(
              "[PipelineEditorPage] Found nodes and edges under configuration property",
            );
            // Move nodes and edges to the top level
            importedFlow.nodes = importedFlow.configuration.nodes;
            importedFlow.edges = importedFlow.configuration.edges;
            // Update the state.importedFlow reference
            state.importedFlow = importedFlow;
          }

          // Check if the flow uses the nodes/edges structure
          if (state.importedFlow.nodes && state.importedFlow.edges) {
            // Ensure each edge has a data field with at least a text property
            const fixedEdges = state.importedFlow.edges.map((edge: any) => {
              if (!edge.data) {
                edge.data = { text: "", id: edge.id, type: "custom" };
              } else if (typeof edge.data === "object" && !edge.data.id) {
                // If data exists but doesn't have id and type fields, add them
                edge.data = {
                  ...edge.data,
                  id: edge.id,
                  type: "custom",
                };
              }
              return edge;
            });

            const fixedNodes = state.importedFlow.nodes.map((node: any) => {
              // Ensure node.data has both id and nodeId properties
              const updatedData = {
                ...node.data,
                // If id is missing but nodeId exists, copy nodeId to id
                id: node.data.id || node.data.nodeId,
                // If nodeId is missing but id exists, copy id to nodeId
                nodeId: node.data.nodeId || node.data.id,
                // Fix icon if needed
                icon:
                  node.data.icon &&
                  typeof node.data.icon === "object" &&
                  node.data.icon.props
                    ? getNodeIcon(node.data.type)
                    : node.data.icon,
              };

              return {
                ...node,
                data: updatedData,
              };
            });

            // Store the imported flow data for later use
            setImportedFlowData({
              nodes: fixedNodes,
              edges: fixedEdges,
            });

            // Validate integration IDs
            try {
              console.log("[PipelineEditorPage] Validating integration IDs...");
              const validationResult =
                await IntegrationValidationService.validateIntegrationIds(
                  fixedNodes,
                );

              if (validationResult.isValid) {
                console.log(
                  "[PipelineEditorPage] All integration IDs are valid",
                );
                // All integration IDs are valid, proceed with import
                // Update ID counter to avoid conflicts with existing nodes
                updateIdCounter(fixedNodes);
                setNodes(fixedNodes);
                setEdges(fixedEdges);

                // Update form data
                const pipelineNodes = fixedNodes.map(convertToPipelineNode);
                const pipelineEdges = fixedEdges.map((edge: any) => ({
                  id: edge.id,
                  source: edge.source,
                  target: edge.target,
                  sourceHandle: edge.sourceHandle,
                  targetHandle: edge.targetHandle,
                  type: edge.type || "custom",
                  data: edge.data || { text: "", id: edge.id, type: "custom" },
                }));

                setFormData((prev) => ({
                  ...prev,
                  configuration: {
                    ...prev.configuration,
                    nodes: pipelineNodes,
                    edges: pipelineEdges,
                  },
                }));
              } else {
                console.log(
                  "[PipelineEditorPage] Invalid integration IDs found:",
                  validationResult.invalidNodes,
                );
                // Some integration IDs are invalid, show validation dialog
                setInvalidNodes(validationResult.invalidNodes);
                setAvailableIntegrations(
                  validationResult.availableIntegrations,
                );
                setValidationDialogOpen(true);
              }
            } catch (validationError) {
              console.error(
                "[PipelineEditorPage] Error validating integration IDs:",
                validationError,
              );
              // Proceed with import without validation
              // Update ID counter to avoid conflicts with existing nodes
              updateIdCounter(fixedNodes);
              setNodes(fixedNodes);
              setEdges(fixedEdges);

              // Update form data
              const pipelineNodes = fixedNodes.map(convertToPipelineNode);
              const pipelineEdges = fixedEdges.map((edge: any) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                sourceHandle: edge.sourceHandle,
                targetHandle: edge.targetHandle,
                type: edge.type || "custom",
                data: edge.data || { text: "", id: edge.id, type: "custom" },
              }));

              setFormData((prev) => ({
                ...prev,
                configuration: {
                  ...prev.configuration,
                  nodes: pipelineNodes,
                  edges: pipelineEdges,
                },
              }));
            }
          }
        } catch (error) {
          console.error(
            "[PipelineEditorPage] Error initializing from imported flow:",
            error,
          );
        } finally {
          setIsImporting(false);
        }
      }
    };

    loadImportedFlow();
  }, [location.state]);

  // Handle validation dialog confirmation
  const handleValidationConfirm = async (mappings: IntegrationMapping[]) => {
    if (importedFlowData) {
      setIsImporting(true);
      console.log(
        "[PipelineEditorPage] Applying integration mappings:",
        mappings,
      );

      try {
        // Update nodes with new integration IDs
        const updatedPipelineNodes =
          IntegrationValidationService.mapInvalidIntegrationIds(
            importedFlowData.nodes,
            mappings,
          );

        // Convert PipelineNode[] to Node[] for ReactFlow
        const updatedReactFlowNodes = updatedPipelineNodes.map((node: any) => ({
          ...node,
          data: {
            ...node.data,
            // Fix the icon property to ensure it's properly rendered
            icon:
              node.data.icon &&
              typeof node.data.icon === "object" &&
              node.data.icon.props
                ? getNodeIcon(node.data.type)
                : node.data.icon,
          },
          position: {
            x:
              typeof node.position.x === "string"
                ? parseFloat(node.position.x)
                : node.position.x,
            y:
              typeof node.position.y === "string"
                ? parseFloat(node.position.y)
                : node.position.y,
          },
          // Convert other string numbers to actual numbers if needed
          ...(node.positionAbsolute && {
            positionAbsolute: {
              x:
                typeof node.positionAbsolute.x === "string"
                  ? parseFloat(node.positionAbsolute.x)
                  : node.positionAbsolute.x,
              y:
                typeof node.positionAbsolute.y === "string"
                  ? parseFloat(node.positionAbsolute.y)
                  : node.positionAbsolute.y,
            },
          }),
        }));

        // Apply the updated nodes
        // Update ID counter to avoid conflicts with existing nodes
        updateIdCounter(updatedReactFlowNodes);
        setNodes(updatedReactFlowNodes);
        setEdges(importedFlowData.edges);

        // Update form data
        const pipelineNodes = updatedReactFlowNodes.map(convertToPipelineNode);
        setFormData((prev) => ({
          ...prev,
          configuration: {
            ...prev.configuration,
            nodes: pipelineNodes,
            edges: importedFlowData.edges,
          },
        }));
      } catch (error) {
        console.error(
          "[PipelineEditorPage] Error applying integration mappings:",
          error,
        );
      } finally {
        // Close the dialog
        setValidationDialogOpen(false);
        setIsImporting(false);
      }
    }
  };

  // Initialize ReactFlow nodes and edges from pipeline configuration
  React.useEffect(() => {
    // Only initialize if the pipeline has data and hasn't been initialized yet
    if (
      pipeline?.configuration?.nodes &&
      pipeline.configuration.nodes.length > 0 &&
      !pipelineInitialized.current
    ) {
      console.log(
        "[PipelineEditorPage] Initializing ReactFlow from pipeline configuration",
      );
      // Update ID counter to avoid conflicts with existing nodes
      updateIdCounter(pipeline.configuration.nodes);
      console.log(
        "[PipelineEditorPage] Configuration nodes:",
        pipeline.configuration.nodes,
      );
      console.log(
        "[PipelineEditorPage] Configuration edges:",
        pipeline.configuration.edges,
      );

      // Convert configuration nodes to ReactFlow nodes
      const reactFlowNodes = pipeline.configuration.nodes.map((node) => {
        console.log("[PipelineEditorPage] Processing node:", node);
        // Create a ReactFlow node from the pipeline node
        // Direct call to getNodeIcon instead of using useMemo inside map function
        const nodeIcon = getNodeIcon(node.data.type);
        return {
          id: node.id,
          type: node.type || "custom",
          position: {
            x:
              typeof node.position.x === "string"
                ? parseFloat(node.position.x)
                : node.position.x,
            y:
              typeof node.position.y === "string"
                ? parseFloat(node.position.y)
                : node.position.y,
          },
          data: {
            nodeId: node.data.id,
            label: node.data.label,
            description: node.data.description || "", // Use node description if available
            icon: nodeIcon,
            inputTypes: node.data.inputTypes || [],
            outputTypes: node.data.outputTypes || [],
            type: node.data.type,
            configuration: node.data.configuration,
            onDelete: onDeleteNode,
            onConfigure: onConfigureNode,
          },
          // Preserve width and height
          width:
            typeof node.width === "string"
              ? parseFloat(node.width)
              : node.width,
          height:
            typeof node.height === "string"
              ? parseFloat(node.height)
              : node.height,
          // Preserve positionAbsolute if it exists
          ...(node.positionAbsolute && {
            positionAbsolute: {
              x:
                typeof node.positionAbsolute.x === "string"
                  ? parseFloat(node.positionAbsolute.x)
                  : node.positionAbsolute.x,
              y:
                typeof node.positionAbsolute.y === "string"
                  ? parseFloat(node.positionAbsolute.y)
                  : node.positionAbsolute.y,
            },
          }),
          // Preserve dragging and selected states if they exist
          ...(node.dragging !== undefined && { dragging: node.dragging }),
          ...(node.selected !== undefined && { selected: node.selected }),
        };
      });

      console.log("[PipelineEditorPage] ReactFlow nodes:", reactFlowNodes);

      // Set the nodes state
      setNodes(reactFlowNodes);

      // Convert configuration edges to ReactFlow edges
      if (
        pipeline.configuration.edges &&
        pipeline.configuration.edges.length > 0
      ) {
        const reactFlowEdges = pipeline.configuration.edges.map((edge) => {
          console.log("[PipelineEditorPage] Processing edge:", edge);

          // Use type assertion to handle sourceHandle and targetHandle
          const edgeWithHandles = edge as any;

          return {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            type: edge.type || "custom",
            data: edge.data,
            // Include sourceHandle and targetHandle if they exist in the edge data
            ...(edgeWithHandles.sourceHandle && {
              sourceHandle: edgeWithHandles.sourceHandle,
            }),
            ...(edgeWithHandles.targetHandle && {
              targetHandle: edgeWithHandles.targetHandle,
            }),
          };
        });

        console.log("[PipelineEditorPage] ReactFlow edges:", reactFlowEdges);

        // Set the edges state
        setEdges(reactFlowEdges);
      }

      // Mark the pipeline as initialized
      pipelineInitialized.current = true;
      console.log("[PipelineEditorPage] Pipeline initialized");
    }
  }, [pipeline, onDeleteNode, onConfigureNode, setNodes, setEdges]);

  // Update existing nodes with handlers
  React.useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          onDelete: onDeleteNode,
          onConfigure: onConfigureNode,
        },
      })),
    );
  }, [onDeleteNode, onConfigureNode, setNodes]);

  // Handle edge reconnection start
  const onReconnectStart = useCallback(() => {
    edgeReconnectSuccessful.current = false;
  }, []);

  // Handle successful edge reconnection
  const onReconnect = useCallback(
    (oldEdge, newConnection) => {
      edgeReconnectSuccessful.current = true;
      setEdges((els) => reconnectEdge(oldEdge, newConnection, els));

      // Update pipeline configuration with the reconnected edge
      setFormData((prev) => {
        const updatedEdges = prev.configuration.edges.map((edge) => {
          if (edge.id === oldEdge.id) {
            return {
              ...edge,
              source: newConnection.source,
              target: newConnection.target,
              sourceHandle: newConnection.sourceHandle,
              targetHandle: newConnection.targetHandle,
            };
          }
          return edge;
        });

        return {
          ...prev,
          configuration: {
            ...prev.configuration,
            edges: updatedEdges,
          },
        };
      });
    },
    [setEdges],
  );

  // Handle edge reconnection end - delete edge if reconnection failed
  const onReconnectEnd = useCallback(
    (_, edge) => {
      if (!edgeReconnectSuccessful.current) {
        // Remove the edge from the edges state
        setEdges((eds) => eds.filter((e) => e.id !== edge.id));

        // Also remove the edge from the pipeline configuration
        setFormData((prev) => ({
          ...prev,
          configuration: {
            ...prev.configuration,
            edges: prev.configuration.edges.filter((e) => e.id !== edge.id),
          },
        }));
      }

      // Reset the flag
      edgeReconnectSuccessful.current = true;
    },
    [setEdges],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const targetNode = nodes.find((node) => node.id === connection.target);

      // Prevent connections to trigger nodes
      if (targetNode?.data.type?.includes("TRIGGER")) {
        setErrorType("trigger");
        setIsErrorModalOpen(true);
        return;
      }

      // DO NOT DELETE - Input/Output validation will be enabled later
      /*
            const sourceNode = nodes.find((node) => node.id === connection.source);
            if (sourceNode && targetNode) {
                const isCompatible =
                    sourceNode.data.outputTypes &&
                    targetNode.data.inputTypes &&
                    sourceNode.data.outputTypes.some((outputType: string) =>
                        targetNode.data.inputTypes.includes(outputType)
                    );

                if (!isCompatible) {
                    setIsErrorModalOpen(true);
                    return;
                }
            }
            */

      const newEdge = {
        ...connection,
        id: `${connection.source}-${connection.target}`,
        type: "custom",
        data: {
          text: "Connected",
        },
      } as PipelineEdge;

      setEdges((eds) => addEdge(newEdge, eds));

      // Update pipeline configuration
      setFormData((prev) => ({
        ...prev,
        configuration: {
          ...prev.configuration,
          edges: [...prev.configuration.edges, newEdge],
        },
      }));
    },
    [nodes, setEdges],
  );

  const onDrop = useCallback(
    async (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowWrapper.current) return;

      const nodeData = JSON.parse(
        event.dataTransfer.getData("application/reactflow"),
      );
      console.log(nodeData);
      if (typeof nodeData === "undefined" || !nodeData) {
        return;
      }

      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = screenToFlowPosition({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      // Ensure ID counter is up to date with current nodes to prevent conflicts
      updateIdCounter(nodes);

      // Check if this is our special job status node
      // const isJobStatusNode = nodeData.customNodeType === 'jobStatusNode';

      const newReactFlowNode: Node<CustomNodeData> = {
        id: getId(),
        type: "custom", // Removed jobStatusNode type
        position,
        data: {
          nodeId: nodeData.id,
          label: nodeData.label || "New Node",
          description: nodeData.description || "",
          icon: nodeData.icon || getNodeIcon(nodeData.type?.toUpperCase()),
          inputTypes: nodeData.inputTypes || [],
          outputTypes: nodeData.outputTypes || [],
          type: nodeData.type?.toUpperCase(),
          configuration: nodeData.methodConfig || {
            method: "",
            path: "",
            parameters: {},
            operationId: "",
            requestMapping: "",
            responseMapping: "",
          },
        },
      };

      const newPipelineNode = convertToPipelineNode(newReactFlowNode);

      // Update the node with handlers before adding it
      const nodeWithHandlers = {
        ...newReactFlowNode,
        data: {
          ...newReactFlowNode.data,
          onDelete: onDeleteNode,
          onConfigure: onConfigureNode,
        },
      };

      // Update nodes and pipeline configuration as before
      setNodes((nds) => nds.concat(nodeWithHandlers));

      setFormData((prev) => ({
        ...prev,
        configuration: {
          ...prev.configuration,
          nodes: [...prev.configuration.nodes, newPipelineNode],
          settings: prev.configuration.settings || {
            autoStart: false,
            retryAttempts: 3,
            timeout: 3600,
          },
        },
      }));

      // Determine whether configuration parameters exist
      const parameters = newReactFlowNode.data.configuration?.parameters;
      const hasParameters = parameters && Object.keys(parameters).length > 0;

      console.log("[PipelineEditorPage] Node configuration check:", {
        nodeId: nodeData.id,
        nodeType: nodeData.type,
        configuration: newReactFlowNode.data.configuration,
        parameters: parameters,
        hasParameters: hasParameters,
        parameterKeys: parameters ? Object.keys(parameters) : [],
      });

      if (hasParameters) {
        // If parameters exist, open the configuration dialog
        console.log(
          "[PipelineEditorPage] Opening configuration dialog for node:",
          nodeData.id,
        );
        setSelectedNode(nodeWithHandlers);
        setIsNodeConfigOpen(true);
      } else {
        // No configuration needed—skip opening the dialog
        console.log(
          "[PipelineEditorPage] Node has no configuration parameters; skipping config dialog for:",
          nodeData.id,
        );
      }

      // setNodes((nds) => nds.concat(nodeWithHandlers));

      // // Update pipeline configuration
      // setFormData(prev => ({
      //     ...prev,
      //     configuration: {
      //         ...prev.configuration,
      //         nodes: [...prev.configuration.nodes, newPipelineNode],
      //         settings: prev.configuration.settings || {
      //             autoStart: false,
      //             retryAttempts: 3,
      //             timeout: 3600
      //         }
      //     }
      // }));

      // // Automatically open configuration dialog for the new node
      // setSelectedNode(nodeWithHandlers);
      // setIsNodeConfigOpen(true);
    },
    [screenToFlowPosition, setNodes, onDeleteNode, onConfigureNode],
  );

  const handleNodeConfigClose = useCallback(() => {
    setIsNodeConfigOpen(false);
    setSelectedNode(null);
  }, []);

  const handleNodeConfigSave = useCallback(
    async (configuration: any) => {
      console.log(
        "[PipelineEditorPage] handleNodeConfigSave called with:",
        configuration,
      );
      console.log(
        "[PipelineEditorPage] Configuration JSON:",
        JSON.stringify(configuration),
      );
      try {
        if (selectedNode) {
          console.log("[PipelineEditorPage] Selected node:", selectedNode);
          // Update node in ReactFlow

          const updatedNode = {
            ...selectedNode,
            data: {
              ...selectedNode.data,
              configuration,
              label: configuration.method
                ? `${selectedNode.data.label} (${configuration.method})`
                : selectedNode.data.label,
            },
          };

          console.log("[PipelineEditorPage] Updated node:", updatedNode);
          console.log(
            "[PipelineEditorPage] Updated node configuration:",
            updatedNode.data.configuration,
          );

          // Update ReactFlow state
          setNodes((nds) => {
            console.log("[PipelineEditorPage] Current nodes:", nds);
            const updatedNodes = nds.map((node) =>
              node.id === selectedNode.id ? updatedNode : node,
            );
            console.log("[PipelineEditorPage] Updated nodes:", updatedNodes);
            return updatedNodes;
          });
          console.log("[PipelineEditorPage] Nodes updated");

          // Convert to pipeline node format and update form data
          const updatedPipelineNode = convertToPipelineNode(updatedNode);
          console.log(
            "[PipelineEditorPage] Updated pipeline node:",
            updatedPipelineNode,
          );
          console.log(
            "[PipelineEditorPage] Updated pipeline node data:",
            updatedPipelineNode.data,
          );

          // Update pipeline configuration in form data
          setFormData((prev) => {
            console.log("[PipelineEditorPage] Previous form data:", prev);
            const updatedNodes = prev.configuration.nodes.map((node) =>
              node.id === selectedNode.id ? updatedPipelineNode : node,
            );
            console.log(
              "[PipelineEditorPage] Updated nodes in form data:",
              updatedNodes,
            );

            const newFormData = {
              ...prev,
              configuration: {
                ...prev.configuration,
                nodes: updatedNodes,
                settings: prev.configuration.settings || {
                  autoStart: false,
                  retryAttempts: 3,
                  timeout: 3600,
                },
              },
            };
            console.log("[PipelineEditorPage] New form data:", newFormData);
            return newFormData;
          });
          console.log("[PipelineEditorPage] Form data updated");
        }

        // Close the dialog
        console.log("[PipelineEditorPage] Closing node config dialog");
        handleNodeConfigClose();
      } catch (error) {
        console.error(
          "[PipelineEditorPage] Error saving node configuration:",
          error,
        );
        // Don't close the dialog on error so the user can try again
      }
    },
    [selectedNode, setNodes, handleNodeConfigClose],
  );

  // Function to get the appropriate icon based on node type
  const getNodeIcon = (nodeType: string | undefined) => {
    if (!nodeType) return <FaFileVideo size={20} />;

    const type = nodeType?.toUpperCase() || "";

    if (type.includes("TRIGGER")) {
      return <FaBolt size={20} />;
    } else if (type.includes("FLOW")) {
      return <FaCodeBranch size={20} />;
    } else if (type.includes("UTILITY")) {
      return <FaTools size={20} />;
    } else if (type.includes("INTEGRATION")) {
      return <FaPlug size={20} />;
    }

    // Default icon for other types
    return <FaCogs size={20} />;
  };

  const stableIcon = useMemo(() => <FaFileVideo size={20} />, []);

  const convertNodeToReactFlowNode = (
    node: NodeType,
  ): Node<CustomNodeData> => ({
    id: node.nodeId || getId(),
    type: "custom",
    position: { x: 0, y: 0 },
    data: {
      nodeId: node.nodeId || "",
      label: node.info.title,
      description: node.info.description || "",
      icon: getNodeIcon(node.info.nodeType),
      inputTypes: node.info.inputTypes || [],
      outputTypes: node.info.outputTypes || [],
      configuration: null,
    },
  });

  return (
    <Box
      sx={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        margin: 0,
        padding: 0,
      }}
    >
      {/* Loading Backdrop */}
      <Backdrop
        sx={{
          color: "#fff",
          zIndex: (theme) => theme.zIndex.drawer + 1,
          flexDirection: "column",
          gap: 2,
        }}
        open={isImporting}
      >
        <CircularProgress color="inherit" />
        <Box sx={{ typography: "body1", fontWeight: "medium" }}>
          Importing Pipeline...
        </Box>
      </Backdrop>
      <PipelineToolbar
        onSave={handleSave}
        isLoading={createPipeline.isPending || updatePipeline.isPending}
        pipelineName={formData.name}
        onPipelineNameChange={(value) =>
          setFormData((prev) => ({ ...prev, name: value }))
        }
        reactFlowInstance={reactFlowInstance}
        setNodes={setNodes}
        setEdges={setEdges}
        active={formData.active !== undefined ? formData.active : true}
        onActiveChange={handleActiveChange}
        status={pipeline?.deploymentStatus}
        isEditMode={!!pipelineId && pipelineId !== "new"}
        updateFormData={(importedNodes, importedEdges) => {
          // Convert imported React Flow nodes to pipeline nodes
          const pipelineNodes = importedNodes.map((node) =>
            convertToPipelineNode(node),
          );

          // Convert imported React Flow edges to pipeline edges
          const pipelineEdges = importedEdges.map((edge) => ({
            id: edge.id || `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: edge.type || "custom",
            data: edge.data || { text: "Connected" },
            // Include sourceHandle and targetHandle if they exist
            ...(edge.sourceHandle && { sourceHandle: edge.sourceHandle }),
            ...(edge.targetHandle && { targetHandle: edge.targetHandle }),
          })) as PipelineEdge[];

          // Check if the imported flow has an active property
          const importedActive =
            importedNodes.length > 0 &&
            importedNodes[0].data &&
            importedNodes[0].data.flow &&
            importedNodes[0].data.flow.active !== undefined
              ? importedNodes[0].data.flow.active
              : undefined;

          // Update formData with imported nodes and edges
          setFormData((prev) => ({
            ...prev,
            // Preserve active property from imported flow if available, otherwise keep current value
            active: importedActive !== undefined ? importedActive : prev.active,
            configuration: {
              ...prev.configuration,
              nodes: pipelineNodes,
              edges: pipelineEdges,
              settings: prev.configuration.settings || {
                autoStart: false,
                retryAttempts: 3,
                timeout: 3600,
              },
            },
          }));
          console.log(
            "[PipelineEditorPage] Updated formData with imported pipeline",
          );
          console.log(
            "[PipelineEditorPage] Imported nodes:",
            pipelineNodes.length,
          );
          console.log(
            "[PipelineEditorPage] Imported edges:",
            pipelineEdges.length,
          );
          console.log(
            "[PipelineEditorPage] Updated formData with imported pipeline",
          );
        }}
        onDelete={
          pipelineId && pipelineId !== "new"
            ? () => {
                // Open delete dialog
                setDeleteDialog({
                  open: true,
                  pipelineId: pipelineId,
                  pipelineName: formData.name,
                  userInput: "",
                });
              }
            : undefined
        }
      />
      <Box
        sx={{
          position: "fixed",
          overflow: "hidden",
          height: "calc(100vh - 64px)",
          width: "100%",
          left: 0,
          top: 64,
          right: 0,
          bottom: 0,
        }}
      >
        <Box
          sx={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: isExpanded ? "300px" : "0px",
            transition: (theme) =>
              theme.transitions.create(["width"], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
            zIndex: 2,
          }}
        >
          <Sidebar />
        </Box>
        <Box
          ref={reactFlowWrapper}
          sx={{
            position: "absolute",
            left: 0,
            top: 0,
            right: isExpanded ? "300px" : 0,
            bottom: 0,
            transition: (theme) =>
              theme.transitions.create(["right"], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
            zIndex: 1,
          }}
        >
          <ReactFlow
            style={{
              width: "100%",
              height: "100%",
              margin: 0,
              padding: 0,
              position: "absolute",
              left: 0,
              top: 0,
              right: 0,
              bottom: 0,
            }}
            defaultViewport={{ x: 0, y: 0, zoom: 1 }}
            minZoom={0.1}
            maxZoom={4}
            snapToGrid={true}
            snapGrid={[16, 16]}
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onReconnectStart={onReconnectStart}
            onReconnect={onReconnect}
            onReconnectEnd={onReconnectEnd}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onDrop={onDrop}
            onDragOver={(event) => event.preventDefault()}
            fitView={false}
            connectionRadius={100}
            connectOnClick={true}
          >
            <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </Box>
      </Box>

      {/* Integration Validation Dialog */}
      <IntegrationValidationDialog
        open={validationDialogOpen}
        invalidNodes={invalidNodes}
        availableIntegrations={availableIntegrations}
        onClose={() => setValidationDialogOpen(false)}
        onConfirm={handleValidationConfirm}
      />

      <Dialog
        open={isNodeConfigOpen}
        onClose={(event, reason) => {
          // Prevent closing on backdrop click or escape key
          if (reason === "backdropClick" || reason === "escapeKeyDown") {
            return;
          }
          setIsNodeConfigOpen(false);
        }}
        maxWidth="sm"
        PaperProps={{
          sx: {
            width: "400px",
          },
        }}
        disableEscapeKeyDown
      >
        <DialogTitle>Configure Node</DialogTitle>
        <DialogContent>
          {selectedNode && !isNodeDetailsLoading && nodeDetails && (
            <NodeConfigurationForm
              node={convertedNodeData}
              configuration={selectedNode.data.configuration}
              onSubmit={handleNodeConfigSave}
              onCancel={() => setIsNodeConfigOpen(false)}
            />
          )}
          {isNodeDetailsLoading && (
            <Box sx={{ p: 2, textAlign: "center" }}>
              <Typography>Loading node configuration...</Typography>
            </Box>
          )}
        </DialogContent>
      </Dialog>

      <Modal
        open={isErrorModalOpen}
        onClose={() => setIsErrorModalOpen(false)}
        aria-labelledby="modal-modal-title"
        aria-describedby="modal-modal-description"
      >
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 400,
            bgcolor: "background.paper",
            boxShadow: 24,
            p: 4,
          }}
        >
          <Typography id="modal-modal-title" variant="h6" component="h2">
            Connection Error
          </Typography>
          <Typography id="modal-modal-description" sx={{ mt: 2 }}>
            {errorType === "trigger"
              ? "Trigger nodes cannot have incoming connections. They can only trigger other nodes."
              : "The nodes cannot be connected because their input/output types are not compatible."}
          </Typography>
        </Box>
      </Modal>

      {/* API Status Modal */}
      <ApiStatusModal
        open={apiStatusModalOpen}
        onClose={handleApiStatusModalClose}
        status={apiStatusModalState}
        action={apiStatusModalAction}
        message={apiStatusModalMessage}
      />

      {/* Pipeline Delete Dialog */}
      <PipelineDeleteDialog
        open={deleteDialog.open}
        pipelineName={deleteDialog.pipelineName}
        userInput={deleteDialog.userInput}
        onClose={() => setDeleteDialog((prev) => ({ ...prev, open: false }))}
        onConfirm={() => {
          // Close the dialog first to prevent UI freezing
          setDeleteDialog((prev) => ({ ...prev, open: false }));

          // Show loading modal
          setApiStatusModalState("loading");
          setApiStatusModalAction("Deleting Pipeline");
          setApiStatusModalMessage("");
          setApiStatusModalOpen(true);

          // Use the PipelinesService to delete the pipeline
          import("../api/pipelinesService").then(({ PipelinesService }) => {
            PipelinesService.deletePipeline(deleteDialog.pipelineId)
              .then(() => {
                // Show success message
                setApiStatusModalState("success");
                setApiStatusModalAction("Pipeline Deleted");
                setApiStatusModalMessage(
                  "The pipeline has been deleted successfully.",
                );

                // Navigate back to pipelines page after a short delay
                setTimeout(() => {
                  navigate("/settings/pipelines");
                }, 1500);
              })
              .catch((error) => {
                // Show error message
                setApiStatusModalState("error");
                setApiStatusModalAction("Delete Failed");
                setApiStatusModalMessage(
                  error.message ||
                    "An error occurred while deleting the pipeline.",
                );
              });
          });
        }}
        onUserInputChange={(input) =>
          setDeleteDialog((prev) => ({ ...prev, userInput: input }))
        }
        isDeleting={false}
      />

      {/* Pipeline Update Confirmation Dialog */}
      <PipelineUpdateConfirmationDialog
        open={updateConfirmationOpen}
        onClose={() => setUpdateConfirmationOpen(false)}
        onConfirm={() => {
          setUpdateConfirmationOpen(false);
          proceedWithSave();
        }}
      />
    </Box>
  );
};

const PipelineEditorPage = () => (
  <RightSidebarProvider>
    <ReactFlowProvider>
      <PipelineEditorContent />
    </ReactFlowProvider>
  </RightSidebarProvider>
);

export default PipelineEditorPage;
