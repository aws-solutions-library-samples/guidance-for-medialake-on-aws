import React from "react";
import {
  Box,
  Typography,
  FormControlLabel,
  CircularProgress,
} from "@mui/material";
import {
  PowerSettingsNew as PowerOnIcon,
  PowerOff as PowerOffIcon,
} from "@mui/icons-material";
import { IconSwitch } from "@/components/common";
import { TableCellContent } from "@/components/common/table/TableCellContent";
import type { Pipeline } from "../types/pipelines.types";

interface PipelineStatusCellProps {
  pipeline: Pipeline;
  onToggleActive: (id: string, active: boolean) => void;
  togglingPipelines: Record<string, boolean>;
}

export const PipelineStatusCell: React.FC<PipelineStatusCellProps> = ({
  pipeline,
  onToggleActive,
  togglingPipelines,
}) => {
  const status = pipeline.deploymentStatus;
  let color: "text.secondary" | "success.main" | "info.main" | "error.main" =
    "text.secondary";

  if (status === "DEPLOYED") {
    color = "success.main";
  } else if (status === "CREATING") {
    color = "info.main";
  } else if (status === "FAILED") {
    color = "error.main";
  }

  const isToggling = togglingPipelines[pipeline.id] || false;

  return (
    <TableCellContent variant="secondary">
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
        }}
      >
        {status !== "DEPLOYED" && (
          <Typography
            variant="body2"
            sx={{
              color: color,
              fontWeight: "medium",
            }}
          >
            {status || "N/A"}
          </Typography>
        )}

        {status === "DEPLOYED" && (
          <FormControlLabel
            control={
              <Box sx={{ position: "relative" }}>
                <IconSwitch
                  sx={{ m: 1 }}
                  size="small"
                  checked={pipeline.active !== false}
                  onChange={(e) =>
                    onToggleActive(pipeline.id, e.target.checked)
                  }
                  disabled={pipeline.system || isToggling}
                  onIcon={<PowerOnIcon />}
                  offIcon={<PowerOffIcon />}
                  onColor="#2b6cb0"
                  offColor="#757575"
                  trackOnColor="#b2ebf2"
                  trackOffColor="#cfd8dc"
                />
                {isToggling && (
                  <CircularProgress
                    size={24}
                    sx={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      marginTop: "-12px",
                      marginLeft: "-12px",
                      color: pipeline.active !== false ? "#2e7d32" : "#757575",
                    }}
                  />
                )}
              </Box>
            }
            label=""
            sx={{ mt: 1, ml: 0 }}
          />
        )}
      </Box>
    </TableCellContent>
  );
};
