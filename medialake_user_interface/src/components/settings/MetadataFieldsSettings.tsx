import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useDebounce } from "@/hooks/useDebounce";
import {
  Box,
  Typography,
  TextField,
  Switch,
  Button,
  CircularProgress,
  Alert,
  Snackbar,
  Chip,
  Menu,
  FormControlLabel,
  Checkbox,
  Badge,
} from "@mui/material";
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  ChevronRight as ChevronRightIcon,
  ExpandMore as ExpandMoreIcon,
  FilterList as FilterListIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
} from "@mui/icons-material";
import { useMetadataFieldsMapping } from "@/api/hooks/useMetadataFieldsMapping";
import { useMetadataFieldsConfig } from "@/api/hooks/useMetadataFieldsConfig";
import { useUpdateMetadataFieldsConfig } from "@/api/hooks/useUpdateMetadataFieldsConfig";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";

interface LocalFieldState {
  name: string;
  type: string;
  displayType: "string" | "number" | "date";
  displayName: string;
  isDisplayable: boolean;
  isFilterable: boolean;
  autoPopulateValues: boolean;
  predefinedValues?: string[];
}

const DEFAULT_FIELDS: LocalFieldState[] = [
  {
    name: "DigitalSourceAsset.Type",
    displayName: "Asset Type",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
    autoPopulateValues: false,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.Format",
    displayName: "File Format",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
    autoPopulateValues: false,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
    displayName: "File Size",
    type: "number",
    displayType: "number",
    isDisplayable: true,
    isFilterable: true,
    autoPopulateValues: false,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
    displayName: "File name",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
    autoPopulateValues: false,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
    displayName: "Created date",
    type: "date",
    displayType: "date",
    isDisplayable: true,
    isFilterable: true,
    autoPopulateValues: false,
  },
];

const DEFAULT_FIELD_NAMES = new Set(DEFAULT_FIELDS.map((f) => f.name));

interface FieldRowProps {
  field: LocalFieldState;
  isDefault: boolean;
  onChange?: (name: string, patch: Partial<LocalFieldState>) => void;
}

