import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import {
  Box,
  Tooltip,
  IconButton,
  Typography,
  Chip,
  FormControlLabel,
} from "@mui/material";
import { IconSwitch } from "@/components/common";
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from "@mui/icons-material";
import { TableCellContent } from "@/components/common/table";
import { format } from "date-fns";
import { Pipeline } from "../types/pipelines.types";
import { TriggerTypeChips } from "../components";

interface UsePipelineColumnsProps {
  onEdit: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onToggleActive: (id: string, active: boolean) => void;
}

const columnHelper = createColumnHelper<Pipeline>();

export const usePipelineColumns = ({
  onEdit,
  onDelete,
  onToggleActive,
}: UsePipelineColumnsProps) => {
  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Name",
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="primary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("type", {
        header: "Type",
        size: 150,
        enableSorting: true,
        cell: (info) => {
          // Get the pipeline object
          const pipeline = info.row.original;

          // Parse the comma-separated list into an array
          const triggerTypes = info.getValue().split(",");

          // Always display as "Event Triggered" regardless of the original value
          const displayTypes = triggerTypes.map(() => "Event Triggered");

          return (
            <TableCellContent variant="secondary">
              <TriggerTypeChips
                triggerTypes={displayTypes}
                eventRuleInfo={pipeline.eventRuleInfo}
                pipeline={pipeline}
              />
            </TableCellContent>
          );
        },
      }),
      // columnHelper.accessor('system', {
      //     header: 'System',
      //     size: 100,
      //     enableSorting: true,
      //     cell: info => (
      //         <TableCellContent variant="secondary">
      //             <Chip
      //                 label={info.getValue() ? 'Yes' : 'No'}
      //                 size="small"
      //                 color={info.getValue() ? 'success' : 'default'}
      //             />
      //         </TableCellContent>
      //     ),
      // }),
      columnHelper.accessor("deploymentStatus", {
        header: "Status",
        size: 150, // Increased size to accommodate the switch
        enableSorting: true,
        cell: (info) => {
          const status = info.getValue();
          const pipeline = info.row.original;
          let color:
            | "text.secondary"
            | "success.main"
            | "info.main"
            | "error.main" = "text.secondary";

          if (status === "DEPLOYED") {
            color = "success.main";
          } else if (status === "CREATING") {
            color = "info.main";
          } else if (status === "FAILED") {
            color = "error.main";
          }

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
                      <IconSwitch
                        size="small"
                        checked={pipeline.active !== false}
                        onChange={(e) =>
                          onToggleActive(pipeline.id, e.target.checked)
                        }
                        disabled={pipeline.system}
                        onIcon={<CheckCircleIcon />}
                        offIcon={<CancelIcon />}
                        onColor="#2b6cb0"
                        offColor="#757575"
                        trackOnColor="#b2ebf2"
                        trackOffColor="#cfd8dc"
                      />
                    }
                    // label={pipeline.active !== false ? "Active" : "Inactive"}
                    label=""
                    sx={{ mt: 0, ml: 0 }}
                  />
                )}
              </Box>
            </TableCellContent>
          );
        },
      }),
      columnHelper.accessor("createdAt", {
        header: "Created",
        size: 180,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip
              title={format(new Date(dateValue), "MMM dd, yyyy HH:mm")}
              placement="top"
            >
              <Box>
                <TableCellContent variant="secondary">
                  {format(new Date(dateValue), "MMM dd, yyyy")}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor("updatedAt", {
        header: "Updated",
        size: 180,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip
              title={format(new Date(dateValue), "MMM dd, yyyy HH:mm")}
              placement="top"
            >
              <Box>
                <TableCellContent variant="secondary">
                  {format(new Date(dateValue), "MMM dd, yyyy")}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        size: 120,
        cell: (info) => (
          <Box sx={{ display: "flex", gap: 1 }} className="action-buttons">
            <Tooltip
              title={
                info.row.original.deploymentStatus &&
                !["DEPLOYED", "FAILED"].includes(
                  info.row.original.deploymentStatus,
                )
                  ? "Cannot edit pipeline while it's being created"
                  : "Edit Pipeline"
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={() => onEdit(info.row.original.id)}
                  disabled={
                    info.row.original.deploymentStatus &&
                    !["DEPLOYED", "FAILED"].includes(
                      info.row.original.deploymentStatus,
                    )
                  }
                >
                  <EditIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip
              title={
                info.row.original.deploymentStatus &&
                !["DEPLOYED", "FAILED"].includes(
                  info.row.original.deploymentStatus,
                )
                  ? "Cannot delete pipeline while it's being created"
                  : "Delete Pipeline"
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={() =>
                    onDelete(info.row.original.id, info.row.original.name)
                  }
                  disabled={
                    info.row.original.system ||
                    (info.row.original.deploymentStatus &&
                      !["DEPLOYED", "FAILED"].includes(
                        info.row.original.deploymentStatus,
                      ))
                  }
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        ),
      }),
    ],
    [onEdit, onDelete, onToggleActive],
  );
};

export const defaultColumnVisibility = {
  name: true,
  type: true,
  system: true,
  deploymentStatus: true,
  createdAt: true,
  updatedAt: true,
  actions: true,
};
