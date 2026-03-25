import React, { useCallback } from "react";
import { Handle, Position, type NodeProps, useReactFlow, type Node } from "@xyflow/react";
import { Box, Typography, IconButton } from "@mui/material";
import SettingsIcon from "@mui/icons-material/Settings";
import DeleteIcon from "@mui/icons-material/Delete";
import { CustomNodeData } from "./CustomNode";
import { colorTokens } from "@/theme/tokens";

const HANDLE_CONNECT_RADIUS = 50;

// We're extending CustomNodeData to ensure compatibility
export interface JobStatusNodeData extends CustomNodeData {
  // Additional props specific to job status node can be added here
  [key: string]: unknown;
}

export type JobStatusFlowNode = Node<JobStatusNodeData, "jobStatus">;

const JobStatusNode: React.FC<NodeProps<JobStatusFlowNode>> = ({ id, data, isConnectable }) => {
  const { screenToFlowPosition } = useReactFlow();

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
      const clickX = event.clientX;
      const clickY = event.clientY;

      // Helper function to check if click is near a handle
      const isNearHandle = (handleElement: Element | null) => {
        if (!handleElement) return false;
        const handleRect = handleElement.getBoundingClientRect();
        const handleX = handleRect.left + handleRect.width / 2;
        const handleY = handleRect.top + handleRect.height / 2;

        const distance = Math.sqrt(Math.pow(clickX - handleX, 2) + Math.pow(clickY - handleY, 2));

        return distance <= HANDLE_CONNECT_RADIUS;
      };

      // Find the closest handle
      const handles = Array.from(
        document.querySelectorAll(`[data-nodeid="${id}"] .react-flow__handle-source`)
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
    [id, screenToFlowPosition]
  );

  return (
    <Box
      onClick={handleNodeClick}
      sx={{
        padding: "10px",
        borderRadius: "8px",
        backgroundColor: "background.paper",
        border: 1,
        borderColor: data.configuration ? "primary.main" : "divider",
        width: "200px",
        maxWidth: "200px",
        position: "relative",
        boxShadow: 2,
        cursor: "pointer",
        "&:hover": {
          boxShadow: 3,
        },
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        style={{
          background: colorTokens.text.secondary.light,
          width: "12px",
          height: "12px",
          border: `2px solid ${colorTokens.primary.contrastText}`,
          borderRadius: "6px",
        }}
      />

      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          gap: 1,
          position: "relative",
        }}
      >
        {data.icon}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="subtitle1"
            sx={{
              lineHeight: 1.2,
              fontWeight: "medium",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {data.label}
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              lineHeight: 1.2,
              overflow: "hidden",
              textOverflow: "ellipsis",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              display: "-webkit-box",
            }}
          >
            {data.description}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 0.5, ml: 0.5 }}>
          <IconButton size="small" onClick={handleConfigure} sx={{ p: 0.5 }}>
            <SettingsIcon sx={{ fontSize: 14 }} />
          </IconButton>
          <IconButton size="small" onClick={handleDelete} sx={{ p: 0.5 }}>
            <DeleteIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Box>
      </Box>

      {/* Multiple outputs for the different job statuses */}
      <Box
        sx={{
          position: "absolute",
          right: 0,
          top: "25%",
          height: "75%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        {/* Completed output */}
        <Box
          sx={{
            position: "relative",
            height: "24px",
            display: "flex",
            alignItems: "center",
            mr: "-6px",
          }}
        >
          <Typography variant="caption" sx={{ mr: 1, fontSize: "0.7rem" }}>
            Completed
          </Typography>
          <Handle
            type="source"
            position={Position.Right}
            id="completed"
            isConnectable={isConnectable}
            style={{
              background: colorTokens.success.main, // Green for completed
              width: "10px",
              height: "10px",
              border: `2px solid ${colorTokens.primary.contrastText}`,
              borderRadius: "5px",
            }}
          />
        </Box>

        {/* In Progress output */}
        <Box
          sx={{
            position: "relative",
            height: "24px",
            display: "flex",
            alignItems: "center",
            mr: "-6px",
          }}
        >
          <Typography variant="caption" sx={{ mr: 1, fontSize: "0.7rem" }}>
            In Progress
          </Typography>
          <Handle
            type="source"
            position={Position.Right}
            id="in-progress"
            isConnectable={isConnectable}
            style={{
              background: colorTokens.info.main, // Blue for in progress
              width: "10px",
              height: "10px",
              border: `2px solid ${colorTokens.primary.contrastText}`,
              borderRadius: "5px",
            }}
          />
        </Box>

        {/* Fail output */}
        <Box
          sx={{
            position: "relative",
            height: "24px",
            display: "flex",
            alignItems: "center",
            mr: "-6px",
          }}
        >
          <Typography variant="caption" sx={{ mr: 1, fontSize: "0.7rem" }}>
            Fail
          </Typography>
          <Handle
            type="source"
            position={Position.Right}
            id="fail"
            isConnectable={isConnectable}
            style={{
              background: colorTokens.error.main, // Red for fail
              width: "10px",
              height: "10px",
              border: `2px solid ${colorTokens.primary.contrastText}`,
              borderRadius: "5px",
            }}
          />
        </Box>
      </Box>
    </Box>
  );
};

export default JobStatusNode;
