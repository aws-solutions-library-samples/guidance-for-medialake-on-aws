/**
 * Collection Type Widget Configuration Panel
 * Allows users to select which collection type to display
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
  Chip,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useGetCollectionTypes } from "@/api/hooks/useCollections";
import { useDashboardStore } from "../../store/dashboardStore";
import type { CollectionTypeWidgetConfig, SortBy, SortOrder } from "../../types";

interface CollectionTypeWidgetConfigPanelProps {
  open: boolean;
  onClose: () => void;
  widgetId: string;
  config?: CollectionTypeWidgetConfig;
}

export const CollectionTypeWidgetConfigPanel: React.FC<
  CollectionTypeWidgetConfigPanelProps
> = ({ open, onClose, widgetId, config }) => {
  const updateWidgetConfig = useDashboardStore((state) => state.updateWidgetConfig);
  const updateWidgetCustomName = useDashboardStore((state) => state.updateWidgetCustomName);

  const [collectionTypeId, setCollectionTypeId] = useState<string>(config?.collectionTypeId || "");
  const [sortBy, setSortBy] = useState<SortBy>(config?.sorting?.sortBy || "name");
  const [sortOrder, setSortOrder] = useState<SortOrder>(config?.sorting?.sortOrder || "asc");
  const [customName, setCustomName] = useState<string>("");

  // Use the hook to get collection types
  const { data: typesData, isLoading, error } = useGetCollectionTypes();

  const types = typesData?.data || [];

  const handleSave = () => {
    const newConfig: CollectionTypeWidgetConfig = {
      collectionTypeId,
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
    setCollectionTypeId(config?.collectionTypeId || "");
    setSortBy(config?.sorting?.sortBy || "name");
    setSortOrder(config?.sorting?.sortOrder || "asc");
    setCustomName("");
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleCancel} maxWidth="sm" fullWidth>
      <DialogTitle>Configure Collection Type Widget</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3, mt: 2 }}>
          {/* Custom Widget Name */}
          <FormControl fullWidth>
            <FormLabel>Widget Name (Optional)</FormLabel>
            <TextField
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Leave empty to use type name"
              size="small"
              helperText="Custom name for this widget instance"
            />
          </FormControl>

          {/* Collection Type Selection */}
          <FormControl fullWidth required>
            <FormLabel>Collection Type</FormLabel>
            {isLoading ? (
              <Box display="flex" justifyContent="center" py={2}>
                <CircularProgress size={24} />
              </Box>
            ) : error ? (
              <Alert severity="error">Failed to load collection types</Alert>
            ) : types.length === 0 ? (
              <Alert severity="info">
                No collection types available. Create a type first.
              </Alert>
            ) : (
              <Select
                value={collectionTypeId}
                onChange={(e) => setCollectionTypeId(e.target.value)}
                size="small"
                displayEmpty
              >
                <MenuItem value="" disabled>
                  <em>Select a collection type</em>
                </MenuItem>
                {types.map((type) => (
                  <MenuItem key={type.id} value={type.id}>
                    <Box display="flex" alignItems="center" gap={1} width="100%">
                      {type.color && (
                        <Box
                          sx={{
                            width: 12,
                            height: 12,
                            borderRadius: "50%",
                            backgroundColor: type.color,
                            border: "1px solid",
                            borderColor: "divider",
                            flexShrink: 0,
                          }}
                        />
                      )}
                      <Box flex={1}>
                        <Typography variant="body2">{type.name}</Typography>
                        {type.description && (
                          <Typography variant="caption" color="text.secondary">
                            {type.description}
                          </Typography>
                        )}
                      </Box>
                      {type.isSystem && (
                        <Chip label="System" size="small" variant="outlined" />
                      )}
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
          disabled={!collectionTypeId || isLoading}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};
