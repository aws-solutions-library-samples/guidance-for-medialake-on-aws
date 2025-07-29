import React from "react";
import { EdgeProps, getBezierPath } from "reactflow";
import { Box, Typography } from "@mui/material";

const CustomEdge: React.FC<EdgeProps> = ({
  id,
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
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

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
