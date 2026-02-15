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
} from "@mui/material";
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
  return (
    <Box
      sx={{
        px: 2.5,
        py: 1.5,
        bgcolor: "action.hover",
        borderBottom: 1,
        borderColor: "divider",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 2.5,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
        <InfoOutlinedIcon sx={{ fontSize: 14, color: "text.secondary" }} />
        <Typography variant="caption" fontWeight="medium" color="text.secondary">
          Legend:
        </Typography>
      </Box>

      {selectedGroups.map((group, idx) => (
        <Box key={group.id} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box
            sx={{
              width: 16,
              height: 16,
              borderRadius: 0.5,
              border: 1,
              backgroundColor: GROUP_COLORS[idx % GROUP_COLORS.length].headerHex,
              borderColor: GROUP_COLORS[idx % GROUP_COLORS.length].headerHex,
            }}
          />
          <Typography variant="caption" color={GROUP_COLORS[idx % GROUP_COLORS.length].text}>
            {group.name}
          </Typography>
        </Box>
      ))}

      <Box sx={{ width: 1, height: 16, bgcolor: "divider", mx: 0.5 }} />

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
        <Box
          sx={{
            width: 16,
            height: 16,
            borderRadius: 0.5,
            border: 1,
            backgroundColor: "#fef3c7",
            borderColor: "#fcd34d",
          }}
        />
        <Typography variant="caption" color="warning.dark">
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
  const selectedGroups = groups.filter((g) => selectedGroupIds.includes(g.id));

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
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography color="text.secondary">
          {t("permissions.selectOneGroup", "Select at least one group to compare.")}
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <ComparisonLegend selectedGroups={selectedGroups} />

      <TableContainer component={Paper} elevation={0} sx={{ overflow: "auto", border: 0 }}>
        <Table stickyHeader aria-label="group comparison table" size="small">
          <TableHead>
            <TableRow>
              <TableCell
                rowSpan={2}
                sx={{
                  bgcolor: "action.hover",
                  fontWeight: "bold",
                  minWidth: 180,
                  borderRight: 1,
                  borderColor: "divider",
                  verticalAlign: "bottom",
                }}
              >
                Area / Module
              </TableCell>
              {selectedGroups.map((group, idx) => (
                <TableCell
                  key={group.id}
                  colSpan={PERMISSION_TYPES.length}
                  align="center"
                  sx={{
                    bgcolor: GROUP_COLORS[idx % GROUP_COLORS.length].header,
                    borderRight: 1,
                    borderColor: "divider",
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
                      fontWeight="bold"
                      color={GROUP_COLORS[idx % GROUP_COLORS.length].text}
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
                      bgcolor: GROUP_COLORS[groupIdx % GROUP_COLORS.length].bg,
                      fontSize: "0.7rem",
                      px: 0.5,
                      minWidth: 60,
                      borderRight: typeIdx === PERMISSION_TYPES.length - 1 ? 1 : 0,
                      borderColor: "divider",
                      "&:last-child": { borderRight: 0 },
                    }}
                  >
                    <Tooltip title={type.label} placement="top">
                      <Typography variant="caption" color="text.secondary" fontWeight="medium">
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
                  hover
                  sx={{ bgcolor: hasDiff ? "rgba(255, 152, 0, 0.04)" : "inherit" }}
                >
                  <TableCell
                    component="th"
                    scope="row"
                    sx={{ borderRight: 1, borderColor: "divider", bgcolor: "background.paper" }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Typography variant="body2" fontWeight="medium">
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
                            sx={{ height: 20, "& .MuiChip-label": { fontSize: "10px" } }}
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
                              bgcolor: "action.disabledBackground",
                              borderRight: typeIdx === PERMISSION_TYPES.length - 1 ? 1 : 0,
                              borderColor: "divider",
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
                                <RemoveIcon sx={{ fontSize: 14, color: "text.disabled" }} />
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
                            bgcolor: isDifferent
                              ? "rgba(255, 152, 0, 0.12)"
                              : GROUP_COLORS[groupIdx % GROUP_COLORS.length].bg,
                            borderRight: typeIdx === PERMISSION_TYPES.length - 1 ? 1 : 0,
                            borderColor: "divider",
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
                  sx={{ py: 4 }}
                >
                  <Typography variant="body2" color="text.secondary">
                    {showDifferencesOnly
                      ? "No differences found between selected groups."
                      : "No areas found matching your search."}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
