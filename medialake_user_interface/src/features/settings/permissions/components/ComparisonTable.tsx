import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  Typography,
  Chip,
  Tooltip,
  Box,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import RemoveIcon from "@mui/icons-material/Remove";
import { useTranslation } from "react-i18next";
import {
  PermissionMatrix,
  PermissionArea,
  PermissionType,
  PERMISSION_TYPES,
  GROUP_COLORS,
  isPermissionApplicable,
} from "../types/permissions.types";
import { Group } from "@/api/types/group.types";

interface ComparisonTableProps {
  areas: PermissionArea[];
  groups: Group[];
  selectedGroupIds: string[];
  allGroupPermissions: Record<string, PermissionMatrix>;
  showDifferencesOnly: boolean;
  onTogglePermission: (groupId: string, areaId: string, type: PermissionType) => void;
}

function ComparisonLegend({ selectedGroups }: { selectedGroups: Group[] }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  return (
    <Box
      sx={{
        px: 2.5,
        py: 1.5,
        backgroundColor: isDark
          ? alpha(theme.palette.background.default, 0.5)
          : alpha(theme.palette.background.default, 0.6),
        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 2.5,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
        <InfoOutlinedIcon sx={{ fontSize: 14, color: theme.palette.text.secondary }} />
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            color: theme.palette.text.secondary,
            letterSpacing: "0.02em",
          }}
        >
          Legend:
        </Typography>
      </Box>

      {selectedGroups.map((group, idx) => (
        <Box key={group.id} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box
            sx={{
              width: 16,
              height: 16,
              borderRadius: "4px",
              border: `1px solid ${GROUP_COLORS[idx % GROUP_COLORS.length].headerHex}`,
              backgroundColor: GROUP_COLORS[idx % GROUP_COLORS.length].headerHex,
            }}
          />
          <Typography
            variant="caption"
            sx={{
              color: GROUP_COLORS[idx % GROUP_COLORS.length].text,
              fontWeight: 500,
            }}
          >
            {group.name}
          </Typography>
        </Box>
      ))}

      <Box
        sx={{
          width: 1,
          height: 16,
          bgcolor: alpha(theme.palette.divider, 0.2),
          mx: 0.5,
        }}
      />

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
        <Box
          sx={{
            width: 16,
            height: 16,
            borderRadius: "4px",
            border: `1px solid ${theme.palette.warning.main}`,
            backgroundColor: alpha(theme.palette.warning.main, 0.12),
          }}
        />
        <Typography variant="caption" sx={{ color: theme.palette.warning.dark, fontWeight: 500 }}>
          Differs between groups
        </Typography>
      </Box>
    </Box>
  );
}

