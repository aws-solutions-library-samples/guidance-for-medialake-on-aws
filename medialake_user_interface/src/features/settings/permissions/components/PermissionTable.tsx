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
  Tooltip,
  Box,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import RemoveIcon from "@mui/icons-material/Remove";
import {
  PermissionMatrix,
  PermissionArea,
  PermissionType,
  AreaId,
  PERMISSION_TYPES,
  isPermissionApplicable,
} from "../types/permissions.types";

interface PermissionTableProps {
  areas: PermissionArea[];
  matrix: PermissionMatrix;
  onTogglePermission: (areaId: string, type: PermissionType) => void;
  onToggleRow: (areaId: string, selected: boolean) => void;
  onToggleColumn: (type: PermissionType, selected: boolean) => void;
  onToggleAll?: (selected: boolean) => void;
}

export function PermissionTable({
  areas,
  matrix,
  onTogglePermission,
  onToggleRow,
  onToggleColumn,
  onToggleAll,
}: PermissionTableProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const getApplicablePermissions = (areaId: AreaId) => {
    return PERMISSION_TYPES.filter((type) => isPermissionApplicable(type.id, areaId));
  };

  const isRowSelected = (areaId: string) => {
    const applicable = getApplicablePermissions(areaId as AreaId);
    return applicable.every((type) => matrix[areaId]?.[type.id]);
  };

  const isRowIndeterminate = (areaId: string) => {
    const applicable = getApplicablePermissions(areaId as AreaId);
    const selectedCount = applicable.filter((type) => matrix[areaId]?.[type.id]).length;
    return selectedCount > 0 && selectedCount < applicable.length;
  };

  const isColumnSelected = (typeId: PermissionType) => {
    const applicableAreas = areas.filter((area) => isPermissionApplicable(typeId, area.id));
    if (applicableAreas.length === 0) return false;
    return applicableAreas.every((area) => matrix[area.id]?.[typeId]);
  };

  const isColumnIndeterminate = (typeId: PermissionType) => {
    const applicableAreas = areas.filter((area) => isPermissionApplicable(typeId, area.id));
    if (applicableAreas.length === 0) return false;
    const selectedCount = applicableAreas.filter((area) => matrix[area.id]?.[typeId]).length;
    return selectedCount > 0 && selectedCount < applicableAreas.length;
  };

  const isAllSelected = () => {
    return areas.every((area) => isRowSelected(area.id));
  };

  const handleToggleAll = (checked: boolean) => {
    if (onToggleAll) {
      onToggleAll(checked);
    } else {
      areas.forEach((area) => {
        onToggleRow(area.id, checked);
      });
    }
  };

  // Consistent header background matching ResizableTable
  const headerBg = isDark
    ? alpha(theme.palette.background.default, 0.95)
    : alpha(theme.palette.background.paper, 0.95);

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
      <TableContainer sx={{ overflow: "auto" }}>
        <Table
          size="small"
          stickyHeader
          aria-label="permissions table"
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
              {/* Full Access Header */}
              <TableCell
                align="center"
                sx={{
                  py: 1.5,
                  px: 1.5,
                  width: 85,
                  backgroundColor: `${headerBg} !important`,
                  borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                  fontWeight: 600,
                }}
              >
                <Tooltip
                  title={isAllSelected() ? "Revoke all permissions" : "Grant all permissions"}
                >
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 0.5,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.6875rem",
                        fontWeight: 600,
                        color: theme.palette.text.primary,
                        letterSpacing: "0.02em",
                        textTransform: "uppercase",
                      }}
                    >
                      Full Access
                    </Typography>
                    <Checkbox
                      checked={isAllSelected()}
                      indeterminate={
                        !isAllSelected() &&
                        areas.some((a) => isRowIndeterminate(a.id) || isRowSelected(a.id))
                      }
                      onChange={(e) => handleToggleAll(e.target.checked)}
                      color="primary"
                      size="small"
                      sx={{ p: 0.5 }}
                    />
                  </Box>
                </Tooltip>
              </TableCell>

              <TableCell
                sx={{
                  py: 1.5,
                  px: 2,
                  minWidth: 160,
                  backgroundColor: `${headerBg} !important`,
                  borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                  fontWeight: 600,
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

              {PERMISSION_TYPES.map((type) => (
                <TableCell
                  key={type.id}
                  align="center"
                  sx={{
                    py: 1.5,
                    px: 1,
                    minWidth: 75,
                    backgroundColor: `${headerBg} !important`,
                    borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                    fontWeight: 600,
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 0.5,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: theme.palette.text.primary,
                        letterSpacing: "0.01em",
                      }}
                    >
                      {type.label}
                    </Typography>
                    <Checkbox
                      size="small"
                      checked={isColumnSelected(type.id)}
                      indeterminate={isColumnIndeterminate(type.id)}
                      onChange={(e) => onToggleColumn(type.id, e.target.checked)}
                      sx={{ p: 0.5 }}
                    />
                  </Box>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {areas.map((area) => {
              const rowSelected = isRowSelected(area.id);
              const applicablePermissions = getApplicablePermissions(area.id);
              const activeCount = applicablePermissions.filter(
                (t) => matrix[area.id]?.[t.id]
              ).length;

              return (
                <TableRow
                  key={area.id}
                  sx={{
                    backgroundColor: rowSelected
                      ? alpha(theme.palette.primary.main, 0.04)
                      : "inherit",
                    transition: "background-color 0.2s ease",
                    "&:hover": {
                      backgroundColor: rowSelected
                        ? alpha(theme.palette.primary.main, 0.08)
                        : alpha(theme.palette.primary.main, 0.04),
                    },
                  }}
                >
                  {/* Full Access Switch for Row */}
                  <TableCell
                    align="center"
                    sx={{
                      py: 1,
                      px: 1,
                      borderRight: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    }}
                  >
                    <Tooltip
                      title={
                        rowSelected
                          ? `Revoke all ${area.label} permissions`
                          : `Grant full ${area.label} access`
                      }
                    >
                      <Checkbox
                        checked={rowSelected}
                        indeterminate={isRowIndeterminate(area.id)}
                        onChange={(e) => onToggleRow(area.id, e.target.checked)}
                        color="primary"
                        size="small"
                        sx={{ p: 0.5 }}
                      />
                    </Tooltip>
                  </TableCell>

                  <TableCell sx={{ py: 1, px: 2 }}>
                    <Tooltip title={area.description} placement="right">
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
                        <Typography
                          variant="caption"
                          sx={{
                            fontSize: "0.6875rem",
                            color: theme.palette.text.disabled,
                            fontWeight: 400,
                          }}
                        >
                          {activeCount}/{applicablePermissions.length}
                        </Typography>
                      </Box>
                    </Tooltip>
                  </TableCell>

                  {PERMISSION_TYPES.map((type) => {
                    const isApplicable = isPermissionApplicable(type.id, area.id);
                    const isChecked = !!matrix[area.id]?.[type.id];

                    if (!isApplicable) {
                      return (
                        <TableCell
                          key={`${area.id}-${type.id}`}
                          align="center"
                          sx={{
                            py: 1,
                            px: 1,
                            backgroundColor: isDark
                              ? alpha(theme.palette.background.default, 0.3)
                              : alpha(theme.palette.action.disabledBackground, 0.4),
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
                        key={`${area.id}-${type.id}`}
                        align="center"
                        padding="none"
                        sx={{ py: 1, px: 1 }}
                      >
                        <Checkbox
                          checked={isChecked}
                          onChange={() => onTogglePermission(area.id, type.id)}
                          color="primary"
                          size="small"
                          sx={{ p: 0.5 }}
                        />
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}

            {areas.length === 0 && (
              <TableRow>
                <TableCell colSpan={PERMISSION_TYPES.length + 2} align="center" sx={{ py: 6 }}>
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
                      No areas found matching your search.
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
