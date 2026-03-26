import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
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
} from "@mui/material";
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  ChevronRight as ChevronRightIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import { useMetadataFieldsMapping } from "@/api/hooks/useMetadataFieldsMapping";
import { useMetadataFieldsConfig } from "@/api/hooks/useMetadataFieldsConfig";
import { useUpdateMetadataFieldsConfig } from "@/api/hooks/useUpdateMetadataFieldsConfig";

interface LocalFieldState {
  name: string;
  type: string;
  displayType: "string" | "number" | "date";
  displayName: string;
  isDisplayable: boolean;
  isFilterable: boolean;
}

const DEFAULT_FIELDS: LocalFieldState[] = [
  {
    name: "DigitalSourceAsset.Type",
    displayName: "Asset Type",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.Format",
    displayName: "File Format",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
    displayName: "File Size",
    type: "number",
    displayType: "number",
    isDisplayable: true,
    isFilterable: true,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
    displayName: "File name",
    type: "keyword",
    displayType: "string",
    isDisplayable: true,
    isFilterable: true,
  },
  {
    name: "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
    displayName: "Created date",
    type: "date",
    displayType: "date",
    isDisplayable: true,
    isFilterable: true,
  },
];

const DEFAULT_FIELD_NAMES = new Set(DEFAULT_FIELDS.map((f) => f.name));

interface FieldRowProps {
  field: LocalFieldState;
  isDefault: boolean;
  onChange?: (name: string, patch: Partial<LocalFieldState>) => void;
}

const FieldRow: React.FC<FieldRowProps> = ({ field, isDefault, onChange }) => (
  <Box
    sx={{
      display: "grid",
      gridTemplateColumns: "2fr 80px 1.5fr 140px 120px",
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
  </Box>
);

const COLUMN_HEADERS = (
  <Box
    sx={{
      display: "grid",
      gridTemplateColumns: "2fr 80px 1.5fr 140px 120px",
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
      Show in Dropdown
    </Typography>
    <Typography variant="caption" color="text.secondary">
      Allow Filtering
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
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
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
      patch = { ...patch, isFilterable: false };
    }
    setLocalFields((prev) => ({
      ...prev,
      [name]: { ...prev[name], ...patch },
    }));
  }, []);

  const toggleGroup = useCallback((key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }, []);

  const groupedFields = useMemo(() => {
    const filter = searchFilter.toLowerCase();
    const entries = Object.values(localFields).filter(
      (f) => !filter || f.name.toLowerCase().includes(filter)
    );
    const groups: Record<string, LocalFieldState[]> = {};
    for (const f of entries) {
      const groupKey = f.name.split(".")[0];
      (groups[groupKey] ??= []).push(f);
    }
    // Sort groups and fields alphabetically
    const sorted: Record<string, LocalFieldState[]> = {};
    for (const key of Object.keys(groups).sort()) {
      sorted[key] = groups[key].sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  }, [localFields, searchFilter]);

  const handleRefreshFields = useCallback(async () => {
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
      }));

    try {
      await updateMutation.mutateAsync({ fields });
      setSavedFields({ ...localFields });
      showNotification("Metadata fields configuration saved successfully", "success");
    } catch {
      showNotification("Failed to save metadata fields configuration", "error");
    }
  }, [localFields, updateMutation, showNotification]);

  if (mappingQuery.isLoading || configQuery.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
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
      <Box sx={{ display: "flex", gap: 1, p: 2, borderBottom: 1, borderColor: "divider" }}>
        <TextField
          size="small"
          placeholder={t(
            "settings.systemSettings.metadataFields.searchPlaceholder",
            "Search fields..."
          )}
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          sx={{ flex: 1 }}
        />
        <Button variant="outlined" onClick={handleRefreshFields} startIcon={<RefreshIcon />}>
          Refresh Fields
        </Button>
      </Box>

      {/* Scrollable field list */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
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
          {COLUMN_HEADERS}
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
              {collapsedGroups.has(groupKey) ? <ChevronRightIcon /> : <ExpandMoreIcon />}
              <Typography variant="subtitle2">{groupKey}</Typography>
              <Typography variant="caption" color="text.secondary">
                ({fields.length} fields)
              </Typography>
            </Box>
            {!collapsedGroups.has(groupKey) && (
              <Box sx={{ pl: 1 }}>
                {COLUMN_HEADERS}
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
          disabled={!hasChanges || updateMutation.isPending}
          startIcon={updateMutation.isPending ? <CircularProgress size={16} /> : <SaveIcon />}
        >
          Save Changes
        </Button>
      </Box>
    </Box>
  );
};

export default MetadataFieldsSettings;
