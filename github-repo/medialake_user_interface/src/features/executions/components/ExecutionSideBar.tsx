import React from "react";
import {
  Box,
  Typography,
  IconButton,
  Divider,
  Paper,
  Stack,
  Slide,
  Link,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { Link as RouterLink } from "react-router-dom";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import type { PipelineExecution } from "../types/pipelineExecutions.types";

interface ExecutionSideBarProps {
  isOpen: boolean;
  execution: PipelineExecution | null;
  onClose: () => void;
}

export const ExecutionSideBar: React.FC<ExecutionSideBarProps> = ({
  isOpen,
  execution,
  onClose,
}) => {
  if (!execution) return null;

  return (
    <Slide direction="left" in={isOpen} mountOnEnter unmountOnExit>
      <Box
        sx={{
          right: 16,
          top: 16,
          bottom: 16,
          width: "500px",
          height: "100%",
          bgcolor: "background.paper",
          borderLeft: "1px solid",
          borderColor: "divider",
          borderRadius: "8px !important", // Force border radius
          zIndex: 1,
          display: "flex",
          flexDirection: "column",
          boxShadow: (theme) => theme.shadows[1],
          overflow: "hidden",
          "& .MuiPaper-root": {
            borderRadius: "8px",
          },
        }}
      >
        {/* Header */}
        <Box
          sx={{
            p: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid",
            borderColor: "divider",
            bgcolor: "background.paper",
          }}
        >
          <Typography variant="h6">Execution Details</Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>

        {/* Content */}
        <Box
          sx={{
            flex: 1,
            overflow: "auto",
            p: 2,
          }}
        >
          <Stack spacing={2}>
            {/* Basic Information */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Basic Information
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Stack spacing={2}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Pipeline Name
                  </Typography>
                  <Typography>{execution.pipeline_name}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Execution ID
                  </Typography>
                  <Typography>{execution.execution_id}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Status
                  </Typography>
                  <Typography>{execution.status}</Typography>
                </Box>
              </Stack>
            </Paper>

            {/* Timing Information */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Timing Information
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Stack spacing={2}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Start Time
                  </Typography>
                  <Typography>
                    {formatLocalDateTime(execution.start_time, {
                      showSeconds: true,
                    })}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    End Time
                  </Typography>
                  <Typography>
                    {execution.end_time
                      ? formatLocalDateTime(execution.end_time, {
                          showSeconds: true,
                        })
                      : "N/A"}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Duration
                  </Typography>
                  <Typography>
                    {execution.duration_seconds
                      ? `${execution.duration_seconds} seconds`
                      : "N/A"}
                  </Typography>
                </Box>
              </Stack>
            </Paper>

            {/* Additional Information */}
            {(execution.inventory_id ||
              execution.object_key_name ||
              execution.pipeline_trace_id ||
              execution.step_name) && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Additional Information
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Stack spacing={2}>
                  {execution.inventory_id && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Asset ID
                      </Typography>
                      <Typography
                        sx={{ fontFamily: "monospace", fontSize: "0.875rem" }}
                      >
                        {execution.inventory_id}
                      </Typography>
                    </Box>
                  )}
                  {execution.object_key_name && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        File Name
                      </Typography>
                      {execution.inventory_id ? (
                        <Typography>
                          <Link
                            component={RouterLink}
                            to={`/images/${execution.inventory_id}`}
                          >
                            {execution.object_key_name}
                          </Link>
                        </Typography>
                      ) : (
                        <Typography>{execution.object_key_name}</Typography>
                      )}
                    </Box>
                  )}
                  {execution.pipeline_trace_id && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Pipeline Trace ID
                      </Typography>
                      <Typography
                        sx={{ fontFamily: "monospace", fontSize: "0.875rem" }}
                      >
                        {execution.pipeline_trace_id}
                      </Typography>
                    </Box>
                  )}
                  {execution.step_name && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Step Name
                      </Typography>
                      <Typography>{execution.step_name}</Typography>
                    </Box>
                  )}
                  {execution.step_status && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Step Status
                      </Typography>
                      <Typography>{execution.step_status}</Typography>
                    </Box>
                  )}
                  {execution.step_result && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Step Result
                      </Typography>
                      <Typography>{execution.step_result}</Typography>
                    </Box>
                  )}
                </Stack>
              </Paper>
            )}

            {/* Error Information */}
            {(execution.error || execution.cause) && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" color="error" gutterBottom>
                  Error Information
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Stack spacing={2}>
                  {execution.error && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Error Type
                      </Typography>
                      <Typography color="error">{execution.error}</Typography>
                    </Box>
                  )}
                  {execution.cause && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Error Details
                      </Typography>
                      <Box
                        sx={{
                          mt: 1,
                          p: 1.5,
                          bgcolor: "background.default",
                          borderRadius: 1,
                          border: "1px solid",
                          borderColor: "divider",
                          maxHeight: "200px",
                          overflow: "auto",
                        }}
                      >
                        <Typography
                          color="error"
                          sx={{
                            whiteSpace: "pre-wrap",
                            fontFamily: "monospace",
                            fontSize: "0.75rem",
                            wordBreak: "break-word",
                          }}
                        >
                          {typeof execution.cause === "string"
                            ? execution.cause
                            : JSON.stringify(execution.cause, null, 2)}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </Stack>
              </Paper>
            )}

            {/* Metadata */}
            {execution.metadata && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Execution Metadata
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Stack spacing={2}>
                  {Object.entries(
                    execution.metadata as Record<string, any>,
                  ).map(([key, value]) => (
                    <Box key={key}>
                      <Typography variant="caption" color="text.secondary">
                        {key
                          .replace(/([A-Z])/g, " $1")
                          .replace(/^./, (str) => str.toUpperCase())}
                      </Typography>
                      <Typography
                        sx={{
                          fontFamily:
                            typeof value === "string" &&
                            (key.includes("Id") ||
                              key.includes("Arn") ||
                              key.includes("Time"))
                              ? "monospace"
                              : "inherit",
                          fontSize:
                            typeof value === "string" &&
                            (key.includes("Id") ||
                              key.includes("Arn") ||
                              key.includes("Time"))
                              ? "0.875rem"
                              : "inherit",
                          wordBreak: "break-word",
                        }}
                      >
                        {typeof value === "object" && value !== null
                          ? JSON.stringify(value, null, 2)
                          : String(value || "N/A")}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </Paper>
            )}
          </Stack>
        </Box>
      </Box>
    </Slide>
  );
};

export default ExecutionSideBar;
