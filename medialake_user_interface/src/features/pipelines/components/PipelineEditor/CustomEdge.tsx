import React, { useCallback } from "react";
import {
  EdgeLabelRenderer,
  EdgeProps,
  Position,
  useReactFlow,
} from "reactflow";
import { Box, Stack, Typography, useTheme } from "@mui/material";
import { FlashOn } from "@mui/icons-material";

type Nudge = { along?: number; perp?: number };

const adjustPoint = (
  x: number,
  y: number,
  pos: Position,
  { along = 0, perp = 0 }: Nudge,
): [number, number] => {
  switch (pos) {
    case Position.Top: // normal points up
      return [x + perp, y + along]; // +along pushes DOWN toward the edge tip
    case Position.Bottom: // normal points down
      return [x + perp, y - along]; // +along pushes UP toward the edge tip
    case Position.Left: // normal points left
      return [x + along, y + perp]; // +along pushes RIGHT toward the edge tip
    case Position.Right: // normal points right
      return [x - along, y + perp]; // +along pushes LEFT toward the edge tip
    default:
      return [x, y];
  }
};

// NEW: control points that force an orthogonal approach to each side
const computeControlPoints = (
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  sPos: Position,
  tPos: Position,
) => {
  const dx = tx - sx;
  const dy = ty - sy;

  // how far to push along each side's normal (stronger for vertical to fix your case)
  const MIN = 36; // base minimum curvature
  const MIN_VERT = 48; // a bit more when Top/Bottom to avoid "side attach"
  const SCALE = 0.6; // proportional component

  const offFor = (pos: Position) => {
    if (pos === Position.Top || pos === Position.Bottom) {
      return Math.max(MIN_VERT, Math.abs(dy) * SCALE);
    }
    return Math.max(MIN, Math.abs(dx) * SCALE);
  };

  const so = offFor(sPos);
  const to = offFor(tPos);

  // cp1 extends from source along its side normal
  let c1x = sx,
    c1y = sy;
  if (sPos === Position.Left) c1x = sx - so;
  if (sPos === Position.Right) c1x = sx + so;
  if (sPos === Position.Top) c1y = sy - so;
  if (sPos === Position.Bottom) c1y = sy + so;

  // cp2 should sit OUTSIDE the target so the tangent points INTO the node
  let c2x = tx,
    c2y = ty;
  if (tPos === Position.Left) c2x = tx - to; // outside = left
  if (tPos === Position.Right) c2x = tx + to; // outside = right
  if (tPos === Position.Top) c2y = ty - to; // outside = up
  if (tPos === Position.Bottom) c2y = ty + to; // outside = down

  return { c1x, c1y, c2x, c2y };
};

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
}) => {
  // Adjust coordinates for better connection centering
  // Quick Reference for browser/SVG coordinate system:
  // * Positive Y = down
  // * Negative Y = up
  // * Positive X = right
  // * Negative X = left

  // === 1) tip distance from node edge ===
  // smaller = closer. If arrow hides under the node, bump these back up by +1.
  const TIP_GAP = 4; // was 6/10 – try 4 first
  const OUT_H = TIP_GAP;
  const OUT_V = TIP_GAP;

  const alongFor = (pos: Position) =>
    pos === Position.Top || pos === Position.Bottom ? -OUT_V : -OUT_H;

  // small horizontal nudge for Top/Bottom to visually center the tip
  const H_ALIGN_FIX = 1.25; // try 1.0–1.5 depending on your zoom/theme

  const perpFor = (pos: Position) =>
    pos === Position.Top || pos === Position.Bottom ? H_ALIGN_FIX : 0;

  const [sx, sy] = adjustPoint(sourceX, sourceY, sourcePosition, {
    along: data?.sourcePad ?? alongFor(sourcePosition),
    perp: data?.sourcePerp ?? perpFor(sourcePosition),
  });

  const [tx, ty] = adjustPoint(targetX, targetY, targetPosition, {
    along: data?.targetPad ?? alongFor(targetPosition),
    perp: data?.targetPerp ?? perpFor(targetPosition),
  });

  // --- use orthogonal control points ---
  const { c1x, c1y, c2x, c2y } = computeControlPoints(
    sx,
    sy,
    tx,
    ty,
    sourcePosition,
    targetPosition,
  );

  // === 2) final straight segment ===
  // keep it a bit longer than the marker base so the approach stays orthogonal
  const END_TAIL = TIP_GAP + 2; // was 12/10 – reduce with TIP_GAP
  const tailPoint = (() => {
    switch (targetPosition) {
      case Position.Top:
        return { px: tx, py: ty - END_TAIL }; // go DOWN into top
      case Position.Bottom:
        return { px: tx, py: ty + END_TAIL }; // go UP into bottom
      case Position.Left:
        return { px: tx - END_TAIL, py: ty }; // go RIGHT into left
      case Position.Right:
        return { px: tx + END_TAIL, py: ty }; // go LEFT into right
      default:
        return { px: tx, py: ty };
    }
  })();

  // use a cubic into the tailPoint, then a straight segment to the tip
  const edgePath = `M ${sx},${sy} C ${c1x},${c1y} ${c2x},${c2y} ${tailPoint.px},${tailPoint.py} L ${tx},${ty}`;
  const flow = useReactFlow();
  const sourceNode = flow.getNode(source ?? "");

  /**
   * Calculate a point on the bezier curve at a given percentage (0-1)
   * This ensures the label stays on the actual curve path
   */
  // Label point on our bezier (reuse cp's to stay on-curve)
  const getBezierPoint = useCallback(
    (t: number) => {
      const x =
        Math.pow(1 - t, 3) * sx +
        3 * Math.pow(1 - t, 2) * t * c1x +
        3 * (1 - t) * Math.pow(t, 2) * c2x +
        Math.pow(t, 3) * tx;

      const y =
        Math.pow(1 - t, 3) * sy +
        3 * Math.pow(1 - t, 2) * t * c1y +
        3 * (1 - t) * Math.pow(t, 2) * c2y +
        Math.pow(t, 3) * ty;

      return { x, y };
    },
    [sx, sy, c1x, c1y, c2x, c2y, tx, ty],
  );

  const mid = getBezierPoint(0.5);
  const labelX = mid.x;
  const labelY = mid.y;

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

  const isVertical =
    targetPosition === Position.Top || targetPosition === Position.Bottom;

  // stroke-scaled marker like React Flow's default
  const markerId = `${id}-arrow`;
  // === 3) marker anchor fine-tune ===
  // lower numbers push the tip slightly "into" the node along the last segment
  const refXFor = (pos: Position) =>
    pos === Position.Top
      ? 9.0 // was 9.5
      : pos === Position.Bottom
        ? 8.0 // was 8.5
        : 9.0; // was 9.5
  const refX = refXFor(targetPosition);
  const strokeColor = (style as any)?.stroke?.toString() || "#b1b1b7";

  return (
    <>
      {/* Marker definition must live in the same SVG */}
      <defs>
        <marker
          id={markerId}
          markerWidth={10}
          markerHeight={10}
          refX={refX}
          refY={5}
          orient="auto"
          viewBox="0 0 10 10"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L10,5 L0,10 Z" fill={strokeColor} />
        </marker>
      </defs>

      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{ ...style, stroke: strokeColor, strokeWidth: 2, fill: "none" }}
        markerEnd={`url(#${markerId})`}
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
