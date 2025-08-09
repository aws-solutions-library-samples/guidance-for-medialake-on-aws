import React, { useCallback } from "react";
import {
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
  MarkerType,
  Position,
  useReactFlow,
} from "reactflow";
import { Box, Stack, Typography, useTheme } from "@mui/material";
import { FlashOn } from "@mui/icons-material";

const CustomEdge: React.FC<EdgeProps> = ({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style = {},
  markerEnd,
}) => {
  // Adjust coordinates for better connection centering
  const getAdjustedCoordinates = () => {
    let adjustedSourceX = sourceX;
    let adjustedSourceY = sourceY;
    let adjustedTargetX = targetX;
    let adjustedTargetY = targetY;

    // For vertical connections, apply small horizontal offset to center better
    if (targetPosition === Position.Top || targetPosition === Position.Bottom) {
      adjustedTargetX = targetX + 2;
    }

    if (sourcePosition === Position.Top || sourcePosition === Position.Bottom) {
      adjustedSourceX = sourceX + 2;
    }

    // For horizontal connections, apply small vertical offset to center better with rectangular handles
    if (targetPosition === Position.Left || targetPosition === Position.Right) {
      adjustedTargetY = targetY + 2; // Increased upward adjustment for better gap
    }

    if (sourcePosition === Position.Left || sourcePosition === Position.Right) {
      adjustedSourceY = sourceY + 2; // Increased upward adjustment for better gap
    }

    return {
      adjustedSourceX,
      adjustedSourceY,
      adjustedTargetX,
      adjustedTargetY,
    };
  };

  const { adjustedSourceX, adjustedSourceY, adjustedTargetX, adjustedTargetY } =
    getAdjustedCoordinates();

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: adjustedSourceX,
    sourceY: adjustedSourceY,
    sourcePosition,
    targetX: adjustedTargetX,
    targetY: adjustedTargetY,
    targetPosition,
  });
  const flow = useReactFlow();
  const sourceNode = flow.getNode(source ?? "");

  /**
   * Calculate a point on the bezier curve at a given percentage (0-1)
   * This ensures the label stays on the actual curve path
   */
  const getBezierPoint = useCallback(
    (t: number) => {
      // For a cubic bezier curve, we need the control points
      // getBezierPath creates a curve, but we need to calculate our own point
      const dx = adjustedTargetX - adjustedSourceX;
      const dy = adjustedTargetY - adjustedSourceY;

      // Calculate control points based on the source and target positions
      let controlPoint1X = adjustedSourceX;
      let controlPoint1Y = adjustedSourceY;
      let controlPoint2X = adjustedTargetX;
      let controlPoint2Y = adjustedTargetY;

      // Adjust control points based on handle positions (similar to getBezierPath logic)
      if (sourcePosition === Position.Right) {
        controlPoint1X = adjustedSourceX + Math.abs(dx) * 0.5;
      } else if (sourcePosition === Position.Left) {
        controlPoint1X = adjustedSourceX - Math.abs(dx) * 0.5;
      } else if (sourcePosition === Position.Top) {
        controlPoint1Y = adjustedSourceY - Math.abs(dy) * 0.5;
      } else if (sourcePosition === Position.Bottom) {
        controlPoint1Y = adjustedSourceY + Math.abs(dy) * 0.5;
      }

      if (targetPosition === Position.Right) {
        controlPoint2X = adjustedTargetX + Math.abs(dx) * 0.5;
      } else if (targetPosition === Position.Left) {
        controlPoint2X = adjustedTargetX - Math.abs(dx) * 0.5;
      } else if (targetPosition === Position.Top) {
        controlPoint2Y = adjustedTargetY - Math.abs(dy) * 0.5;
      } else if (targetPosition === Position.Bottom) {
        controlPoint2Y = adjustedTargetY + Math.abs(dy) * 0.5;
      }

      // Cubic bezier formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
      const x =
        Math.pow(1 - t, 3) * adjustedSourceX +
        3 * Math.pow(1 - t, 2) * t * controlPoint1X +
        3 * (1 - t) * Math.pow(t, 2) * controlPoint2X +
        Math.pow(t, 3) * adjustedTargetX;

      const y =
        Math.pow(1 - t, 3) * adjustedSourceY +
        3 * Math.pow(1 - t, 2) * t * controlPoint1Y +
        3 * (1 - t) * Math.pow(t, 2) * controlPoint2Y +
        Math.pow(t, 3) * adjustedTargetY;

      return { x, y };
    },
    [
      adjustedSourceX,
      adjustedSourceY,
      adjustedTargetX,
      adjustedTargetY,
      sourcePosition,
      targetPosition,
    ],
  );

  /**
   * Get the choice label for the edge
   * @returns The output handle name (Completed, Fail, In Progress)
   */
  const getChoiceLabel = useCallback(() => {
    // Get the current edge from ReactFlow
    const currentEdge = flow.getEdge(id);

    // The sourceHandle should contain the output handle name
    const sourceHandle = currentEdge?.sourceHandle;

    // If we have a source handle, use it, otherwise try to extract from the edge ID
    if (sourceHandle) {
      return sourceHandle;
    }

    // Fallback: try to extract from edge ID or use output types
    const outputTypes = sourceNode?.data?.outputTypes;
    if (Array.isArray(outputTypes) && outputTypes.length > 0) {
      // For now, just return the first output type name as a fallback
      return outputTypes[0]?.name || "Unknown";
    }

    return "Unknown";
  }, [flow, id, sourceNode]);

  const getChoiceLabelColor = useCallback(() => {
    const label = getChoiceLabel();

    // Use the same colors as the handles in CustomNode
    switch (label) {
      case "Completed":
        return "#4CAF50"; // Green
      case "In Progress":
        return "#2196F3"; // Blue
      case "Fail":
        return "#F44336"; // Red
      default:
        return "#2B6CB0"; // Default blue
    }
  }, [getChoiceLabel]);

  return (
    <>
      <path
        id={id}
        style={{
          ...style,
          stroke: "#b1b1b7",
          strokeWidth: 2,
          fill: "none",
        }}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
      />
      {sourceNode?.data?.type === "TRIGGER" && (
        <EdgeLabelRenderer>
          <Typography
            variant={"caption"}
            className="button-edge__label nodrag nopan"
            style={{
              position: "absolute",
              transform: "translate(-50%, -50%)",
              pointerEvents: "all",
              left: labelX,
              top: labelY,
              padding: "2px 6px 2px 2px",
              fontWeight: 600,
              backgroundColor: "#2B6CB0",
              color: "#fff",
              userSelect: "none",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
            }}
          >
            <FlashOn sx={{ fontSize: "15px" }} />
            {sourceNode?.data?.type}
          </Typography>
        </EdgeLabelRenderer>
      )}
      {sourceNode?.data?.type === "FLOW" &&
        sourceNode?.data?.nodeId === "choice" &&
        (() => {
          const labelPoint = getBezierPoint(0.25);
          return (
            <EdgeLabelRenderer>
              <Typography
                variant={"caption"}
                className="button-edge__label nodrag nopan"
                style={{
                  position: "absolute",
                  transform: "translate(-50%, -50%)",
                  pointerEvents: "all",
                  left: labelPoint.x,
                  top: labelPoint.y,
                  padding: "2px 6px 2px 6px",
                  fontSize: 10,
                  fontWeight: 600,
                  backgroundColor: getChoiceLabelColor(),
                  color: "#fff",
                  userSelect: "none",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {getChoiceLabel()}
              </Typography>
            </EdgeLabelRenderer>
          );
        })()}

      {data?.text && (
        <Box
          sx={{
            position: "absolute",
            transform: "translate(-50%, -50%)",
            fontSize: 12,
            pointerEvents: "all",
            left: labelX,
            top: labelY,
            padding: "4px",
            borderRadius: "4px",
            backgroundColor: "rgba(255, 255, 255, 0.75)",
            userSelect: "none",
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {data.text}
          </Typography>
        </Box>
      )}
    </>
  );
};

export default CustomEdge;
