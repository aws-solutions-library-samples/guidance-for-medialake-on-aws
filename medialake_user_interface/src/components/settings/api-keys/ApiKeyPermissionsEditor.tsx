import React from "react";
import {
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ApiKeyPermissions } from "@/api/types/apiKey.types";

/**
 * Permission categories with their resource:action keys.
 * Matches the authorizer's permission mapping exactly.
 */
const PERMISSION_CATEGORIES: Record<string, { label: string; permissions: string[] }> = {
  assets: {
    label: "Assets",
    permissions: [
      "assets:view",
      "assets:upload",
      "assets:edit",
      "assets:delete",
      "assets:download",
    ],
  },
  collections: {
    label: "Collections",
    permissions: [
      "collections:view",
      "collections:create",
      "collections:edit",
      "collections:delete",
    ],
  },
  connectors: {
    label: "Connectors",
    permissions: ["connectors:view", "connectors:create", "connectors:edit", "connectors:delete"],
  },
  pipelines: {
    label: "Pipelines",
    permissions: [
      "pipelines:view",
      "pipelines:create",
      "pipelines:edit",
      "pipelines:delete",
      "pipelinesExecutions:view",
      "pipelinesExecutions:retry",
    ],
  },
  search: {
    label: "Search",
    permissions: ["search:view"],
  },
  settings: {
    label: "Settings",
    permissions: [
      "api-keys:view",
      "api-keys:create",
      "api-keys:edit",
      "api-keys:delete",
      "collection-types:view",
      "collection-types:create",
      "collection-types:edit",
      "collection-types:delete",
      "system:view",
      "system:edit",
    ],
  },
  users: {
    label: "Users & Permissions",
    permissions: [
      "users:view",
      "users:edit",
      "users:delete",
      "groups:view",
      "groups:create",
      "groups:edit",
      "groups:delete",
      "permissions:view",
      "permissions:create",
      "permissions:edit",
      "permissions:delete",
    ],
  },
  other: {
    label: "Other",
    permissions: [
      "environments:view",
      "environments:create",
      "environments:edit",
      "environments:delete",
      "integrations:view",
      "integrations:create",
      "integrations:edit",
      "integrations:delete",
      "nodes:view",
      "reviews:view",
      "reviews:edit",
      "reviews:delete",
      "storage:view",
      "regions:view",
    ],
  },
};

/** Extract the action part from a resource:action key */
const getActionLabel = (permission: string): string => {
  const action = permission.split(":")[1] || permission;
  return action.charAt(0).toUpperCase() + action.slice(1);
};

/** Get the resource prefix for display */
const getResourcePrefix = (permission: string): string => {
  return permission.split(":")[0];
};

interface ApiKeyPermissionsEditorProps {
  permissions: ApiKeyPermissions;
  onChange: (permissions: ApiKeyPermissions) => void;
  disabled?: boolean;
}

const ApiKeyPermissionsEditor: React.FC<ApiKeyPermissionsEditorProps> = ({
  permissions,
  onChange,
  disabled = false,
}) => {
  const handleToggle = (key: string) => {
    onChange({
      ...permissions,
      [key]: !permissions[key],
    });
  };

  const handleToggleCategory = (categoryPerms: string[], checked: boolean) => {
    const updated = { ...permissions };
    categoryPerms.forEach((perm) => {
      updated[perm] = checked;
    });
    onChange(updated);
  };

  const getCategoryCount = (categoryPerms: string[]): number => {
    return categoryPerms.filter((p) => permissions[p]).length;
  };

  return (
    <Box>
      {Object.entries(PERMISSION_CATEGORIES).map(([key, category]) => {
        const enabledCount = getCategoryCount(category.permissions);
        const allChecked = enabledCount === category.permissions.length;
        const someChecked = enabledCount > 0 && !allChecked;

        return (
          <Accordion
            key={key}
            disableGutters
            variant="outlined"
            sx={{ "&:before": { display: "none" } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box display="flex" alignItems="center" gap={1} width="100%">
                <Checkbox
                  checked={allChecked}
                  indeterminate={someChecked}
                  disabled={disabled}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => handleToggleCategory(category.permissions, e.target.checked)}
                  size="small"
                />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>
                  {category.label}
                </Typography>
                <Chip
                  label={`${enabledCount}/${category.permissions.length}`}
                  size="small"
                  color={enabledCount > 0 ? "primary" : "default"}
                  variant={allChecked ? "filled" : "outlined"}
                  sx={{ mr: 1 }}
                />
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              <FormGroup>
                {/* Group permissions by resource prefix within the category */}
                {(() => {
                  const grouped: Record<string, string[]> = {};
                  category.permissions.forEach((perm) => {
                    const prefix = getResourcePrefix(perm);
                    if (!grouped[prefix]) grouped[prefix] = [];
                    grouped[prefix].push(perm);
                  });

                  return Object.entries(grouped).map(([prefix, perms]) => (
                    <Box key={prefix} sx={{ mb: 1 }}>
                      {Object.keys(grouped).length > 1 && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ ml: 4, display: "block" }}
                        >
                          {prefix}
                        </Typography>
                      )}
                      <Box display="flex" flexWrap="wrap" gap={0}>
                        {perms.map((perm) => (
                          <FormControlLabel
                            key={perm}
                            control={
                              <Checkbox
                                checked={!!permissions[perm]}
                                onChange={() => handleToggle(perm)}
                                disabled={disabled}
                                size="small"
                              />
                            }
                            label={<Typography variant="body2">{getActionLabel(perm)}</Typography>}
                            sx={{ minWidth: 120 }}
                          />
                        ))}
                      </Box>
                    </Box>
                  ));
                })()}
              </FormGroup>
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Box>
  );
};

export default ApiKeyPermissionsEditor;
