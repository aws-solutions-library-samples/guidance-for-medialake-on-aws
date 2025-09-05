import React, { useCallback, useRef, useState } from "react";
import {
  Handle,
  Position,
  NodeProps,
  useReactFlow,
  useOnSelectionChange,
} from "reactflow";
import { Box, Typography, IconButton, Tooltip } from "@mui/material";
import { FaCog, FaTrash } from "react-icons/fa";
import { RotateRight } from "@mui/icons-material";

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
  onRotate?: (id: string, rotation: number) => void;
  type?: string; // Node type (e.g., 'TRIGGER', 'INTEGRATION', 'FLOW')
  rotation?: number; // Rotation angle in degrees (0, 90, 180, 270)
}

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({
  id,
  data,
  isConnectable,
}) => {
  // In File 1: track selection state
  const [selected, setSelected] = useState(false);
  const { project } = useReactFlow();

  // File 1 only: track selection using useOnSelectionChange
  const onChange = useCallback(
    ({ nodes }) => {
      const isSelected = nodes.find((node: any) => node.id === id);
      setSelected(!!isSelected);
    },
    [id],
  );

  useOnSelectionChange({ onChange });

  // Rotation state - use data.rotation or default to 0
  const currentRotation = data.rotation || 0;

  // Handle rotation
  const handleRotate = (event: React.MouseEvent) => {
    event.stopPropagation();
    const newRotation = (currentRotation + 90) % 360;
    data.onRotate?.(id, newRotation);
  };

  // Helper function to get handle position based on rotation
  const getHandlePosition = (
    originalPosition: Position,
    rotation: number,
  ): Position => {
    const rotationMap = {
      0: {
        [Position.Left]: Position.Left,
        [Position.Right]: Position.Right,
        [Position.Top]: Position.Top,
        [Position.Bottom]: Position.Bottom,
      },
      90: {
        [Position.Left]: Position.Bottom,
        [Position.Right]: Position.Top,
        [Position.Top]: Position.Left,
        [Position.Bottom]: Position.Right,
      },
      180: {
        [Position.Left]: Position.Right,
        [Position.Right]: Position.Left,
        [Position.Top]: Position.Bottom,
        [Position.Bottom]: Position.Top,
      },
      270: {
        [Position.Left]: Position.Top,
        [Position.Right]: Position.Bottom,
        [Position.Top]: Position.Right,
        [Position.Bottom]: Position.Left,
      },
    };
    return (
      rotationMap[rotation as keyof typeof rotationMap]?.[originalPosition] ||
      originalPosition
    );
  };

  const getEdgeOffsetStyle = (position: Position) => {
    if (position === Position.Top) return { top: -6 }; // use -7 if your border is 2px
    if (position === Position.Bottom) return { bottom: -6 }; // use -7 if your border is 2px
    return {};
  };

  // Helper function to get handle container styles based on rotation
  const getHandleContainerStyles = (isInput: boolean, rotation: number) => {
    const baseStyles = {
      position: "absolute" as const,
      display: "flex",
      flexDirection: "column" as const,
      justifyContent:
        (isInput ? inputTypes.length : outputTypes.length) === 1
          ? ("center" as const)
          : ("space-evenly" as const),
      zIndex: 10, // Ensure handles are above the node content
    };

    switch (rotation) {
      case 0:
        return {
          ...baseStyles,
          [isInput ? "left" : "right"]: -3, // 50% on edge (12px handle, so -6px centers it)
          top: -5,
          height: "100%",
        };
      case 90:
        return {
          ...baseStyles,
          [isInput ? "bottom" : "top"]: -5, // 50% on edge (16px handle height, so -8px centers it)
          left: -5,
          width: "100%",
          flexDirection: "row" as const,
        };
      case 180:
        return {
          ...baseStyles,
          [isInput ? "right" : "left"]: -3, // 50% on edge (12px handle, so -6px centers it)
          top: -5,
          height: "100%",
        };
      case 270:
        return {
          ...baseStyles,
          [isInput ? "top" : "bottom"]: -5, // 50% on edge (16px handle height, so -8px centers it)
          left: -5,
          width: "100%",
          flexDirection: "row" as const,
        };
      default:
        return {
          ...baseStyles,
          [isInput ? "left" : "right"]: -3,
          top: -5,
          height: "100%",
        };
    }
  };

  // Helper function to get handle item styles based on rotation
  const getHandleItemStyles = (rotation: number) => {
    const baseStyles = {
      position: "relative" as const,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 15, // Ensure handle items are above everything
    };

    switch (rotation) {
      case 0:
        return {
          ...baseStyles,
          height: "24px",
          width: "12px",
        };
      case 90:
        return {
          ...baseStyles,
          width: "24px",
          height: "12px",
        };
      case 180:
        return {
          ...baseStyles,
          height: "24px",
          width: "12px",
        };
      case 270:
        return {
          ...baseStyles,
          width: "24px",
          height: "12px",
        };
      default:
        return {
          ...baseStyles,
          height: "24px",
          width: "12px",
        };
    }
  };

  // Debug logging
  // console.log('[CustomNode] Input types:', data.inputTypes);
  // console.log('[CustomNode] Output types:', data.outputTypes);

  // Helper function to check if node has configurable parameters
  const hasConfigurableParameters = () => {
    const parameters = data.configuration?.parameters;
    const isIntegrationNode = data.type === "INTEGRATION";

    // Integration nodes always need configuration (for integration selection)
    if (isIntegrationNode) return true;

    // If no parameters object, no configuration needed
    if (!parameters) return false;

    // If parameters is an array (from API response), check if it has items
    if (Array.isArray(parameters)) {
      return parameters.length > 0;
    }

    // If parameters is an object, check if it has keys
    if (typeof parameters === "object") {
      return Object.keys(parameters).length > 0;
    }

    return false;
  };

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

  const inputPos = getHandlePosition(Position.Left, currentRotation);
  const outputPos = getHandlePosition(Position.Right, currentRotation);

  const edgeNudge = (pos: Position) =>
    pos === Position.Top
      ? { top: -2 }
      : pos === Position.Bottom
        ? { bottom: -2 }
        : {};

  return (
    <Box
      sx={{
        borderRadius: "8px",
        background: selected
          ? "conic-gradient(from -160deg at 50% 50%, #e92a67 0deg, #a853ba 120deg, #2a8af6 240deg, #e92a67 360deg)"
          : "",
        padding: "2px",
        transition: "all 0.3s linear",
        zIndex: currentRotation === 90 || currentRotation === 270 ? 1 : 5, // Lower z-index when handles are on top/bottom
      }}
      onFocus={(e) => setSelected(true)}
    >
      <Box
        onClick={handleNodeClick}
        sx={{
          padding: "12px",
          borderRadius: "8px",
          backgroundColor: "background.paper",
          border: !selected ? 2 : 0,
          borderColor: data.configuration ? "primary.main" : "divider",
          width: "200px", // Increased width from 200px to 240px
          maxWidth: "200px", // Increased max width from 200px to 240px
          minHeight: "90px",
          position: "relative",
          boxShadow: 2,
          cursor: "pointer",
          zIndex: currentRotation === 90 || currentRotation === 270 ? 1 : 5, // Lower z-index when handles are on top/bottom
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
          <Box sx={getHandleContainerStyles(true, currentRotation)}>
            {inputTypes.map((inputType, index) => (
              <Box
                key={`input-${index}`}
                sx={getHandleItemStyles(currentRotation)}
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
                    position={inputPos}
                    id={`input-${
                      typeof inputType === "string"
                        ? inputType
                        : (inputType as InputType).name
                    }`}
                    isConnectable={isConnectable}
                    style={{
                      background:
                        typeof inputType === "string"
                          ? "#2B6CB0"
                          : (inputType as InputType).name === "Completed"
                            ? "#4CAF50"
                            : (inputType as InputType).name === "In Progress"
                              ? "#2196F3"
                              : (inputType as InputType).name === "Fail"
                                ? "#F44336"
                                : "#555",
                      width: "12px",
                      height: "16px",
                      border: "1px solid #fff",
                      borderRadius: "2px",
                      transform: `rotate(${-currentRotation}deg)`,
                      transformOrigin: "center center",
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
            {hasConfigurableParameters() && (
              <IconButton
                size="small"
                onClick={handleConfigure}
                sx={{ p: 0.5 }}
              >
                <FaCog size={14} />
              </IconButton>
            )}
            <Tooltip title={`Rotate (${currentRotation}°)`}>
              <IconButton size="small" onClick={handleRotate} sx={{ p: 0.5 }}>
                <RotateRight sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
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
          <Box sx={getHandleContainerStyles(false, currentRotation)}>
            {(outputTypes as OutputType[]).map((output, index) => (
              <Box key={output.name} sx={getHandleItemStyles(currentRotation)}>
                <Tooltip title={output.name}>
                  <Handle
                    type="source"
                    position={outputPos}
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
                              : "#2B6CB0",
                      width: "12px",
                      height: "12px",
                      border: "1px solid #fff",
                      borderRadius: "5px",
                      transform: `rotate(${-currentRotation}deg)`,
                      transformOrigin: "center center",
                      ...edgeNudge(outputPos),
                    }}
                  />
                </Tooltip>
              </Box>
            ))}
          </Box>
        ) : // Single output handle (default behavior)
        null}
      </Box>
    </Box>
  );
};

export default CustomNode;
