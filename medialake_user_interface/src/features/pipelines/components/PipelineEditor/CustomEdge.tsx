import React, { useCallback } from 'react';
import { EdgeLabelRenderer, EdgeProps, getBezierPath, MarkerType, Position, useReactFlow } from 'reactflow';
import { Box, Stack, Typography, useTheme } from '@mui/material';
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
    const [edgePath, labelX, labelY] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });
    const flow = useReactFlow();
    const sourceNode = flow.getNode(source ?? "");

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
    }, [flow, id, sourceNode])

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
    }, [getChoiceLabel])

    return (
        <>
            <path
                id={id}
                style={{
                    ...style,
                    stroke: '#b1b1b7',
                    strokeWidth: 2,
                    fill: 'none',
                }}
                className="react-flow__edge-path"
                d={edgePath}
                markerEnd={markerEnd}
            />
            {sourceNode?.data?.type === "TRIGGER" && <EdgeLabelRenderer>
              <Typography
                variant={"caption"}
                className="button-edge__label nodrag nopan"
                style={{
                  position: 'absolute',
                  transform: 'translate(-50%, -50%)',
                  pointerEvents: 'all',
                  left: labelX,
                  top: labelY,
                  padding: '2px 6px 2px 2px',
                  fontWeight: 600,
                  backgroundColor: '#2B6CB0',
                  color: "#fff",
                  userSelect: 'none',
                  borderRadius: "6px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <FlashOn sx={{fontSize: "15px"}} />{sourceNode?.data?.type}
              </Typography>
            </EdgeLabelRenderer>}
            {sourceNode?.data?.type === "FLOW" && sourceNode?.data?.nodeId === "choice" && <EdgeLabelRenderer>
              <Typography
                variant={"caption"}
                className="button-edge__label nodrag nopan"
                style={{
                  position: 'absolute',
                  transform: 'translate(-50%, -50%)',
                  pointerEvents: 'all',
                  left: labelX,
                  top: labelY,
                  padding: '2px 6px 2px 6px',
                  fontSize: 10,
                  fontWeight: 600,
                  backgroundColor: getChoiceLabelColor(),
                  color: "#fff",
                  userSelect: 'none',
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                  {getChoiceLabel()}
              </Typography>
            </EdgeLabelRenderer>}

            {data?.text && (
                <Box
                    sx={{
                        position: 'absolute',
                        transform: 'translate(-50%, -50%)',
                        fontSize: 12,
                        pointerEvents: 'all',
                        left: labelX,
                        top: labelY,
                        padding: '4px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(255, 255, 255, 0.75)',
                        userSelect: 'none',
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