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
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import VideocamIcon from "@mui/icons-material/Videocam";
import BoltIcon from "@mui/icons-material/Bolt";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import BuildIcon from "@mui/icons-material/Build";
import PowerIcon from "@mui/icons-material/Power";
import SettingsIcon from "@mui/icons-material/Settings";
import { useTranslation } from "react-i18next";
import { useGetUnconfiguredNodeMethods } from "@/shared/nodes/api/nodesController";
import { Node as NodeType } from "@/shared/nodes/types/nodes.types";
import { RightSidebar } from "@/components/common/RightSidebar/RightSidebar";
import { useRightSidebar } from "@/components/common/RightSidebar/SidebarContext";

interface NodeSection {
  title: string;
  types: string[];
  nodes: Array<{ node: NodeType; methodName: string; method: any }>;
}

const SidebarContent: React.FC = () => {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSections, setExpandedSections] = useState<string[]>(["TRIGGER"]);
  const [manuallyExpandedSections, setManuallyExpandedSections] = useState<string[]>(["TRIGGER"]);
  const { data: nodesResponse, isLoading, error } = useGetUnconfiguredNodeMethods();

  // Function to get the appropriate icon based on node type
  const getNodeIcon = (nodeType: string | undefined) => {
    if (!nodeType) return <VideocamIcon sx={{ fontSize: 20 }} />;

    const type = nodeType?.toUpperCase() || "";

    if (type.includes("TRIGGER")) {
      return <BoltIcon sx={{ fontSize: 20 }} />;
    } else if (type.includes("FLOW")) {
      return <AccountTreeIcon sx={{ fontSize: 20 }} />;
    } else if (type.includes("UTILITY")) {
      return <BuildIcon sx={{ fontSize: 20 }} />;
    } else if (type.includes("INTEGRATION")) {
      return <PowerIcon sx={{ fontSize: 20 }} />;
    }

    // Default icon for other types
    return <SettingsIcon sx={{ fontSize: 20 }} />;
  };

  const handleSectionToggle = (sectionId: string) => {
    setManuallyExpandedSections((prev) => {
      if (prev.includes(sectionId)) {
        return prev.filter((type) => type !== sectionId);
      }
      return [...prev, sectionId];
    });

    setExpandedSections((prev) => {
      if (prev.includes(sectionId)) {
        return prev.filter((type) => type !== sectionId);
      }
      return [...prev, sectionId];
    });
  };

  const onDragStart = (event: React.DragEvent, node: NodeType, methodName: string) => {
    // For trigger nodes, we need to use "trigger" as the method name
    let actualMethodName = methodName;
    if (node.info.nodeType === "TRIGGER") {
      actualMethodName = "trigger";
    } else if (node.info.nodeType === "INTEGRATION") {
      // For integration nodes, we need to use the actual method name (post, get, etc.)
      // The methodName parameter might be an index, so we need to get the actual method name
      if (Array.isArray(node.methods)) {
        const methodObj = node.methods[parseInt(methodName)] as any;
        if (methodObj && methodObj.name) {
          actualMethodName = methodObj.name;
        }
      } else if (typeof node.methods === "object") {
        // If methods is an object, the keys might be the method names
        // But we need to check if the value has a name property
        const methodObj = node.methods[methodName] as any;
        if (methodObj && methodObj.name) {
          actualMethodName = methodObj.name;
        }
      }
    }

    // Extract operationId from methodName if it's in the format "name:operationId"
    let targetOperationId: string | undefined;
    if (methodName.includes(":")) {
      const parts = methodName.split(":");
      actualMethodName = parts[0];
      targetOperationId = parts[1];
    }

    // Find the method in the methods array or object
    let method;
    if (Array.isArray(node.methods)) {
      // If we have an operationId, use it to find the exact method
      if (targetOperationId) {
        method = node.methods.find(
          (m: any) => m.name === actualMethodName && m.config?.operationId === targetOperationId
        );
      }

      // If no method found with operationId or no operationId provided, fall back to name only
      if (!method) {
        method = node.methods.find((m: any) => m.name === actualMethodName);
      }

      // If still not found and methodName is a number, use it as an index
      if (!method && !isNaN(parseInt(methodName))) {
        method = node.methods[parseInt(methodName)];
      }
    } else if (typeof node.methods === "object") {
      method = node.methods[methodName];
      if (!method) {
        // Try to find by name in the object values
        const methods = Object.values(node.methods);

        // If we have an operationId, use it to find the exact method
        if (targetOperationId) {
          method = methods.find(
            (m: any) => m.name === actualMethodName && m.config?.operationId === targetOperationId
          );
        } else {
          method = methods.find((m: any) => m.name === actualMethodName);
        }
      }
    }

    // Use type assertion to access the config property
    const methodWithConfig = method as any;

    // Set methodConfig based on node type
    let methodConfig;
    if (node.info.nodeType === "TRIGGER") {
      // For trigger nodes, use the method name as the method
      // and get parameters from the config.parameters array
      methodConfig = {
        method: actualMethodName,
        parameters:
          methodWithConfig?.config?.parameters?.reduce((acc: any, param: any) => {
            acc[param.name] = ""; // Initialize with empty values
            return acc;
          }, {}) || {},
        requestMapping: null,
        responseMapping: null,
        path: "",
        operationId: "",
      };
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
    }

    // Check if this node has multiple output types in its connections
    let outputTypes = node.info.outputTypes || [];
    let inputTypes = node.info.inputTypes || [];

    // // For nodes with multiple outputs like Choice, extract the output types from connections

    // Log all connections for debugging
    // if (node.connections) {
    // }

    // Try to find the output types in different possible locations
    let outputTypesConfig;
    let inputTypesConfig;

    // Check for output types in the standard location first
    if (node.connections?.outgoing?.[actualMethodName]?.[0]?.connectionConfig?.type) {
      outputTypesConfig = node.connections.outgoing[actualMethodName][0].connectionConfig.type;
    }
    // If not found, try to look in all outgoing connections
    else if (node.connections?.outgoing) {
      // Look through all methods in outgoing connections
      Object.entries(node.connections.outgoing).forEach(([method, connections]) => {
        if (Array.isArray(connections) && connections.length > 0) {
          connections.forEach((connection: any) => {
            if (connection.connectionConfig?.type) {
              outputTypesConfig = connection.connectionConfig.type;
            }
          });
        }
      });
    }

    // Check for input types in the standard location first
    if (node.connections?.incoming?.[actualMethodName]?.[0]?.connectionConfig?.type) {
      inputTypesConfig = node.connections.incoming[actualMethodName][0].connectionConfig.type;
    }
    // If not found, try to look in all incoming connections
    else if (node.connections?.incoming) {
      // Look through all methods in incoming connections
      Object.entries(node.connections.incoming).forEach(([method, connections]) => {
        if (Array.isArray(connections) && connections.length > 0) {
          connections.forEach((connection: any) => {
            if (connection.connectionConfig?.type) {
              inputTypesConfig = connection.connectionConfig.type;
            }
          });
        }
      });
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
        } else if (typeof outputTypesConfig[0] === "object" && outputTypesConfig[0] !== null) {
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
    }

    // If we found input types, use them
    if (inputTypesConfig) {
      // For inputTypes, we need to keep it as a string array
      if (Array.isArray(inputTypesConfig) && inputTypesConfig.length > 0) {
        if (typeof inputTypesConfig[0] === "string") {
          // If it's already an array of strings, use it directly
          inputTypes = inputTypesConfig;
        } else if (typeof inputTypesConfig[0] === "object" && inputTypesConfig[0] !== null) {
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

    event.dataTransfer.setData("application/reactflow", JSON.stringify(nodeData));
    event.dataTransfer.effectAllowed = "move";
  };

  const sections = useMemo(() => {
    if (!nodesResponse?.data) return [];

    const groupedNodes: NodeSection[] = [
      {
        title: t("common.pipelineEditor.triggers"),
        types: ["TRIGGER"],
        nodes: [],
      },
      {
        title: t("common.pipelineEditor.integrations"),
        types: ["INTEGRATION"],
        nodes: [],
      },
      { title: t("common.pipelineEditor.flow"), types: ["FLOW"], nodes: [] },
      {
        title: t("common.pipelineEditor.utilities"),
        types: ["UTILITY"],
        nodes: [],
      },
    ];

    nodesResponse.data.forEach((node) => {
      if (node.methods) {
        // For integration nodes with multiple methods with the same name,
        // we need to use the operationId to distinguish between them
        if (node.info.nodeType === "INTEGRATION" && Array.isArray(node.methods)) {
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
              s.types.some((type) => nodeType.includes(type))
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
          Object.entries(node.methods).forEach(([, method]) => {
            const nodeType = node.info.nodeType;
            const section = groupedNodes.find((s) =>
              s.types.some((type) => nodeType.includes(type))
            );

            if (section) {
              section.nodes.push({ node, methodName: method.name, method });
            }
          });
        }
      }
    });

    return groupedNodes;
  }, [nodesResponse?.data, t]);

  const filteredSections = useMemo(() => {
    return sections.map((section) => ({
      ...section,
      nodes: section.nodes.filter(({ node, method }) => {
        const searchLower = searchQuery.toLowerCase();
        return (
          node.info.title.toLowerCase().includes(searchLower) ||
          (method.description || node.info.description).toLowerCase().includes(searchLower)
        );
      }),
    }));
  }, [sections, searchQuery]);

  // Auto-expand sections with search matches
  React.useEffect(() => {
    if (searchQuery.trim()) {
      // Find sections that have matching nodes
      const sectionsWithMatches = filteredSections
        .filter((section) => section.nodes.length > 0)
        .map((section) => section.types[0]);

      // Expand sections with matches
      setExpandedSections(sectionsWithMatches);
    } else {
      // When search is cleared, revert to manually expanded sections
      setExpandedSections(manuallyExpandedSections);
    }
  }, [filteredSections, searchQuery, manuallyExpandedSections]);

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
        <Typography color="error">{t("common.failedToLoadNodes")}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ pt: 2 }}>
      <Box sx={{ px: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom sx={{ textAlign: "center", mb: 2 }}>
          Available Nodes
        </Typography>

        <TextField
          fullWidth
          size="small"
          placeholder={t("pipelines.editor.searchNodes")}
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
                    onDragStart={(event) => onDragStart(event, node, methodName)}
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
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          flexShrink: 0,
                        }}
                      >
                        {getNodeIcon(node.info.nodeType)}
                      </Box>
                      <Typography variant="subtitle1">{node.info.title}</Typography>
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
  const { setHasSelectedItems } = useRightSidebar();

  // Pipeline sidebar should always be visible and start expanded
  React.useEffect(() => {
    setHasSelectedItems(true);
    return () => setHasSelectedItems(false);
  }, [setHasSelectedItems]);

  return (
    <RightSidebar alwaysVisible>
      <SidebarContent />
    </RightSidebar>
  );
};

export default Sidebar;
