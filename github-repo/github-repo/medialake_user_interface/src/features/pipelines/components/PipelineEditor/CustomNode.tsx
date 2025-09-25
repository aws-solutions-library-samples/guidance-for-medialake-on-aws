import React, { useCallback, useRef, useState } from "react";
import { Handle, Position, NodeProps, useReactFlow } from "reactflow";
import { Box, Typography, IconButton, Tooltip } from "@mui/material";
import { FaCog, FaTrash } from "react-icons/fa";

const HANDLE_CONNECT_RADIUS = 50;

// Component for expandable description with see more/less functionality
const ExpandableDescription: React.FC<{ text: string }> = ({ text }) => {
  const textRef = useRef<HTMLParagraphElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Check if text is overflowing on mount and window resize
  React.useEffect(() => {
    const checkOverflow = () => {
      if (textRef.current) {
        // For multi-line text with line clamp, check if scrollHeight > clientHeight
        const isTextOverflowing =
          textRef.current.scrollHeight > textRef.current.clientHeight;
        setIsOverflowing(isTextOverflowing);
      }
    };

    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [text]);

  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent node click event
    setIsExpanded(!isExpanded);
  };

  return (
    <Box>
      <Typography
        ref={textRef}
        variant="body2"
        color="text.secondary"
        sx={{
          lineHeight: 1.2,
          overflow: isExpanded ? "visible" : "hidden",
          textOverflow: "ellipsis",
          WebkitLineClamp: isExpanded ? "unset" : 2,
          WebkitBoxOrient: "vertical",
          display: isExpanded ? "block" : "-webkit-box",
          transition: "all 0.2s ease-in-out",
        }}
      >
        {text}
      </Typography>
      {(isOverflowing || isExpanded) && (
        <Typography
          variant="caption"
          color="primary"
          onClick={toggleExpand}
          sx={{
            cursor: "pointer",
            display: "block",
            textAlign: "right",
            mt: 0.5,
            fontWeight: "medium",
            "&:hover": {
              textDecoration: "underline",
            },
          }}
        >
          {isExpanded ? "See less" : "See more"}
        </Typography>
      )}
    </Box>
  );
};