const FieldRow: React.FC<FieldRowProps> = React.memo(({ field, isDefault, onChange }) => (
  <Box
    sx={{
      display: "grid",
      gridTemplateColumns: "2fr 80px 1.5fr 140px 120px 160px",
      gap: 1,
      alignItems: "center",
      py: 0.75,
    }}
  >
    <Typography
      sx={{
        fontFamily: "monospace",
        fontSize: "0.75rem",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {field.name}
    </Typography>
    <Chip label={field.displayType} size="small" />
    <TextField
      size="small"
      value={field.displayName}
      onChange={(e) => onChange?.(field.name, { displayName: e.target.value })}
      disabled={isDefault}
    />
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <Switch
        size="small"
        checked={field.isDisplayable}
        onChange={(_, checked) => onChange?.(field.name, { isDisplayable: checked })}
        disabled={isDefault}
      />
      {isDefault && <Chip label="Default" size="small" color="primary" variant="outlined" />}
    </Box>
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <Switch
        size="small"
        checked={field.isFilterable}
        onChange={(_, checked) => onChange?.(field.name, { isFilterable: checked })}
        disabled={isDefault || !field.isDisplayable}
      />
      {isDefault && <Chip label="Default" size="small" color="primary" variant="outlined" />}
    </Box>
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <Switch
        size="small"
        checked={field.autoPopulateValues}
        onChange={(_, checked) => onChange?.(field.name, { autoPopulateValues: checked })}
        disabled={isDefault || !field.isFilterable || field.displayType !== "string"}
      />
      {field.autoPopulateValues && field.predefinedValues && field.predefinedValues.length > 0 && (
        <Chip
          label={`${field.predefinedValues.length} values`}
          size="small"
          color="info"
          variant="outlined"
        />
      )}
    </Box>
  </Box>
));

const COLUMN_HEADERS = (
  <Box
    sx={{
      display: "grid",
      gridTemplateColumns: "2fr 80px 1.5fr 140px 120px 160px",
      gap: 1,
      py: 0.5,
      mb: 0.5,
    }}
  >
    <Typography variant="caption" color="text.secondary">
      Field Path
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Type
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Display Name
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Asset Card Fields
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Allow Filtering
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Auto-populate Values
    </Typography>
  </Box>
);

const MetadataFieldsSettings: React.FC = () => {
  const { t } = useTranslation();
  const mappingQuery = useMetadataFieldsMapping();
  const configQuery = useMetadataFieldsConfig();
  const updateMutation = useUpdateMetadataFieldsConfig();

  const [localFields, setLocalFields] = useState<Record<string, LocalFieldState>>({});
  const [savedFields, setSavedFields] = useState<Record<string, LocalFieldState>>({});
  const [searchFilter, setSearchFilter] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string> | null>(null);

  // Initialize all groups as collapsed on first data load
  const groupKeys = useMemo(
    () =>
      Object.keys(localFields).reduce<Set<string>>((acc, name) => {
        const parts = name.split(".");
        acc.add(parts.length >= 2 ? `${parts[0]}.${parts[1]}` : parts[0]);
        return acc;
      }, new Set()),
    [localFields]
  );

  // On first load, collapse all groups
  useEffect(() => {
    if (collapsedGroups === null && groupKeys.size > 0) {
      setCollapsedGroups(new Set(groupKeys));
    }
  }, [groupKeys, collapsedGroups]);
  const [enabledFilter, setEnabledFilter] = useState<{ displayable: boolean; filterable: boolean }>(
    {
      displayable: false,
      filterable: false,
    }
  );
  const [filterAnchor, setFilterAnchor] = useState<null | HTMLElement>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info" | "warning";
  }>({ open: false, message: "", severity: "info" });

  const hasChangesRef = useRef(false);

  const showNotification = useCallback(
    (message: string, severity: "success" | "error" | "info" | "warning") => {
      setNotification({ open: true, message, severity });
    },
    []
  );

  // Merge mapping + config on load
  useEffect(() => {
    if (mappingQuery.isLoading || configQuery.isLoading) return;
    if (!mappingQuery.data?.data?.fields) return;
    // Don't overwrite unsaved local edits on auto-refetch
    if (hasChangesRef.current) return;

    const configMap = new Map((configQuery.data?.data?.fields ?? []).map((f) => [f.name, f]));

    const merged: Record<string, LocalFieldState> = {};
    for (const mf of mappingQuery.data.data.fields) {
      if (DEFAULT_FIELD_NAMES.has(mf.name)) continue;
      const saved = configMap.get(mf.name);
      merged[mf.name] = {
        name: mf.name,
        type: mf.type,
        displayType: mf.displayType,
        displayName: saved?.displayName ?? mf.name.split(".").pop() ?? mf.name,
        isDisplayable: saved?.isDisplayable ?? false,
        isFilterable: saved?.isFilterable ?? false,
        autoPopulateValues: saved?.autoPopulateValues ?? false,
        predefinedValues: saved?.predefinedValues,
      };
    }
    setLocalFields(merged);
    setSavedFields(merged);
  }, [mappingQuery.isLoading, configQuery.isLoading, mappingQuery.data, configQuery.data]);

  const hasChanges = useMemo(() => {
    const changed = JSON.stringify(localFields) !== JSON.stringify(savedFields);
    hasChangesRef.current = changed;
    return changed;
  }, [localFields, savedFields]);

  const handleFieldChange = useCallback((name: string, patch: Partial<LocalFieldState>) => {
    if (patch.isFilterable === true) {
      patch = { ...patch, isDisplayable: true };
    }
    if (patch.isDisplayable === false) {
      patch = { ...patch, isFilterable: false, autoPopulateValues: false };
    }
    if (patch.isFilterable === false) {
      patch = { ...patch, autoPopulateValues: false };
    }
    setLocalFields((prev) => ({
      ...prev,
      [name]: { ...prev[name], ...patch },
    }));
  }, []);

  const toggleGroup = useCallback((key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev ?? []);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }, []);

  const debouncedSearch = useDebounce(searchFilter, 150);

  const groupedFields = useMemo(() => {
    const filter = debouncedSearch.toLowerCase();
    const entries = Object.values(localFields).filter((f) => {
      if (filter && !f.name.toLowerCase().includes(filter)) return false;
      if (enabledFilter.displayable && !f.isDisplayable) return false;
      if (enabledFilter.filterable && !f.isFilterable) return false;
      return true;
    });
    const groups: Record<string, LocalFieldState[]> = {};
    for (const f of entries) {
      // Group by the first two segments (e.g., "Metadata.Embedded", "Metadata.Generated")
      const parts = f.name.split(".");
      const groupKey = parts.length >= 2 ? `${parts[0]}.${parts[1]}` : parts[0];
      (groups[groupKey] ??= []).push(f);
    }
    // Sort groups and fields alphabetically
    const sorted: Record<string, LocalFieldState[]> = {};
    for (const key of Object.keys(groups).sort()) {
      sorted[key] = groups[key].sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  }, [localFields, debouncedSearch, enabledFilter]);

  const handleRefreshFields = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const result = await mappingQuery.refetch();
      if (!result.data?.data?.fields) return;

      const newNames = new Set(result.data.data.fields.map((f) => f.name));
      setLocalFields((prev) => {
        const removedCount = Object.keys(prev).filter((k) => !newNames.has(k)).length;
        const next: Record<string, LocalFieldState> = {};
        for (const mf of result.data!.data.fields) {
          if (DEFAULT_FIELD_NAMES.has(mf.name)) continue;
          if (prev[mf.name]) {
            next[mf.name] = prev[mf.name];
          } else {
            next[mf.name] = {
              name: mf.name,
              type: mf.type,
              displayType: mf.displayType,
              displayName: mf.name.split(".").pop() ?? mf.name,
              isDisplayable: false,
              isFilterable: false,
              autoPopulateValues: false,
            };
          }
        }
        showNotification(
          removedCount > 0
            ? `${removedCount} field(s) removed because they no longer exist in the index`
            : "Fields refreshed — no changes",
          removedCount > 0 ? "warning" : "info"
        );
        return next;
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [mappingQuery, showNotification]);

  const handleSave = useCallback(async () => {
    const fields = Object.values(localFields)
      .filter((f) => f.isDisplayable || f.isFilterable)
      .map((f) => ({
        name: f.name,
        displayName: f.displayName,
        type: f.displayType,
        isDisplayable: f.isDisplayable,
        isFilterable: f.isFilterable && f.isDisplayable,
        autoPopulateValues: f.autoPopulateValues && f.isFilterable && f.displayType === "string",
        predefinedValues: f.predefinedValues,
      }));

    try {
      // Fetch distinct values from OpenSearch for fields with autoPopulateValues enabled
      const fieldsToPopulate = fields.filter((f) => f.autoPopulateValues);
      if (fieldsToPopulate.length > 0) {
        try {
          const response = await apiClient.post<{
            status: string;
            data: Record<string, string[]> | null;
          }>(API_ENDPOINTS.SEARCH_FIELDS_VALUES, {
            fields: fieldsToPopulate.map((f) => f.name),
          });

          if (response.data?.data) {
            for (const f of fields) {
              if (f.autoPopulateValues && response.data.data[f.name]) {
                f.predefinedValues = response.data.data[f.name];
              }
            }
          }
        } catch (valuesError) {
          // Values fetch failed — save will proceed but without populated values
          showNotification(
            "Could not fetch filter values from index. Saving config without pre-populated values.",
            "warning"
          );
        }
      }

      // Clear predefinedValues for fields that have autoPopulateValues disabled
      for (const f of fields) {
        if (!f.autoPopulateValues) {
          delete f.predefinedValues;
        }
      }

      await updateMutation.mutateAsync({ fields });

      // Build complete updated state from localFields + computed fields so both
      // localFields and savedFields are set synchronously in the same render batch,
      // avoiding transient inconsistency in the hasChanges comparison.
      const fieldMap = new Map(fields.map((f) => [f.name, f]));
      const nextState: Record<string, LocalFieldState> = {};
      for (const [key, entry] of Object.entries(localFields)) {
        const saved = fieldMap.get(key);
        const base: LocalFieldState = {
          name: entry.name,
          displayName: entry.displayName,
          type: entry.type,
          displayType: entry.displayType,
          isDisplayable: entry.isDisplayable,
          isFilterable: entry.isFilterable,
          autoPopulateValues: entry.autoPopulateValues,
        };
        if (saved?.predefinedValues && saved.autoPopulateValues) {
          base.predefinedValues = saved.predefinedValues;
        } else if (entry.predefinedValues && entry.autoPopulateValues) {
          base.predefinedValues = entry.predefinedValues;
        }
        // Strip predefinedValues when autoPopulateValues is off
        if (!base.autoPopulateValues) {
          delete base.predefinedValues;
        }
        nextState[key] = base;
      }
      setLocalFields(() => nextState);
      setSavedFields(() => nextState);

      showNotification("Metadata fields configuration saved successfully", "success");
    } catch (error) {
      console.error("Failed to save metadata fields configuration:", error);
      showNotification("Failed to save metadata fields configuration", "error");
    }
  }, [localFields, updateMutation, showNotification]);

  // Show loading on initial load OR when data is cached but localFields hasn't been populated yet
  const isInitializing =
    mappingQuery.isLoading ||
    configQuery.isLoading ||
    (!!mappingQuery.data?.data?.fields &&
      Object.keys(localFields).length === 0 &&
      !hasChangesRef.current);

  if (isInitializing) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          py: 8,
          gap: 1.5,
        }}
      >
        <CircularProgress size={32} />
        <Typography variant="body2" color="text.secondary">
          Loading metadata fields…
        </Typography>
      </Box>
    );
  }

  if (mappingQuery.error || configQuery.error) {
    return (
      <Alert severity="error" sx={{ my: 2 }}>
        Failed to load metadata fields. Please try refreshing the page.
      </Alert>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <Snackbar
        open={notification.open}
        autoHideDuration={4000}
        onClose={() => setNotification((n) => ({ ...n, open: false }))}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <Alert
          onClose={() => setNotification((n) => ({ ...n, open: false }))}
          severity={notification.severity}
          sx={{ width: "100%" }}
        >
          {notification.message}
        </Alert>
      </Snackbar>

      {/* Toolbar */}
      <Box
        sx={{
          display: "flex",
          gap: 1,
          p: 2,
          borderBottom: 1,
          borderColor: "divider",
          alignItems: "center",
        }}
      >
        <TextField
          size="small"
          placeholder={t(
            "settings.systemSettings.metadataFields.searchPlaceholder",
            "Search fields..."
          )}
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          sx={{ flex: 1, minWidth: 160 }}
        />
        <Badge
          badgeContent={(enabledFilter.displayable ? 1 : 0) + (enabledFilter.filterable ? 1 : 0)}
          color="primary"
          invisible={!enabledFilter.displayable && !enabledFilter.filterable}
          sx={{ "& .MuiBadge-badge": { fontSize: "0.625rem", height: 16, minWidth: 16 } }}
        >
          <Button
            variant="outlined"
            size="small"
            startIcon={<FilterListIcon />}
            endIcon={<KeyboardArrowDownIcon />}
            onClick={(e) => setFilterAnchor(e.currentTarget)}
          >
            Filter
          </Button>
        </Badge>
        <Menu
          open={Boolean(filterAnchor)}
          anchorEl={filterAnchor}
          onClose={() => setFilterAnchor(null)}
          anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
          transformOrigin={{ vertical: "top", horizontal: "left" }}
          slotProps={{ paper: { sx: { mt: 0.5, borderRadius: 2, minWidth: 220 } } }}
        >
          <Box sx={{ px: 2, py: 1 }}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                fontWeight: 600,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                fontSize: "0.6875rem",
              }}
            >
              Show only enabled
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={enabledFilter.displayable}
                  onChange={(_, checked) =>
                    setEnabledFilter((prev) => ({ ...prev, displayable: checked }))
                  }
                />
              }
              label={
                <Typography variant="body2" sx={{ fontSize: "0.8125rem" }}>
                  Asset Card Fields
                </Typography>
              }
              sx={{ display: "flex", mx: 0, mt: 0.5 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={enabledFilter.filterable}
                  onChange={(_, checked) =>
                    setEnabledFilter((prev) => ({ ...prev, filterable: checked }))
                  }
                />
              }
              label={
                <Typography variant="body2" sx={{ fontSize: "0.8125rem" }}>
                  Allow Filtering
                </Typography>
              }
              sx={{ display: "flex", mx: 0 }}
            />
          </Box>
        </Menu>
        <Button
          variant="outlined"
          onClick={handleRefreshFields}
          disabled={isRefreshing}
          startIcon={isRefreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
        >
          {isRefreshing ? "Refreshing…" : "Refresh Fields"}
        </Button>
      </Box>

      {/* Sticky column headers */}
      <Box
        sx={{
          px: 2,
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: "background.paper",
          zIndex: 1,
        }}
      >
        {COLUMN_HEADERS}
      </Box>

      {/* Scrollable field list */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 2, position: "relative" }}>
        {/* Loading overlay while refreshing */}
        {isRefreshing && (
          <Box
            sx={{
              position: "absolute",
              inset: 0,
              bgcolor: "rgba(255,255,255,0.7)",
              zIndex: 10,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 1.5,
              borderRadius: 1,
            }}
          >
            <CircularProgress size={32} />
            <Typography variant="body2" color="text.secondary">
              Refreshing fields from OpenSearch index…
            </Typography>
          </Box>
        )}
        {/* Default Fields section */}
        <Box
          sx={{
            border: 1,
            borderColor: "primary.light",
            borderRadius: 1,
            bgcolor: "primary.50",
            p: 1.5,
            mb: 2,
          }}
        >
          <Typography variant="subtitle2" color="primary" sx={{ mb: 1 }}>
            Default Fields (always available)
          </Typography>
          {DEFAULT_FIELDS.map((field) => (
            <FieldRow key={field.name} field={field} isDefault />
          ))}
        </Box>

        {/* Grouped fields */}
        {Object.entries(groupedFields).map(([groupKey, fields]) => (
          <Box key={groupKey}>
            <Box
              onClick={() => toggleGroup(groupKey)}
              sx={{
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 1,
                py: 1,
                borderBottom: 1,
                borderColor: "divider",
              }}
            >
              {collapsedGroups?.has(groupKey) ? <ChevronRightIcon /> : <ExpandMoreIcon />}
              <Typography variant="subtitle2">{groupKey}</Typography>
              <Typography variant="caption" color="text.secondary">
                ({fields.length} fields)
              </Typography>
            </Box>
            {!collapsedGroups?.has(groupKey) && (
              <Box sx={{ pl: 1 }}>
                {fields.map((field) => (
                  <FieldRow
                    key={field.name}
                    field={field}
                    isDefault={false}
                    onChange={handleFieldChange}
                  />
                ))}
              </Box>
            )}
          </Box>
        ))}
      </Box>

      {/* Footer */}
      <Box
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: "divider",
          display: "flex",
          justifyContent: "flex-end",
          gap: 1,
        }}
      >
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!hasChanges || updateMutation.isPending || isRefreshing}
          startIcon={updateMutation.isPending ? <CircularProgress size={16} /> : <SaveIcon />}
        >
          Save Changes
        </Button>
      </Box>
    </Box>
  );
};

export default MetadataFieldsSettings;
