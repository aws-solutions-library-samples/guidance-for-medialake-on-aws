import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { createColumnHelper } from "@tanstack/react-table";
import { Box, Tooltip, IconButton, Typography, Chip, Switch } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { colorTokens } from "@/theme/tokens";
import {
  EditOutlined as EditIcon,
  DeleteOutlineRounded as DeleteIcon,
  CircleRounded as CircleIcon,
} from "@mui/icons-material";
import { TableCellContent } from "@/components/common/table";
import { format, formatDistanceToNow } from "date-fns";
import { Pipeline } from "../types/pipelines.types";
import { TriggerTypeChips } from "../components";

interface UsePipelineColumnsProps {
  onEdit: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onToggleActive: (id: string, active: boolean) => void;
}

const columnHelper = createColumnHelper<Pipeline>();

/** Ensure UTC timestamps without a Z suffix are parsed as UTC */
const parseUtcDate = (value: string): Date => {
  if (
    value &&
    !value.endsWith("Z") &&
    !value.includes("+") &&
    !/\d{2}:\d{2}$/.test(value.slice(-6))
  ) {
    return new Date(value + "Z");
  }
  return new Date(value);
};

export const usePipelineColumns = ({
  onEdit,
  onDelete,
  onToggleActive,
}: UsePipelineColumnsProps) => {
  const { t } = useTranslation();

  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: t("common.columns.name"),
        size: 220,
        enableSorting: true,
        cell: ({ getValue }) => {
          const name = getValue();
          return (
            <TableCellContent variant="primary">
              <Tooltip title={name} enterDelay={400} arrow>
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    wordBreak: "break-word",
                    lineHeight: 1.4,
                  }}
                >
                  {name}
                </Typography>
              </Tooltip>
            </TableCellContent>
          );
        },
      }),
      columnHelper.accessor("type", {
        header: t("common.columns.type"),
        size: 220,
        enableSorting: true,
        cell: (info) => {
          const pipeline = info.row.original;
          const triggerTypes = info
            .getValue()
            .split(",")
            .map((t: string) => t.trim());

          return (
            <TableCellContent variant="secondary">
              <TriggerTypeChips
                triggerTypes={triggerTypes}
                eventRuleInfo={pipeline.eventRuleInfo}
                pipeline={pipeline}
              />
            </TableCellContent>
          );
        },
      }),

      columnHelper.accessor("deploymentStatus", {
        header: t("common.columns.status"),
        size: 120,
        enableSorting: true,
        cell: (info) => {
          const status = info.getValue();
          const pipeline = info.row.original;
          const isActive = pipeline.active !== false;

          if (status === "DEPLOYED") {
            return (
              <TableCellContent variant="secondary">
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Switch
                    size="small"
                    checked={isActive}
                    onChange={() => onToggleActive(pipeline.id, !isActive)}
                    disabled={pipeline.system}
                    sx={{
                      "& .MuiSwitch-switchBase.Mui-checked": {
                        color: "success.main",
                      },
                      "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
                        backgroundColor: "success.main",
                      },
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 500,
                      fontSize: "0.75rem",
                      color: isActive ? colorTokens.success.dark : "text.disabled",
                    }}
                  >
                    {isActive ? "Active" : "Inactive"}
                  </Typography>
                </Box>
              </TableCellContent>
            );
          }

          const statusConfig: Record<string, { color: string; bg: string; border: string }> = {
            CREATING: {
              color: colorTokens.info.main,
              bg: alpha(colorTokens.info.main, 0.08),
              border: alpha(colorTokens.info.main, 0.2),
            },
            FAILED: {
              color: colorTokens.error.main,
              bg: alpha(colorTokens.error.main, 0.08),
              border: alpha(colorTokens.error.main, 0.2),
            },
            DELETING: {
              color: colorTokens.warning.main,
              bg: alpha(colorTokens.warning.main, 0.08),
              border: alpha(colorTokens.warning.main, 0.2),
            },
          };

          const config = statusConfig[status || ""] || {
            color: "text.secondary",
            bg: "transparent",
            border: "divider",
          };

          return (
            <TableCellContent variant="secondary">
              <Chip
                icon={
                  <CircleIcon
                    sx={{
                      fontSize: "8px !important",
                      color: `${config.color} !important`,
                    }}
                  />
                }
                label={status || "N/A"}
                size="small"
                sx={{
                  height: 26,
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  color: config.color,
                  bgcolor: config.bg,
                  border: "1px solid",
                  borderColor: config.border,
                  "& .MuiChip-icon": { ml: 0.5 },
                  "& .MuiChip-label": { px: 0.75 },
                }}
              />
            </TableCellContent>
          );
        },
      }),

      columnHelper.accessor("createdAt", {
        header: t("common.columns.created"),
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          const date = parseUtcDate(dateValue);
          const relative = formatDistanceToNow(date, { addSuffix: true });
          const absolute = format(date, "MMM dd, yyyy 'at' h:mm a");

          return (
            <Tooltip title={absolute} placement="top" arrow>
              <Box>
                <TableCellContent variant="secondary">
                  <Typography
                    variant="body2"
                    sx={{ fontSize: "0.8125rem", color: "text.secondary" }}
                  >
                    {relative}
                  </Typography>
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),

      columnHelper.accessor("updatedAt", {
        header: t("common.columns.updated"),
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          const date = parseUtcDate(dateValue);
          const relative = formatDistanceToNow(date, { addSuffix: true });
          const absolute = format(date, "MMM dd, yyyy 'at' h:mm a");

          return (
            <Tooltip title={absolute} placement="top" arrow>
              <Box>
                <TableCellContent variant="secondary">
                  <Typography
                    variant="body2"
                    sx={{ fontSize: "0.8125rem", color: "text.secondary" }}
                  >
                    {relative}
                  </Typography>
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),

      columnHelper.display({
        id: "actions",
        header: t("common.columns.actions"),
        size: 100,
        cell: (info) => {
          const pipeline = info.row.original;
          const isDeploying =
            pipeline.deploymentStatus &&
            !["DEPLOYED", "FAILED"].includes(pipeline.deploymentStatus);

          return (
            <Box
              sx={{
                display: "flex",
                gap: 0.5,
                opacity: 0.6,
                transition: "opacity 0.15s ease",
                "tr:hover &": { opacity: 1 },
              }}
              className="action-buttons"
            >
              <Tooltip
                title={isDeploying ? "Cannot edit while deploying" : t("common.editPipeline")}
                arrow
              >
                <span>
                  <IconButton
                    size="small"
                    onClick={() => onEdit(pipeline.id)}
                    disabled={isDeploying}
                    sx={{
                      color: "text.secondary",
                      "&:hover": {
                        color: "primary.main",
                        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08),
                      },
                    }}
                  >
                    <EditIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip
                title={isDeploying ? "Cannot delete while deploying" : t("common.deletePipeline")}
                arrow
              >
                <span>
                  <IconButton
                    size="small"
                    onClick={() => onDelete(pipeline.id, pipeline.name)}
                    disabled={pipeline.system || isDeploying}
                    sx={{
                      color: "text.secondary",
                      "&:hover": {
                        color: "error.main",
                        bgcolor: (theme) => alpha(theme.palette.error.main, 0.08),
                      },
                    }}
                  >
                    <DeleteIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          );
        },
      }),
    ],
    [onEdit, onDelete, onToggleActive, t]
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