const LabelWithTooltip: React.FC<{ text: string }> = ({ text }) => {
  const textRef = useRef<HTMLSpanElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  // Check if text is overflowing on mount and window resize
  React.useEffect(() => {
    const checkOverflow = () => {
      if (textRef.current) {
        const isTextOverflowing =
          textRef.current.scrollWidth > textRef.current.clientWidth;
        setIsOverflowing(isTextOverflowing);
      }
    };

    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [text]);

  return (
    <Tooltip title={text} disableHoverListener={!isOverflowing}>
      <Typography
        ref={textRef}
        variant="subtitle1"
        sx={{
          lineHeight: 1.2,
          fontWeight: "medium",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap", // Keep on single line
          marginBottom: "10px",
          width: "100%",
        }}
      >
        {text}
      </Typography>
    </Tooltip>
  );
};

export interface InputType {
  name: string;
  description?: string;
}

export interface OutputType {
  name: string;
  description?: string;
}

export interface CustomNodeData {
  label: string;
  icon: React.ReactNode;
  inputTypes: string[] | InputType[];
  outputTypes: string[] | OutputType[];
  nodeId: string; // Original node ID from the API
  description: string; // Node description
  configuration?: any; // Node configuration
  onDelete?: (id: string) => void;
  onConfigure?: (id: string) => void;
  type?: string; // Node type (e.g., 'TRIGGER', 'INTEGRATION', 'FLOW')
}

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({
  id,
  data,
  isConnectable,
}) => {
  const { project } = useReactFlow();

  // Debug logging
  // console.log('[CustomNode] Input types:', data.inputTypes);
  // console.log('[CustomNode] Output types:', data.outputTypes);

  const handleDelete = (event: React.MouseEvent) => {
    event.stopPropagation();
    data.onDelete?.(id);
  };

  const handleConfigure = (event: React.MouseEvent) => {
    event.stopPropagation();
    data.onConfigure?.(id);
  };

  const handleNodeClick = useCallback(
    (event: React.MouseEvent) => {
      const rect = (event.target as HTMLElement).getBoundingClientRect();
      const clickX = event.clientX;
      const clickY = event.clientY;

      // Helper function to check if click is near a handle
      const isNearHandle = (handleElement: Element | null) => {
        if (!handleElement) return false;
        const handleRect = handleElement.getBoundingClientRect();
        const handleX = handleRect.left + handleRect.width / 2;
        const handleY = handleRect.top + handleRect.height / 2;

        const distance = Math.sqrt(
          Math.pow(clickX - handleX, 2) + Math.pow(clickY - handleY, 2),
        );

        return distance <= HANDLE_CONNECT_RADIUS;
      };

      // Find the closest handle
      const handles = Array.from(
        document.querySelectorAll(
          `[data-nodeid="${id}"] .react-flow__handle-source`,
        ),
      );
      for (const handle of handles) {
        if (isNearHandle(handle)) {
          const event = new MouseEvent("mousedown", {
            clientX: clickX,
            clientY: clickY,
            bubbles: true,
          });
          handle.dispatchEvent(event);
          break;
        }
      }
    },
    [id, project],
  );

  const isTriggerNode = data.type?.includes("TRIGGER");
  const isIntegrationNode = data.type === "INTEGRATION";

  // For INTEGRATION nodes, ensure we have at least one input and one output
  const inputTypes =
    isIntegrationNode && (!data.inputTypes || data.inputTypes.length === 0)
      ? [{ name: "default" } as InputType]
      : data.inputTypes;

  const outputTypes =
    isIntegrationNode && (!data.outputTypes || data.outputTypes.length === 0)
      ? [{ name: "default" } as OutputType]
      : data.outputTypes;

  return (
    <Box
      onClick={handleNodeClick}
      sx={{
        padding: "12px",
        borderRadius: "8px",
        backgroundColor: "background.paper",
        border: 1,
        borderColor: data.configuration ? "primary.main" : "divider",
        width: "200px", // Increased width from 200px to 240px
        maxWidth: "200px", // Increased max width from 200px to 240px
        minHeight: "100px",
        position: "relative",
        boxShadow: 2,
        cursor: "pointer",
        "&:hover": {
          boxShadow: 3,
          "& .node-actions": {
            opacity: 1, // Show buttons on hover
            width: "auto", // Allow buttons to take their natural width
            marginLeft: "8px", // Add some spacing
          },
          "& .label-container": {
            width: "calc(100% - 60px)", // Reduce width to make room for buttons
          },
        },
      }}
    >
      {/* Input handles */}
      {!isTriggerNode && (
        <Box
          sx={{
            position: "absolute",
            left: 3,
            top: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: inputTypes.length === 1 ? "center" : "space-evenly",
          }}
        >
          {inputTypes.map((inputType, index) => (
            <Box
              key={`input-${index}`}
              sx={{
                position: "relative",
                height: "24px",
                display: "flex",
                alignItems: "center",
                ml: "-6px",
              }}
            >
              <Tooltip
                title={
                  typeof inputType === "string"
                    ? inputType
                    : (inputType as InputType).name
                }
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={`input-${
                    typeof inputType === "string"
                      ? inputType
                      : (inputType as InputType).name
                  }`}
                  isConnectable={isConnectable}
                  style={{
                    background:
                      typeof inputType === "string"
                        ? "#555"
                        : (inputType as InputType).name === "Completed"
                          ? "#4CAF50"
                          : (inputType as InputType).name === "In Progress"
                            ? "#2196F3"
                            : (inputType as InputType).name === "Fail"
                              ? "#F44336"
                              : "#555",
                    width: "12px",
                    height: "12px",
                    border: "2px solid #fff",
                    borderRadius: "6px",
                  }}
                />
              </Tooltip>
            </Box>
          ))}
        </Box>
      )}

      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          gap: 1,
          position: "relative",
        }}
      >
        {data.icon}
        <Box
          className="label-container"
          sx={{
            flex: 1,
            minWidth: 0,
            width: "100%",
            transition: "all 0.2s ease-in-out", // Smooth transition for container
          }}
        >
          {/* Label with tooltip that only shows when text is truncated */}
          <LabelWithTooltip text={data.label} />
        </Box>
        <Box
          className="node-actions"
          sx={{
            display: "flex",
            gap: 0.5,
            ml: 0.5,
            opacity: 0, // Hide by default
            width: 0, // Take up no space when hidden
            overflow: "hidden", // Hide overflow when width is 0
            transition: "all 0.2s ease-in-out", // Smooth transition for all properties
          }}
        >
          <IconButton size="small" onClick={handleConfigure} sx={{ p: 0.5 }}>
            <FaCog size={14} />
          </IconButton>
          <IconButton size="small" onClick={handleDelete} sx={{ p: 0.5 }}>
            <FaTrash size={14} />
          </IconButton>
        </Box>
      </Box>
      {/* Expandable description with see more/less functionality */}
      <ExpandableDescription text={data.description} />
      {/* Check if we have multiple output types or a single output */}
      {Array.isArray(outputTypes) &&
      outputTypes.length > 0 &&
      typeof outputTypes[0] === "object" &&
      "name" in (outputTypes[0] as any) ? (
        // Multiple output types as objects with name/description
        <Box
          sx={{
            position: "absolute",
            right: 3,
            top: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent:
              (outputTypes as OutputType[]).length === 1
                ? "center"
                : "space-evenly",
          }}
        >
          {(outputTypes as OutputType[]).map((output, index) => (
            <Box
              key={output.name}
              sx={{
                position: "relative",
                height: "24px",
                display: "flex",
                alignItems: "center",
                mr: "-6px",
              }}
            >
              {/* <Typography variant="caption" sx={{ mr: 1, fontSize: '0.7rem' }}>
                                {output.name}
                            </Typography> */}
              <Tooltip title={output.name}>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={output.name}
                  isConnectable={isConnectable}
                  style={{
                    background:
                      output.name === "Completed"
                        ? "#4CAF50"
                        : output.name === "In Progress"
                          ? "#2196F3"
                          : output.name === "Fail"
                            ? "#F44336"
                            : "#555",
                    width: "12px",
                    height: "12px",
                    border: "2px solid #fff",
                    borderRadius: "5px",
                  }}
                />
              </Tooltip>
            </Box>
          ))}
        </Box>
      ) : // Single output handle (default behavior)
      null}
    </Box>
  );
};

export default CustomNode;
