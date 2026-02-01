/**
 * Collection Group Widget Configuration Panel
 * Allows users to select which collection group to display
 */

import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  FormLabel,
  Select,
  MenuItem,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Alert,
  RadioGroup,
  FormControlLabel,
  Radio,
} from "@mui/material";
import { useCollectionGroups } from "@/features/collection-groups/hooks/useCollectionGroups";
import { useDashboardStore } from "../../store/dashboardStore";
import type { CollectionGroupWidgetConfig, SortBy, SortOrder } from "../../types";

interface CollectionGroupWidgetConfigPanelProps {
  open: boolean;
  onClose: () => void;
  widgetId: string;
  config?: CollectionGroupWidgetConfig;
}

export const CollectionGroupWidgetConfigPanel: React.FC<
  CollectionGroupWidgetConfigPanelProps
> = ({ open, onClose, widgetId, config }) => {
  const updateWidgetConfig = useDashboardStore((state) => state.updateWidgetConfig);
  const updateWidgetCustomName = useDashboardStore((state) => state.updateWidgetCustomName);

  const [groupId, setGroupId] = useState<string>(config?.groupId || "");
  const [sortBy, setSortBy] = useState<SortBy>(config?.sorting?.sortBy || "name");
  const [sortOrder, setSortOrder] = useState<SortOrder>(config?.sorting?.sortOrder || "asc");
  const [customName, setCustomName] = useState<string>("");

  const { data: groupsData, isLoading, error } = useCollectionGroups();

  const groups = groupsData?.data || [];

  const handleSave = () => {
    const newConfig: CollectionGroupWidgetConfig = {
      groupId,
      sorting: {
        sortBy,
        sortOrder,
      },
    };

    updateWidgetConfig(widgetId, newConfig);
    
    if (customName.trim()) {
      updateWidgetCustomName(widgetId, customName.trim());
    } else {
      updateWidgetCustomName(widgetId, undefined);
    }

    onClose();
  };

  const handleCancel = () => {
    // Reset to current config
    setGroupId(config?.groupId || "");
    setSortBy(config?.sorting?.sortBy || "name");
    setSortOrder(config?.sorting?.sortOrder || "asc");
    setCustomName("");
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleCancel} maxWidth="sm" fullWidth>
      <DialogTitle>Configure Collection Group Widget</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3, mt: 2 }}>
          {/* Custom Widget Name */}
          <FormControl fullWidth>
            <FormLabel>Widget Name (Optional)</FormLabel>
            <TextField
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Leave empty to use group name"
              size="small"
              helperText="Custom name for this widget instance"
            />
          </FormControl>

          {/* Collection Group Selection */}
          <FormControl fullWidth required>
            <FormLabel>Collection Group</FormLabel>
            {isLoading ? (
              <Box display="flex" justifyContent="center" py={2}>
                <CircularProgress size={24} />
              </Box>
            ) : error ? (
              <Alert severity="error">Failed to load collection groups</Alert>
            ) : groups.length === 0 ? (
              <Alert severity="info">
                No collection groups available. Create a group first.
              </Alert>
            ) : (
              <Select
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                size="small"
                displayEmpty
              >
                <MenuItem value="" disabled>
                  <em>Select a collection group</em>
                </MenuItem>
                {groups.map((group) => (
                  <MenuItem key={group.id} value={group.id}>
                    <Box>
                      <Typography variant="body2">{group.name}</Typography>
                      {group.description && (
                        <Typography variant="caption" color="text.secondary">
                          {group.description}
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.secondary" display="block">
                        {group.collectionCount} collection{group.collectionCount !== 1 ? "s" : ""}
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            )}
          </FormControl>

          {/* Sort By */}
          <FormControl fullWidth>
            <FormLabel>Sort By</FormLabel>
            <RadioGroup
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              row
            >
              <FormControlLabel value="name" control={<Radio />} label="Name" />
              <FormControlLabel value="createdAt" control={<Radio />} label="Created" />
              <FormControlLabel value="updatedAt" control={<Radio />} label="Updated" />
            </RadioGroup>
          </FormControl>

          {/* Sort Order */}
          <FormControl fullWidth>
            <FormLabel>Sort Order</FormLabel>
            <RadioGroup
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              row
            >
              <FormControlLabel value="asc" control={<Radio />} label="Ascending" />
              <FormControlLabel value="desc" control={<Radio />} label="Descending" />
            </RadioGroup>
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancel}>Cancel</Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={!groupId || isLoading}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};
