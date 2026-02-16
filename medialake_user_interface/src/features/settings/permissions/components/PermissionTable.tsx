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
} from "@mui/material";
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

  return (
    <TableContainer component={Paper} elevation={0} sx={{ overflow: "hidden", border: 0 }}>
      <Table size="small" stickyHeader aria-label="permissions table">
        <TableHead>
          <TableRow>
            {/* Full Access Header */}
            <TableCell align="center" sx={{ py: 1.5, px: 1.5, width: 85, bgcolor: "action.hover" }}>
              <Tooltip title={isAllSelected() ? "Revoke all permissions" : "Grant all permissions"}>
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
                    fontWeight="bold"
                    color="text.secondary"
                    sx={{ fontSize: "11px" }}
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

            <TableCell sx={{ py: 1.5, px: 2, minWidth: 160, bgcolor: "action.hover" }}>
              <Typography variant="body2" fontWeight="bold">
                Area / Module
              </Typography>
            </TableCell>

            {PERMISSION_TYPES.map((type) => (
              <TableCell
                key={type.id}
                align="center"
                sx={{ py: 1.5, px: 1, minWidth: 75, bgcolor: "action.hover" }}
              >
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 0.5,
                  }}
                >
                  <Typography variant="caption" fontWeight="bold" sx={{ fontSize: "12px" }}>
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
            const activeCount = applicablePermissions.filter((t) => matrix[area.id]?.[t.id]).length;

            return (
              <TableRow
                key={area.id}
                hover
                sx={{
                  backgroundColor: rowSelected ? "rgba(59, 130, 246, 0.04)" : "inherit",
                  "&:hover": {
                    backgroundColor: rowSelected ? "rgba(59, 130, 246, 0.08)" : undefined,
                  },
                }}
              >
                {/* Full Access Switch for Row */}
                <TableCell
                  align="center"
                  sx={{ py: 1, px: 1, borderRight: 1, borderColor: "divider" }}
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
                      <Typography variant="body2" fontWeight="medium">
                        {area.label}
                      </Typography>
                      <Typography variant="caption" color="text.disabled" sx={{ fontSize: "11px" }}>
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
                        sx={{ py: 1, px: 1, backgroundColor: "action.disabledBackground" }}
                      >
                        <Tooltip title={`${type.label} does not apply to ${area.label}`}>
                          <Box
                            sx={{ display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            <RemoveIcon sx={{ fontSize: 14, color: "text.disabled" }} />
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
                <Typography variant="body2" color="text.secondary">
                  No areas found matching your search.
                </Typography>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
