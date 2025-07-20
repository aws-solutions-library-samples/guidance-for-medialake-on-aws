import React, { useState, useMemo } from "react";
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useGetUnconfiguredNodeMethods } from "@/shared/nodes/api/nodesController";
import { Node as NodeType } from "@/shared/nodes/types/nodes.types";
import { RightSidebar } from "@/components/common/RightSidebar/RightSidebar";
// import { createJobStatusNodeData } from './jobStatusNodeUtils';

interface NodeSection {
  title: string;
  types: string[];
  nodes: Array<{ node: NodeType; methodName: string; method: any }>;
}

const SidebarContent: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSections, setExpandedSections] = useState<string[]>([
    "TRIGGER",
  ]);
  const {
    data: nodesResponse,
    isLoading,
    error,
  } = useGetUnconfiguredNodeMethods();

  const handleSectionToggle = (sectionId: string) => {
    setExpandedSections((prev) => {
      if (prev.includes(sectionId)) {
        return prev.filter((type) => type !== sectionId);
      }
      return [...prev, sectionId];
    });
  };

  const onDragStart = (
    event: React.DragEvent,
    node: NodeType,
    methodName: string,
  ) => {
    console.log(
      "[Sidebar] onDragStart for node:",
      node.nodeId,
      "method:",
      methodName,
    );
    console.log("[Sidebar] Node methods:", node.methods);

    // For trigger nodes, we need to use "trigger" as the method name
    let actualMethodName = methodName;
    if (node.info.nodeType === "TRIGGER") {
      actualMethodName = "trigger";
      console.log('[Sidebar] Using "trigger" as method name for trigger node');
    } else if (node.info.nodeType === "INTEGRATION") {
      // For integration nodes, we need to use the actual method name (post, get, etc.)
      // The methodName parameter might be an index, so we need to get the actual method name
      if (Array.isArray(node.methods)) {
        const methodObj = node.methods[parseInt(methodName)] as any;
        if (methodObj && methodObj.name) {
          actualMethodName = methodObj.name;
          console.log(
            "[Sidebar] Using method name from array:",
            actualMethodName,
          );
        }
      } else if (typeof node.methods === "object") {
        // If methods is an object, the keys might be the method names
        // But we need to check if the value has a name property
        const methodObj = node.methods[methodName] as any;
        if (methodObj && methodObj.name) {
          actualMethodName = methodObj.name;
          console.log(
            "[Sidebar] Using method name from object:",
            actualMethodName,
          );
        }
      }
    }

    // Extract operationId from methodName if it's in the format "name:operationId"
    let targetOperationId: string | undefined;
    if (methodName.includes(":")) {
      const parts = methodName.split(":");
      actualMethodName = parts[0];
      targetOperationId = parts[1];
      console.log(
        "[Sidebar] Extracted operationId from methodName:",
        targetOperationId,
      );
    }

    // Find the method in the methods array or object
    let method;
    if (Array.isArray(node.methods)) {
      // If we have an operationId, use it to find the exact method
      if (targetOperationId) {
        method = node.methods.find(
          (m: any) =>
            m.name === actualMethodName &&
            m.config?.operationId === targetOperationId,
        );
        console.log(
          "[Sidebar] Finding method by name and operationId:",
          actualMethodName,
          targetOperationId,
        );
      }

      // If no method found with operationId or no operationId provided, fall back to name only
      if (!method) {
        method = node.methods.find((m: any) => m.name === actualMethodName);
        console.log("[Sidebar] Finding method by name only:", actualMethodName);
      }

      // If still not found and methodName is a number, use it as an index
      if (!method && !isNaN(parseInt(methodName))) {
        method = node.methods[parseInt(methodName)];
        console.log("[Sidebar] Using method at index:", methodName);
      }
    } else if (typeof node.methods === "object") {
      method = node.methods[methodName];
      if (!method) {
        // Try to find by name in the object values
        const methods = Object.values(node.methods);

        // If we have an operationId, use it to find the exact method
        if (targetOperationId) {
          method = methods.find(
            (m: any) =>
              m.name === actualMethodName &&
              m.config?.operationId === targetOperationId,
          );
        } else {
          method = methods.find((m: any) => m.name === actualMethodName);
        }
      }
    }

    // Use type assertion to access the config property
    const methodWithConfig = method as any;
    console.log("[Sidebar] Method found:", methodWithConfig);

    // Set methodConfig based on node type
    let methodConfig;
    if (node.info.nodeType === "TRIGGER") {
      // For trigger nodes, use the method name as the method
      // and get parameters from the config.parameters array
      methodConfig = {
        method: actualMethodName,
        parameters:
          methodWithConfig?.config?.parameters?.reduce(
            (acc: any, param: any) => {
              acc[param.name] = ""; // Initialize with empty values
              return acc;
            },
            {},
          ) || {},
        requestMapping: null,
        responseMapping: null,
        path: "",
        operationId: "",
      };
      console.log("[Sidebar] Trigger node methodConfig:", methodConfig);
    } else {
      // For integration nodes, use the method name (post, get, etc.)
      methodConfig = {
        method: actualMethodName,
        parameters: methodWithConfig?.config?.parameters || {},
        requestMapping: methodWithConfig?.config?.requestMapping,
        responseMapping: methodWithConfig?.config?.responseMapping,
        path: methodWithConfig?.config?.path,
        operationId: methodWithConfig?.config?.operationId,
      };
      // console.log('[Sidebar] Integration node methodConfig:', methodConfig);
    }

    // Check if this node has multiple output types in its connections
    let outputTypes = node.info.outputTypes || [];
    let inputTypes = node.info.inputTypes || [];

    // console.log('[Sidebar] Node ID:', node.nodeId);
    // console.log('[Sidebar] Node type:', node.info.nodeType);
    // console.log('[Sidebar] Initial outputTypes:', outputTypes);
    // console.log('[Sidebar] Initial inputTypes:', inputTypes);
    // console.log('[Sidebar] Node connections:', node.connections);

    // // For nodes with multiple outputs like Choice, extract the output types from connections
    // console.log('[Sidebar] Checking for multiple outputs in node:', node.nodeId);

    // Log all connections for debugging
    // if (node.connections) {
    //     console.log('[Sidebar] Node connections structure:', JSON.stringify(node.connections, null, 2));
    // }

    // Try to find the output types in different possible locations
    let outputTypesConfig;
    let inputTypesConfig;

    // Check for output types in the standard location first
    if (
      node.connections?.outgoing?.[actualMethodName]?.[0]?.connectionConfig
        ?.type
    ) {
      outputTypesConfig =
        node.connections.outgoing[actualMethodName][0].connectionConfig.type;
      console.log(
        "[Sidebar] Found output types in standard location:",
        outputTypesConfig,
      );
    }
    // If not found, try to look in all outgoing connections
    else if (node.connections?.outgoing) {
      // Look through all methods in outgoing connections
      Object.entries(node.connections.outgoing).forEach(
        ([method, connections]) => {
          if (Array.isArray(connections) && connections.length > 0) {
            connections.forEach((connection: any) => {
              if (connection.connectionConfig?.type) {
                outputTypesConfig = connection.connectionConfig.type;
                console.log(
                  "[Sidebar] Found output types in method:",
                  method,
                  outputTypesConfig,
                );
              }
            });
          }
        },
      );
    }

    // Check for input types in the standard location first
    if (
      node.connections?.incoming?.[actualMethodName]?.[0]?.connectionConfig
        ?.type
    ) {
      inputTypesConfig =
        node.connections.incoming[actualMethodName][0].connectionConfig.type;
      console.log(
        "[Sidebar] Found input types in standard location:",
        inputTypesConfig,
      );
    }
    // If not found, try to look in all incoming connections
    else if (node.connections?.incoming) {
      // Look through all methods in incoming connections
      Object.entries(node.connections.incoming).forEach(
        ([method, connections]) => {
          if (Array.isArray(connections) && connections.length > 0) {
            connections.forEach((connection: any) => {
              if (connection.connectionConfig?.type) {
                inputTypesConfig = connection.connectionConfig.type;
                console.log(
                  "[Sidebar] Found input types in method:",
                  method,
                  inputTypesConfig,
                );
              }
            });
          }
        },
      );
    }

    // If we found output types, use them
    if (outputTypesConfig) {
      // Check if outputTypesConfig is an array of strings or objects
      if (Array.isArray(outputTypesConfig) && outputTypesConfig.length > 0) {
        if (typeof outputTypesConfig[0] === "string") {
          // If it's an array of strings, convert each string to an object with name property
          outputTypes = outputTypesConfig.map((type: string) => ({
            name: type,
            description: `Output type: ${type}`,
          }));
        } else if (
          typeof outputTypesConfig[0] === "object" &&
          outputTypesConfig[0] !== null
        ) {
          // If it's already an array of objects, use as is if they have name property
          // or create objects with name property if they don't
          outputTypes = outputTypesConfig.map((type: any) => {
            if (type.name) {
              return {
                name: type.name,
                description: type.description,
              };
            } else {
              // If the object doesn't have a name property, use a default
              return {
                name: "output",
                description: "Default output type",
              };
            }
          });
        }
      }
      console.log("[Sidebar] Node has multiple output types:", outputTypes);
    }

    // If we found input types, use them
    if (inputTypesConfig) {
      // For inputTypes, we need to keep it as a string array
      if (Array.isArray(inputTypesConfig) && inputTypesConfig.length > 0) {
        if (typeof inputTypesConfig[0] === "string") {
          // If it's already an array of strings, use it directly
          inputTypes = inputTypesConfig;
        } else if (
          typeof inputTypesConfig[0] === "object" &&
          inputTypesConfig[0] !== null
        ) {
          // If it's an array of objects, extract the name property
          inputTypes = inputTypesConfig.map((type: any) => {
            if (type.name) {
              return type.name;
            } else {
              return "input";
            }
          });
        }
      }
      console.log("[Sidebar] Node has multiple input types:", inputTypes);
    }

    const nodeData = {
      id: node.nodeId,
      type: node.info.nodeType,
      label: node.info.title,
      description: method?.description || node.info.description,
      inputTypes: inputTypes,
      outputTypes: outputTypes,
      methods: node.methods || {},
      icon: node.info.iconUrl,
      selectedMethod: actualMethodName,
      methodConfig: methodConfig,
    };

    console.log("[Sidebar] Final node data for drag:", nodeData);

    console.log("[Sidebar] Node data for drag:", nodeData);

    event.dataTransfer.setData(
      "application/reactflow",
      JSON.stringify(nodeData),
    );
    event.dataTransfer.effectAllowed = "move";
  };

  // Handler for dragging the custom job status node
  // const onDragStartJobStatus = (event: React.DragEvent) => {
  //     const nodeData = createJobStatusNodeData();
  //     event.dataTransfer.setData('application/reactflow', JSON.stringify({
  //         ...nodeData,
  //         customNodeType: 'jobStatusNode' // This helps identify it as a special node type
  //     }));
  //     event.dataTransfer.effectAllowed = 'move';
  // };

  const sections = useMemo(() => {
    if (!nodesResponse?.data) return [];

    const groupedNodes: NodeSection[] = [
      { title: "Triggers", types: ["TRIGGER"], nodes: [] },
      { title: "Integrations", types: ["INTEGRATION"], nodes: [] },
      { title: "Flow", types: ["FLOW"], nodes: [] },
      { title: "Utilities", types: ["UTILITY"], nodes: [] },
    ];

    nodesResponse.data.forEach((node) => {
      if (node.methods) {
        // For integration nodes with multiple methods with the same name,
        // we need to use the operationId to distinguish between them
        if (
          node.info.nodeType === "INTEGRATION" &&
          Array.isArray(node.methods)
        ) {
          // Group methods by name to check for duplicates
          const methodsByName: Record<string, any[]> = {};

          node.methods.forEach((method: any, index: number) => {
            if (!methodsByName[method.name]) {
              methodsByName[method.name] = [];
            }
            methodsByName[method.name].push({ method, index });
          });

          // For each group of methods with the same name
          Object.entries(methodsByName).forEach(([name, methods]) => {
            const nodeType = node.info.nodeType;
            const section = groupedNodes.find((s) =>
              s.types.some((type) => nodeType.includes(type)),
            );

            if (section) {
              // If there's only one method with this name, use the index as methodName
              if (methods.length === 1) {
                section.nodes.push({
                  node,
                  methodName: methods[0].index.toString(),
                  method: methods[0].method,
                });
              } else {
                // If there are multiple methods with the same name, use name:operationId format
                methods.forEach(({ method, index }) => {
                  const operationId = method.config?.operationId;
                  const uniqueMethodName = operationId
                    ? `${name}:${operationId}`
                    : index.toString();

                  section.nodes.push({
                    node,
                    methodName: uniqueMethodName,
                    method,
                  });
                });
              }
            }
          });
        } else {
          // For non-integration nodes or nodes with object methods, use the original logic
          Object.entries(node.methods).forEach(([methodName, method]) => {
            const nodeType = node.info.nodeType;
            const section = groupedNodes.find((s) =>
              s.types.some((type) => nodeType.includes(type)),
            );

            if (section) {
              section.nodes.push({ node, methodName: method.name, method });
            }
          });
        }
      }
    });

    return groupedNodes;
  }, [nodesResponse?.data]);

  const filteredSections = useMemo(() => {
    return sections.map((section) => ({
      ...section,
      nodes: section.nodes.filter(({ node, method }) => {
        const searchLower = searchQuery.toLowerCase();
        return (
          node.info.title.toLowerCase().includes(searchLower) ||
          (method.description || node.info.description)
            .toLowerCase()
            .includes(searchLower)
        );
      }),
    }));
  }, [sections, searchQuery]);

  if (isLoading) {
    return (
      <Box
        sx={{
          p: 2,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error || !nodesResponse?.data) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">
          Failed to load nodes. Please try again later.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ pt: 2 }}>
      <Box sx={{ px: 2, mb: 2 }}>
        <Typography
          variant="h6"
          gutterBottom
          sx={{ textAlign: "center", mb: 2 }}
        >
          Available Nodes
        </Typography>

        <TextField
          fullWidth
          size="small"
          placeholder="Search nodes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </Box>

      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          "& .MuiAccordion-root + .MuiAccordion-root": {
            mt: -1,
          },
        }}
      >
        {filteredSections.map((section) => (
          <Accordion
            key={section.types[0]}
            expanded={expandedSections.includes(section.types[0])}
            onChange={() => handleSectionToggle(section.types[0])}
            disableGutters
            sx={{
              "&.MuiAccordion-root": {
                boxShadow: "none",
                "&:before": {
                  display: "none",
                },
                width: "100%",
                margin: 0,
              },
            }}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon sx={{ fontSize: "0.9rem" }} />}
              sx={{
                minHeight: "36px",
                py: 0,
                px: 2,
                backgroundColor: "background.default",
                borderBottom: "1px solid",
                borderColor: "divider",
                width: "100%",
                margin: 0,
                "& .MuiAccordionSummary-content": {
                  margin: "6px 0",
                },
              }}
            >
              <Typography
                sx={{
                  fontWeight: 500,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  fontSize: "0.75rem",
                  color: "text.secondary",
                }}
              >
                {section.title}
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 2 }}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {/* If this is the Utilities section, add our custom Job Status node */}
                {/* {section.types[0] === 'UTILITY' && (
                                    <Paper
                                        elevation={2}
                                        draggable
                                        sx={{
                                            p: 2,
                                            cursor: 'grab',
                                            '&:hover': {
                                                backgroundColor: 'action.hover',
                                            },
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: 1,
                                        }}
                                    >
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography variant="subtitle1">
                                                Check Job Status
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            Checks the status of a job and routes based on completion status
                                        </Typography>
                                    </Paper>
                                )} */}

                {/* Render existing nodes */}
                {section.nodes.map(({ node, methodName, method }) => (
                  <Paper
                    key={`${node.nodeId}-${methodName}`}
                    elevation={2}
                    onDragStart={(event) =>
                      onDragStart(event, node, methodName)
                    }
                    draggable
                    sx={{
                      p: 2,
                      cursor: "grab",
                      "&:hover": {
                        backgroundColor: "action.hover",
                      },
                      display: "flex",
                      flexDirection: "column",
                      gap: 1,
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Typography variant="subtitle1">
                        {node.info.title}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {method.description || node.info.description}
                    </Typography>
                  </Paper>
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    </Box>
  );
};

const Sidebar: React.FC = () => {
  return (
    <RightSidebar>
      <SidebarContent />
    </RightSidebar>
  );
};

export default Sidebar;
