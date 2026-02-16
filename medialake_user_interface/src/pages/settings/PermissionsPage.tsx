import React, { useCallback, useEffect, useState, useMemo } from "react";
import {
  Box,
  Typography,
  Button,
  TextField,
  InputAdornment,
  Alert,
  Snackbar,
  CircularProgress,
  ToggleButtonGroup,
  ToggleButton,
  FormControlLabel,
  Switch,
  Chip,
  Autocomplete,
  Checkbox,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import SaveIcon from "@mui/icons-material/Save";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import GroupIcon from "@mui/icons-material/Group";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { useTranslation } from "react-i18next";
import { PageHeader, PageContent } from "@/components/common/layout";
import { useGetGroups } from "@/api/hooks/useGroups";
import {
  useGetGroupPermissions,
  useUpdateGroupPermissions,
  GroupPermissionsData,
} from "@/api/hooks/useGroupPermissions";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { Group } from "@/api/types/group.types";
import { GroupSelector } from "@/features/settings/permissions/components/GroupSelector";
import { PermissionTable } from "@/features/settings/permissions/components/PermissionTable";
import { ComparisonTable } from "@/features/settings/permissions/components/ComparisonTable";
import { CreateGroupDialog } from "@/features/settings/permissions/components/CreateGroupDialog";
import { CopyPermissionsDialog } from "@/features/settings/permissions/components/CopyPermissionsDialog";
import { ContextualActionBar } from "@/features/settings/permissions/components/ContextualActionBar";
import {
  PermissionMatrix,
  AREAS,
  PERMISSION_TYPES,
  PermissionType,
  AreaId,
  isPermissionApplicable,
} from "@/features/settings/permissions/types/permissions.types";
import { useCreateGroup } from "@/api/hooks/useGroups";

// Types for change history
interface PermissionChange {
  areaId: string;
  type: PermissionType;
  previousValue: boolean;
  newValue: boolean;
}

const createEmptyMatrix = (): PermissionMatrix => {
  const matrix: PermissionMatrix = {};
  AREAS.forEach((area) => {
    matrix[area.id] = {};
    PERMISSION_TYPES.forEach((type) => {
      if (isPermissionApplicable(type.id, area.id)) {
        matrix[area.id][type.id] = false;
      }
    });
  });
  return matrix;
};

/**
 * Converts a backend permissions array (from the permission set API) into a PermissionMatrix.
 * Backend format: [{ action: "view", resource: "assets", effect: "Allow" }]
 * Frontend format: { assets: { view: true } }
 */
const permissionsArrayToMatrix = (
  permissions: Array<{ action: string; resource: string; effect: string }>
): PermissionMatrix => {
  const matrix = createEmptyMatrix();

  if (!permissions || !Array.isArray(permissions)) {
    return matrix;
  }

  permissions.forEach((perm) => {
    const resource = perm.resource?.toLowerCase();
    const action = perm.action?.toLowerCase();
    const allowed = perm.effect === "Allow";

    if (matrix[resource] !== undefined) {
      matrix[resource][action] = allowed;
    }
  });

  return matrix;
};

/**
 * Converts a PermissionMatrix into a backend permissions array.
 * Frontend format: { assets: { view: true } }
 * Backend format: [{ action: "view", resource: "assets", effect: "Allow" }]
 */
const matrixToPermissionsArray = (
  matrix: PermissionMatrix
): Array<{ action: string; resource: string; effect: string }> => {
  const permissions: Array<{ action: string; resource: string; effect: string }> = [];

  Object.entries(matrix).forEach(([areaId, perms]) => {
    Object.entries(perms).forEach(([action, allowed]) => {
      if (isPermissionApplicable(action as PermissionType, areaId as AreaId)) {
        permissions.push({
          action,
          resource: areaId,
          effect: allowed ? "Allow" : "Deny",
        });
      }
    });
  });

  return permissions;
};

const PermissionsPage: React.FC = () => {
  const { t } = useTranslation();

  // Fetch groups
  const { data: groups = [], isLoading: isLoadingGroups, error: groupsError } = useGetGroups();
  const createGroupMutation = useCreateGroup();
  const updatePermissionsMutation = useUpdateGroupPermissions();

  // View mode: 'single' or 'compare'
  const [viewMode, setViewMode] = useState<"single" | "compare">("single");

  // Single group mode state
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [matrix, setMatrix] = useState<PermissionMatrix>(createEmptyMatrix());

  // Comparison mode state
  const [comparisonGroupIds, setComparisonGroupIds] = useState<string[]>([]);
  const [showDifferencesOnly, setShowDifferencesOnly] = useState(false);

  // Store all group permissions (keyed by group ID)
  const [allGroupPermissions, setAllGroupPermissions] = useState<Record<string, PermissionMatrix>>(
    {}
  );

  // Common state
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveMessage, setSaveMessage] = useState("Permissions saved successfully!");
  const [saveSeverity, setSaveSeverity] = useState<"success" | "error">("success");

  // Change tracking
  const [changeHistory, setChangeHistory] = useState<PermissionChange[]>([]);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);

  // Fetch permissions for the selected group
  const { data: groupPermissionsData, isLoading: isLoadingPermissions } =
    useGetGroupPermissions(selectedGroupId);

  // Auto-select first group when groups load
  useEffect(() => {
    if (groups.length > 0 && !selectedGroupId) {
      setSelectedGroupId(groups[0].id);
      if (groups.length >= 2) {
        setComparisonGroupIds([groups[0].id, groups[1].id]);
      } else {
        setComparisonGroupIds([groups[0].id]);
      }
    }
  }, [groups, selectedGroupId]);

  // Load permissions when group permissions data arrives
  useEffect(() => {
    if (groupPermissionsData && selectedGroupId) {
      const permMatrix = permissionsArrayToMatrix(groupPermissionsData.permissions || []);
      setMatrix(permMatrix);
      setAllGroupPermissions((prev) => ({
        ...prev,
        [selectedGroupId]: permMatrix,
      }));
      setHasChanges(false);
      setChangeHistory([]);
      if (groupPermissionsData.updatedAt) {
        setLastSavedAt(new Date(groupPermissionsData.updatedAt));
      } else {
        setLastSavedAt(null);
      }
    }
  }, [groupPermissionsData, selectedGroupId]);

  // Fetch permissions for comparison groups that aren't loaded yet
  useEffect(() => {
    if (viewMode !== "compare") return;

    const fetchMissing = async () => {
      for (const gId of comparisonGroupIds) {
        if (allGroupPermissions[gId]) continue; // already loaded

        try {
          const { data } = await apiClient.get<any>(API_ENDPOINTS.GROUP_PERMISSIONS.GET(gId));
          let parsed: GroupPermissionsData | null = null;

          if (typeof data.body === "string") {
            const body = JSON.parse(data.body);
            parsed = body.data || body;
          } else if (data.body?.data) {
            parsed = data.body.data;
          } else if (data.data) {
            parsed = data.data;
          }

          if (parsed) {
            const permMatrix = permissionsArrayToMatrix(parsed.permissions || []);
            setAllGroupPermissions((prev) => ({ ...prev, [gId]: permMatrix }));
          }
        } catch (err) {
          console.error(`Failed to fetch permissions for group ${gId}:`, err);
        }
      }
    };

    fetchMissing();
  }, [viewMode, comparisonGroupIds, allGroupPermissions]);

  const selectedGroup = useMemo(
    () => groups.find((g) => g.id === selectedGroupId),
    [groups, selectedGroupId]
  );

  // Compute actual diff count: how many permissions differ from the saved state
  const actualChangeCount = useMemo(() => {
    const saved = allGroupPermissions[selectedGroupId] || createEmptyMatrix();
    let count = 0;
    for (const area of AREAS) {
      for (const type of PERMISSION_TYPES) {
        if (!isPermissionApplicable(type.id, area.id)) continue;
        const savedVal = !!saved[area.id]?.[type.id];
        const currentVal = !!matrix[area.id]?.[type.id];
        if (savedVal !== currentVal) count++;
      }
    }
    return count;
  }, [matrix, allGroupPermissions, selectedGroupId]);

  const handleViewModeChange = (
    _: React.MouseEvent<HTMLElement>,
    newMode: "single" | "compare" | null
  ) => {
    if (newMode !== null) {
      if (hasChanges) {
        if (
          window.confirm(
            t(
              "permissions.unsavedWarning",
              "You have unsaved changes. Are you sure you want to switch modes?"
            )
          )
        ) {
          setViewMode(newMode);
          setHasChanges(false);
          setChangeHistory([]);
        }
      } else {
        setViewMode(newMode);
      }
    }
  };

  const handleGroupChange = (groupId: string) => {
    if (hasChanges) {
      if (
        window.confirm(
          t(
            "permissions.unsavedWarning",
            "You have unsaved changes. Are you sure you want to switch groups?"
          )
        )
      ) {
        setSelectedGroupId(groupId);
        setHasChanges(false);
        setChangeHistory([]);
      }
    } else {
      setSelectedGroupId(groupId);
    }
  };

  const handleComparisonGroupsChange = (_: React.SyntheticEvent, newValue: Group[]) => {
    if (newValue.length <= 3) {
      setComparisonGroupIds(newValue.map((g) => g.id));
    }
  };

  const handleCreateGroup = async (
    groupData: { name: string; id: string; description: string },
    copyFromGroupId?: string
  ) => {
    try {
      await createGroupMutation.mutateAsync({
        name: groupData.name,
        id: groupData.id,
        description: groupData.description,
      });

      // If copying from another group, save those permissions to the new group
      if (copyFromGroupId && allGroupPermissions[copyFromGroupId]) {
        const copiedPermissions = { ...allGroupPermissions[copyFromGroupId] };
        const permArray = matrixToPermissionsArray(copiedPermissions);

        await updatePermissionsMutation.mutateAsync({
          groupId: groupData.id,
          permissions: permArray,
        });
      }

      setSelectedGroupId(groupData.id);
      setLastSavedAt(new Date());
      setSaveSeverity("success");
      setSaveMessage(t("permissions.groupCreated", { name: groupData.name }));
      setSaveSuccess(true);
    } catch (err) {
      console.error("Error creating group:", err);
      setSaveSeverity("error");
      setSaveMessage(t("permissions.createError", "Error creating group. Please try again."));
      setSaveSuccess(true);
    }
  };

  const handleCopyPermissions = async (sourceGroupId: string, targetGroupId: string) => {
    const sourcePermissions = allGroupPermissions[sourceGroupId];
    if (sourcePermissions) {
      const copiedPermissions: PermissionMatrix = {};
      Object.keys(sourcePermissions).forEach((areaId) => {
        copiedPermissions[areaId] = { ...sourcePermissions[areaId] };
      });

      // Save to backend
      const permArray = matrixToPermissionsArray(copiedPermissions);
      try {
        await updatePermissionsMutation.mutateAsync({
          groupId: targetGroupId,
          permissions: permArray,
        });

        setAllGroupPermissions((prev) => ({
          ...prev,
          [targetGroupId]: copiedPermissions,
        }));

        if (viewMode === "single" && selectedGroupId === targetGroupId) {
          setMatrix(copiedPermissions);
        }

        const sourceGroup = groups.find((g) => g.id === sourceGroupId);
        const targetGroup = groups.find((g) => g.id === targetGroupId);
        setLastSavedAt(new Date());
        setSaveMessage(`Permissions copied from ${sourceGroup?.name} to ${targetGroup?.name}!`);
        setSaveSuccess(true);
      } catch (err) {
        console.error("Error copying permissions:", err);
        setSaveSeverity("error");
        setSaveMessage(t("permissions.copyError", "Error copying permissions. Please try again."));
        setSaveSuccess(true);
      }
    } else {
      setSaveSeverity("error");
      setSaveMessage(
        t(
          "permissions.copySourceNotLoaded",
          "Source group permissions not loaded. Select the source group first."
        )
      );
      setSaveSuccess(true);
    }
  };

  // Single mode handlers with change tracking
  const handleTogglePermission = (areaId: string, type: PermissionType) => {
    if (!isPermissionApplicable(type, areaId as AreaId)) return;

    const previousValue = !!matrix[areaId]?.[type];
    const newValue = !previousValue;

    setChangeHistory((prev) => [...prev, { areaId, type, previousValue, newValue }]);
    setMatrix((prev) => ({
      ...prev,
      [areaId]: { ...prev[areaId], [type]: newValue },
    }));
    setHasChanges(true);
  };

  const handleToggleRow = (areaId: string, selected: boolean) => {
    const applicablePermissions = PERMISSION_TYPES.filter((type) =>
      isPermissionApplicable(type.id, areaId as AreaId)
    );

    applicablePermissions.forEach((type) => {
      const previousValue = !!matrix[areaId]?.[type.id];
      if (previousValue !== selected) {
        setChangeHistory((prev) => [
          ...prev,
          { areaId, type: type.id, previousValue, newValue: selected },
        ]);
      }
    });

    setMatrix((prev) => {
      const newAreaPermissions = { ...prev[areaId] };
      applicablePermissions.forEach((type) => {
        newAreaPermissions[type.id] = selected;
      });
      return { ...prev, [areaId]: newAreaPermissions };
    });
    setHasChanges(true);
  };

  const handleToggleColumn = (typeId: PermissionType, selected: boolean) => {
    const applicableAreas = AREAS.filter((area) => isPermissionApplicable(typeId, area.id));

    applicableAreas.forEach((area) => {
      const previousValue = !!matrix[area.id]?.[typeId];
      if (previousValue !== selected) {
        setChangeHistory((prev) => [
          ...prev,
          { areaId: area.id, type: typeId, previousValue, newValue: selected },
        ]);
      }
    });

    setMatrix((prev) => {
      const newMatrix = { ...prev };
      applicableAreas.forEach((area) => {
        newMatrix[area.id] = { ...newMatrix[area.id], [typeId]: selected };
      });
      return newMatrix;
    });
    setHasChanges(true);
  };

  // Undo last change
  const handleUndo = useCallback(() => {
    if (changeHistory.length === 0) return;

    const lastChange = changeHistory[changeHistory.length - 1];
    setMatrix((prev) => ({
      ...prev,
      [lastChange.areaId]: {
        ...prev[lastChange.areaId],
        [lastChange.type]: lastChange.previousValue,
      },
    }));
    setChangeHistory((prev) => prev.slice(0, -1));
  }, [changeHistory]);

  // Discard all changes
  const handleDiscard = () => {
    if (window.confirm(t("permissions.discardConfirm", "Discard all unsaved changes?"))) {
      const savedPermissions = allGroupPermissions[selectedGroupId] || createEmptyMatrix();
      setMatrix(savedPermissions);
      setHasChanges(false);
      setChangeHistory([]);
    }
  };

  // Comparison mode handler
  const handleComparisonTogglePermission = (
    groupId: string,
    areaId: string,
    type: PermissionType
  ) => {
    if (!isPermissionApplicable(type, areaId as AreaId)) return;

    setAllGroupPermissions((prev) => ({
      ...prev,
      [groupId]: {
        ...prev[groupId],
        [areaId]: {
          ...prev[groupId]?.[areaId],
          [type]: !prev[groupId]?.[areaId]?.[type],
        },
      },
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      if (viewMode === "single") {
        const permArray = matrixToPermissionsArray(matrix);
        await updatePermissionsMutation.mutateAsync({
          groupId: selectedGroupId,
          permissions: permArray,
        });
        setAllGroupPermissions((prev) => ({
          ...prev,
          [selectedGroupId]: { ...matrix },
        }));
      } else {
        // Comparison mode: save all modified groups
        const savePromises = comparisonGroupIds.map(async (gId) => {
          const groupMatrix = allGroupPermissions[gId];
          if (!groupMatrix) return;
          const permArray = matrixToPermissionsArray(groupMatrix);
          await updatePermissionsMutation.mutateAsync({
            groupId: gId,
            permissions: permArray,
          });
        });
        await Promise.all(savePromises);
      }

      setHasChanges(false);
      setChangeHistory([]);
      setLastSavedAt(new Date());
      setSaveSeverity("success");
      setSaveMessage(t("permissions.saved", "Permissions saved successfully!"));
      setSaveSuccess(true);
    } catch (err) {
      console.error("Error saving permissions:", err);
      setSaveSeverity("error");
      setSaveMessage(t("permissions.saveError", "Error saving permissions"));
      setSaveSuccess(true);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    if (window.confirm(t("permissions.resetConfirm", "Reset all changes to last saved state?"))) {
      if (viewMode === "single") {
        const savedPermissions = allGroupPermissions[selectedGroupId] || createEmptyMatrix();
        setMatrix(savedPermissions);
      }
      setHasChanges(false);
      setChangeHistory([]);
    }
  };

  const filteredAreas = AREAS.filter(
    (area) =>
      area.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      area.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isPageLoading = isLoadingGroups || (viewMode === "single" && isLoadingPermissions);

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flex: 1,
        width: "100%",
        position: "relative",
        maxWidth: "100%",
        p: 3,
      }}
    >
      <PageHeader
        title={t("permissions.title", "Permission Management")}
        description={t(
          "permissions.description",
          "Manage access levels and granular permissions for different groups in the platform."
        )}
      />

      <PageContent isLoading={isLoadingGroups} error={groupsError as Error}>
        {/* View Mode Toggle */}
        <Box
          sx={{
            mb: 3,
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
            alignItems: { xs: "flex-start", sm: "center" },
            justifyContent: "space-between",
          }}
        >
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            aria-label="view mode"
            size="small"
          >
            <ToggleButton value="single" aria-label="single group view">
              <GroupIcon sx={{ fontSize: 18, mr: 1 }} />
              {t("permissions.singleGroup", "Single Group")}
            </ToggleButton>
            <ToggleButton value="compare" aria-label="comparison view">
              <CompareArrowsIcon sx={{ fontSize: 18, mr: 1 }} />
              {t("permissions.compareGroups", "Compare Groups")}
            </ToggleButton>
          </ToggleButtonGroup>

          <Button
            variant="outlined"
            startIcon={<ContentCopyIcon />}
            onClick={() => setCopyDialogOpen(true)}
          >
            {t("permissions.copyPermissions", "Copy Permissions")}
          </Button>
        </Box>

        {/* Group Selection */}
        {viewMode === "single" ? (
          <Box sx={{ mb: 3 }}>
            <GroupSelector
              groups={groups}
              selectedGroupId={selectedGroupId}
              onGroupChange={handleGroupChange}
              onCreateGroupClick={() => setCreateDialogOpen(true)}
            />
          </Box>
        ) : (
          <Box
            sx={{
              mb: 3,
              p: 2.5,
              bgcolor: "background.paper",
              borderRadius: 2,
              border: 1,
              borderColor: "divider",
            }}
          >
            <Box
              sx={{
                display: "flex",
                flexDirection: { xs: "column", md: "row" },
                gap: 2,
                alignItems: { xs: "flex-start", md: "center" },
                justifyContent: "space-between",
              }}
            >
              <Box sx={{ flex: 1, width: { xs: "100%", md: "auto" }, maxWidth: { md: 500 } }}>
                <Typography variant="subtitle2" sx={{ mb: 1, color: "text.secondary" }}>
                  {t("permissions.selectGroupsCompare", "Select groups to compare (max 3)")}
                </Typography>
                <Autocomplete
                  multiple
                  options={groups}
                  value={groups.filter((g) => comparisonGroupIds.includes(g.id))}
                  onChange={handleComparisonGroupsChange}
                  getOptionLabel={(option) => option.name}
                  disableCloseOnSelect
                  renderOption={(props, option, { selected }) => (
                    <li {...props}>
                      <Checkbox size="small" checked={selected} sx={{ mr: 1 }} />
                      {option.name}
                    </li>
                  )}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      placeholder={t("permissions.selectGroupsPlaceholder", "Select groups...")}
                      size="small"
                    />
                  )}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip
                        label={option.name}
                        size="small"
                        {...getTagProps({ index })}
                        key={option.id}
                      />
                    ))
                  }
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={showDifferencesOnly}
                    onChange={(e) => setShowDifferencesOnly(e.target.checked)}
                    color="warning"
                  />
                }
                label={
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <span>{t("permissions.differencesOnly", "Differences Only")}</span>
                    {showDifferencesOnly && (
                      <Chip
                        label="Active"
                        size="small"
                        color="warning"
                        sx={{ height: 20, "& .MuiChip-label": { fontSize: "10px" } }}
                      />
                    )}
                  </Box>
                }
              />
            </Box>
          </Box>
        )}

        {/* Permission Table */}
        <Box
          sx={{
            bgcolor: "background.paper",
            borderRadius: 2,
            boxShadow: 1,
            border: 1,
            borderColor: "divider",
            overflow: "hidden",
          }}
        >
          {/* Contextual Action Bar */}
          {viewMode === "single" ? (
            <ContextualActionBar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              hasChanges={actualChangeCount > 0}
              changeCount={actualChangeCount}
              loading={loading}
              groupName={selectedGroup?.name || "Unknown"}
              lastSavedAt={lastSavedAt}
              onSave={handleSave}
              onDiscard={handleDiscard}
              onUndo={handleUndo}
              canUndo={changeHistory.length > 0}
            />
          ) : (
            <Box
              sx={{
                p: 2,
                borderBottom: 1,
                borderColor: "divider",
                display: "flex",
                flexDirection: { xs: "column", sm: "row" },
                gap: 2,
                justifyContent: "space-between",
                alignItems: "center",
                bgcolor: "background.paper",
              }}
            >
              <TextField
                placeholder={t("permissions.filterAreas", "Filter areas...")}
                size="small"
                variant="outlined"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                    </InputAdornment>
                  ),
                }}
                sx={{ width: { xs: "100%", sm: 288 } }}
              />

              <Box
                sx={{
                  display: "flex",
                  gap: 1,
                  width: { xs: "100%", sm: "auto" },
                  justifyContent: "flex-end",
                }}
              >
                <Button
                  variant="outlined"
                  color="inherit"
                  startIcon={<RestartAltIcon />}
                  onClick={handleReset}
                  disabled={!hasChanges || loading}
                >
                  {t("common.reset", "Reset")}
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={
                    loading ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />
                  }
                  onClick={handleSave}
                  disabled={!hasChanges || loading}
                >
                  {t("common.saveChanges", "Save Changes")}
                </Button>
              </Box>
            </Box>
          )}

          <Box sx={{ position: "relative", minHeight: 400 }}>
            {(loading || isPageLoading) && (
              <Box
                sx={{
                  position: "absolute",
                  inset: 0,
                  bgcolor: "rgba(255, 255, 255, 0.8)",
                  zIndex: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CircularProgress />
              </Box>
            )}

            {viewMode === "single" ? (
              <PermissionTable
                areas={filteredAreas}
                matrix={matrix}
                onTogglePermission={handleTogglePermission}
                onToggleRow={handleToggleRow}
                onToggleColumn={handleToggleColumn}
              />
            ) : (
              <ComparisonTable
                areas={filteredAreas}
                groups={groups}
                selectedGroupIds={comparisonGroupIds}
                allGroupPermissions={allGroupPermissions}
                showDifferencesOnly={showDifferencesOnly}
                onTogglePermission={handleComparisonTogglePermission}
              />
            )}
          </Box>
        </Box>

        {/* Dialogs */}
        <CreateGroupDialog
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
          onCreateGroup={handleCreateGroup}
          existingGroups={groups}
        />

        <CopyPermissionsDialog
          open={copyDialogOpen}
          onClose={() => setCopyDialogOpen(false)}
          onCopyPermissions={handleCopyPermissions}
          groups={groups}
        />

        <Snackbar
          open={saveSuccess}
          autoHideDuration={4000}
          onClose={() => setSaveSuccess(false)}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        >
          <Alert onClose={() => setSaveSuccess(false)} severity={saveSeverity} variant="filled">
            {saveMessage}
          </Alert>
        </Snackbar>
      </PageContent>
    </Box>
  );
};

export default PermissionsPage;