export function ComparisonTable({
  areas,
  groups,
  selectedGroupIds,
  allGroupPermissions,
  showDifferencesOnly,
  onTogglePermission,
}: ComparisonTableProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const selectedGroups = groups.filter((g) => selectedGroupIds.includes(g.id));

  // Consistent header background matching ResizableTable
  const headerBg = isDark
    ? alpha(theme.palette.background.default, 0.95)
    : alpha(theme.palette.background.paper, 0.95);

  const hasPermissionDifference = (areaId: string, typeId: PermissionType): boolean => {
    if (selectedGroupIds.length < 2) return false;
    if (!isPermissionApplicable(typeId, areaId)) return false;
    const values = selectedGroupIds.map(
      (groupId) => allGroupPermissions[groupId]?.[areaId]?.[typeId] ?? false
    );
    return !values.every((v) => v === values[0]);
  };

  const hasAreaDifference = (areaId: string): boolean => {
    return PERMISSION_TYPES.filter((type) => isPermissionApplicable(type.id, areaId)).some((type) =>
      hasPermissionDifference(areaId, type.id)
    );
  };

  const filteredAreas = showDifferencesOnly
    ? areas.filter((area) => hasAreaDifference(area.id))
    : areas;

  const getDifferenceCount = (areaId: string): number => {
    return PERMISSION_TYPES.filter(
      (type) => isPermissionApplicable(type.id, areaId) && hasPermissionDifference(areaId, type.id)
    ).length;
  };

  if (selectedGroupIds.length === 0) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 4,
          textAlign: "center",
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          borderRadius: "12px",
          backgroundColor: isDark
            ? alpha(theme.palette.background.paper, 0.2)
            : theme.palette.background.paper,
        }}
      >
        <Typography color="text.secondary">
          {t("permissions.selectOneGroup", "Select at least one group to compare.")}
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      elevation={0}
      sx={{
        overflow: "hidden",
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        borderRadius: "12px",
        backgroundColor: isDark
          ? alpha(theme.palette.background.paper, 0.2)
          : theme.palette.background.paper,
      }}
    >
      <ComparisonLegend selectedGroups={selectedGroups} />

      <TableContainer sx={{ overflow: "auto" }}>
        <Table
          stickyHeader
          aria-label="group comparison table"
          size="small"
          sx={{
            borderSpacing: 0,
            "& .MuiTableCell-root": {
              borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
              fontSize: "0.8125rem",
              backgroundColor: "transparent",
            },
          }}
        >
          <TableHead>
            <TableRow>
              <TableCell
                rowSpan={2}
                sx={{
                  backgroundColor: `${headerBg} !important`,
                  fontWeight: 600,
                  minWidth: 180,
                  borderRight: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                  borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                  verticalAlign: "bottom",
                  color: theme.palette.text.primary,
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 600,
                    color: theme.palette.text.primary,
                    letterSpacing: "0.01em",
                  }}
                >
                  Area / Module
                </Typography>
              </TableCell>
              {selectedGroups.map((group, idx) => (
                <TableCell
                  key={group.id}
                  colSpan={PERMISSION_TYPES.length}
                  align="center"
                  sx={{
                    backgroundColor: `${GROUP_COLORS[idx % GROUP_COLORS.length].header} !important`,
                    borderRight: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                    "&:last-child": { borderRight: 0 },
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 1,
                      py: 0.5,
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 600,
                        color: GROUP_COLORS[idx % GROUP_COLORS.length].text,
                        letterSpacing: "0.01em",
                      }}
                    >
                      {group.name}
                    </Typography>
                  </Box>
                </TableCell>
              ))}
            </TableRow>

            <TableRow>
              {selectedGroups.map((group, groupIdx) =>
                PERMISSION_TYPES.map((type, typeIdx) => (
                  <TableCell
                    key={`${group.id}-${type.id}`}
                    align="center"
                    sx={{
                      backgroundColor: `${
                        GROUP_COLORS[groupIdx % GROUP_COLORS.length].bg
                      } !important`,
                      fontSize: "0.6875rem",
                      px: 0.5,
                      minWidth: 60,
                      borderRight:
                        typeIdx === PERMISSION_TYPES.length - 1
                          ? `1px solid ${alpha(theme.palette.divider, 0.1)}`
                          : 0,
                      borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                      "&:last-child": { borderRight: 0 },
                    }}
                  >
                    <Tooltip title={type.label} placement="top">
                      <Typography
                        variant="caption"
                        sx={{
                          color: theme.palette.text.secondary,
                          fontWeight: 500,
                          fontSize: "0.6875rem",
                        }}
                      >
                        {type.label.substring(0, 3)}
                      </Typography>
                    </Tooltip>
                  </TableCell>
                ))
              )}
            </TableRow>
          </TableHead>

          <TableBody>
            {filteredAreas.map((area) => {
              const hasDiff = hasAreaDifference(area.id);
              const diffCount = getDifferenceCount(area.id);

              return (
                <TableRow
                  key={area.id}
                  sx={{
                    backgroundColor: hasDiff ? alpha(theme.palette.warning.main, 0.04) : "inherit",
                    transition: "background-color 0.2s ease",
                    "&:hover": {
                      backgroundColor: hasDiff
                        ? alpha(theme.palette.warning.main, 0.08)
                        : alpha(theme.palette.primary.main, 0.04),
                    },
                  }}
                >
                  <TableCell
                    component="th"
                    scope="row"
                    sx={{
                      borderRight: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                      backgroundColor: isDark
                        ? alpha(theme.palette.background.paper, 0.3)
                        : theme.palette.background.paper,
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 500,
                          color: theme.palette.text.primary,
                        }}
                      >
                        {area.label}
                      </Typography>
                      {hasDiff && (
                        <Tooltip
                          title={`${diffCount} permission${
                            diffCount > 1 ? "s" : ""
                          } differ across groups`}
                        >
                          <Chip
                            icon={<WarningAmberIcon sx={{ fontSize: 12 }} />}
                            label={`${diffCount} diff`}
                            size="small"
                            color="warning"
                            variant="outlined"
                            sx={{
                              height: 22,
                              borderRadius: "6px",
                              "& .MuiChip-label": {
                                fontSize: "0.625rem",
                                fontWeight: 600,
                                px: 0.75,
                              },
                              "& .MuiChip-icon": { ml: 0.5 },
                            }}
                          />
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>

                  {selectedGroups.map((group, groupIdx) =>
                    PERMISSION_TYPES.map((type, typeIdx) => {
                      const isApplicable = isPermissionApplicable(type.id, area.id);
                      const isChecked =
                        allGroupPermissions[group.id]?.[area.id]?.[type.id] ?? false;
                      const isDifferent = hasPermissionDifference(area.id, type.id);

                      if (!isApplicable) {
                        return (
                          <TableCell
                            key={`${group.id}-${area.id}-${type.id}`}
                            align="center"
                            sx={{
                              backgroundColor: isDark
                                ? alpha(theme.palette.background.default, 0.3)
                                : alpha(theme.palette.action.disabledBackground, 0.4),
                              borderRight:
                                typeIdx === PERMISSION_TYPES.length - 1
                                  ? `1px solid ${alpha(theme.palette.divider, 0.1)}`
                                  : 0,
                              "&:last-child": { borderRight: 0 },
                            }}
                          >
                            <Tooltip title={`${type.label} does not apply to ${area.label}`}>
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                              >
                                <RemoveIcon
                                  sx={{
                                    fontSize: 14,
                                    color: alpha(theme.palette.text.disabled, 0.5),
                                  }}
                                />
                              </Box>
                            </Tooltip>
                          </TableCell>
                        );
                      }

                      return (
                        <TableCell
                          key={`${group.id}-${area.id}-${type.id}`}
                          align="center"
                          padding="checkbox"
                          sx={{
                            backgroundColor: isDifferent
                              ? alpha(theme.palette.warning.main, 0.12)
                              : GROUP_COLORS[groupIdx % GROUP_COLORS.length].bg,
                            borderRight:
                              typeIdx === PERMISSION_TYPES.length - 1
                                ? `1px solid ${alpha(theme.palette.divider, 0.1)}`
                                : 0,
                            "&:last-child": { borderRight: 0 },
                          }}
                        >
                          <Tooltip title={`${group.name}: ${type.label}`}>
                            <Checkbox
                              checked={isChecked}
                              onChange={() => onTogglePermission(group.id, area.id, type.id)}
                              color="primary"
                              size="small"
                            />
                          </Tooltip>
                        </TableCell>
                      );
                    })
                  )}
                </TableRow>
              );
            })}

            {filteredAreas.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={1 + selectedGroups.length * PERMISSION_TYPES.length}
                  align="center"
                  sx={{ py: 6 }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 1,
                    }}
                  >
                    <Box
                      sx={{
                        width: 56,
                        height: 56,
                        borderRadius: "50%",
                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        mb: 1,
                      }}
                    >
                      <RemoveIcon sx={{ fontSize: 28, color: theme.palette.primary.main }} />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {showDifferencesOnly
                        ? "No differences found between selected groups."
                        : "No areas found matching your search."}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
