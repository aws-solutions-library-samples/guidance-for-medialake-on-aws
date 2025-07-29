import React from "react";
import {
  Box,
  Typography,
  Button,
  ToggleButtonGroup,
  ToggleButton,
  Menu,
  MenuItem,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Switch,
  Radio,
  ListItemIcon,
  ListItemText,
} from "@mui/material";

import ViewModuleIcon from "@mui/icons-material/ViewModule";
import ViewListIcon from "@mui/icons-material/ViewList";
import ViewColumnIcon from "@mui/icons-material/ViewColumn";
import SortIcon from "@mui/icons-material/Sort";
import TuneIcon from "@mui/icons-material/Tune";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import CropPortraitIcon from "@mui/icons-material/CropPortrait";
import CropSquareIcon from "@mui/icons-material/CropSquare";
import CropLandscapeIcon from "@mui/icons-material/CropLandscape";
import PhotoSizeSelectSmallIcon from "@mui/icons-material/PhotoSizeSelectSmall";
import PhotoSizeSelectLargeIcon from "@mui/icons-material/PhotoSizeSelectLarge";
import FitScreenIcon from "@mui/icons-material/FitScreen";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import InfoIcon from "@mui/icons-material/Info";
import { type SortingState } from "@tanstack/react-table";
import {
  type AssetField,
  type SortOption,
  type CardSize,
  type AspectRatio,
  type AssetViewControlsProps as BaseAssetViewControlsProps,
} from "../../types/shared/assetComponents";
import { useFeatureFlag } from "@/utils/featureFlags";

interface AssetViewControlsProps extends BaseAssetViewControlsProps {
  // Search fields
  selectedFields?: string[];
  availableFields?: Array<{
    name: string;
    displayName: string;
    description: string;
    type: string;
    isDefault: boolean;
  }>;
  onFieldsChange?: (event: any) => void;

  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  cardSize: CardSize;
  onCardSizeChange: (size: CardSize) => void;
  aspectRatio: AspectRatio;
  onAspectRatioChange: (ratio: AspectRatio) => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  // Selection props
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;
}

const AssetViewControls: React.FC<AssetViewControlsProps> = ({
  viewMode,
  onViewModeChange,
  title,
  sorting,
  sortOptions,
  onSortChange,
  fields,
  onFieldToggle,
  // Search fields
  selectedFields,
  availableFields,
  onFieldsChange,
  groupByType,
  onGroupByTypeChange,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange,
  // Selection props
  hasSelectedAssets = false,
  selectAllState = "none",
  onSelectAllToggle,
}) => {
  const [sortAnchor, setSortAnchor] = React.useState<null | HTMLElement>(null);
  const [fieldsAnchor, setFieldsAnchor] = React.useState<null | HTMLElement>(
    null,
  );
  const [appearanceAnchor, setAppearanceAnchor] =
    React.useState<null | HTMLElement>(null);

  const handleSortClose = () => setSortAnchor(null);
  const handleFieldsClose = () => setFieldsAnchor(null);
  const handleAppearanceClose = () => setAppearanceAnchor(null);

  // Check if multi-select feature is enabled
  const multiSelectFeature = useFeatureFlag(
    "search-multi-select-enabled",
    false,
  );

  // Create a mapping between API field IDs and column IDs
  const fieldMapping: Record<string, string> = {
    // Root level fields (new API structure)
    id: "id",
    assetType: "type",
    format: "format",
    createdAt: "date",
    objectName: "name",
    fileSize: "size",
    fullPath: "fullPath",
    bucket: "bucket",
    FileHash: "hash",

    // Legacy nested fields (for backward compatibility)
    "DigitalSourceAsset.Type": "type",
    "DigitalSourceAsset.MainRepresentation.Format": "format",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate":
      "date",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate":
      "date",
    "DigitalSourceAsset.CreateDate": "date",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name":
      "name",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size":
      "size",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize":
      "size",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath":
      "fullPath",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket":
      "bucket",
    "Metadata.Consolidated": "metadata",
    InventoryID: "id",
  };

  // Create a reverse mapping for easier lookup
  const reverseFieldMapping: Record<string, string[]> = {};
  Object.entries(fieldMapping).forEach(([apiId, colId]) => {
    if (!reverseFieldMapping[colId]) {
      reverseFieldMapping[colId] = [];
    }
    reverseFieldMapping[colId].push(apiId);
  });

  // Filter sort options based on selected fields
  const filteredSortOptions = React.useMemo(() => {
    if (!selectedFields || selectedFields.length === 0) {
      return sortOptions;
    }

    return sortOptions.filter((option) => {
      // Special case for name field
      if (option.id === "name") {
        return selectedFields.some(
          (field) => field.includes("Name") || field === "objectName",
        );
      }

      // Special case for date field
      if (option.id === "date") {
        return selectedFields.some(
          (field) => field.includes("CreateDate") || field === "createdAt",
        );
      }

      // Special case for size field
      if (option.id === "size") {
        return selectedFields.some(
          (field) =>
            field.includes("FileSize") ||
            field.includes("Size") ||
            field === "fileSize",
        );
      }

      // For other fields, check if any of their mapped API field IDs are in the selectedSearchFields
      const apiFieldIds = reverseFieldMapping[option.id] || [];
      return apiFieldIds.some((apiFieldId) =>
        selectedFields.includes(apiFieldId),
      );
    });
  }, [sortOptions, selectedFields, reverseFieldMapping]);

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        mb: 3,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={onViewModeChange}
          size="small"
        >
          <ToggleButton value="card">
            <ViewModuleIcon />
          </ToggleButton>
          <ToggleButton value="table">
            <ViewListIcon />
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
        {multiSelectFeature.value && (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
            }}
          >
            <FormControlLabel
              control={
                <Checkbox
                  checked={selectAllState === "all"}
                  indeterminate={selectAllState === "some"}
                  onChange={onSelectAllToggle}
                  size="small"
                  sx={{
                    color: "primary.main",
                    "&.Mui-checked": {
                      color: "primary.main",
                    },
                    "&.MuiCheckbox-indeterminate": {
                      color: "primary.main",
                    },
                    "& .MuiSvgIcon-root": {
                      fontSize: "1.2rem",
                    },
                  }}
                />
              }
              label={selectAllState === "all" ? "Deselect Page" : "Select Page"}
              sx={{
                margin: 0,
                "& .MuiFormControlLabel-label": {
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  color: "primary.main",
                },
              }}
            />
          </Box>
        )}
        {/* Sort Button */}
        <Button
          size="small"
          startIcon={<SortIcon />}
          endIcon={<KeyboardArrowDownIcon />}
          onClick={(e) => setSortAnchor(e.currentTarget)}
          sx={{
            bgcolor: sortAnchor ? "action.selected" : "transparent",
            textTransform: "none",
          }}
        >
          Sort
        </Button>

        {/* Show Fields Button */}
        <Button
          size="small"
          startIcon={<ViewColumnIcon />}
          endIcon={<KeyboardArrowDownIcon />}
          onClick={(e) => setFieldsAnchor(e.currentTarget)}
          sx={{
            bgcolor: fieldsAnchor ? "action.selected" : "transparent",
            textTransform: "none",
          }}
        >
          Fields
        </Button>

        {/* Appearance Button */}
        <Button
          size="small"
          startIcon={<TuneIcon />}
          endIcon={<KeyboardArrowDownIcon />}
          onClick={(e) => setAppearanceAnchor(e.currentTarget)}
          sx={{
            bgcolor: appearanceAnchor ? "action.selected" : "transparent",
            textTransform: "none",
          }}
        >
          Appearance
        </Button>
      </Box>

      {/* Sort Menu */}
      <Menu
        open={Boolean(sortAnchor)}
        anchorEl={sortAnchor}
        onClose={handleSortClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <Box sx={{ p: 2, minWidth: 200 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Sort By
          </Typography>
          {filteredSortOptions.map((option) => (
            <MenuItem
              key={option.id}
              onClick={() => {
                onSortChange(option.id);
                handleSortClose();
              }}
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                py: 1,
              }}
            >
              <Typography variant="body2">{option.label}</Typography>
              {sorting[0]?.id === option.id && (
                <Typography variant="caption" color="primary">
                  {sorting[0]?.desc ? "↓" : "↑"}
                </Typography>
              )}
            </MenuItem>
          ))}
        </Box>
      </Menu>

      {/* Show Fields Menu */}
      <Menu
        open={Boolean(fieldsAnchor)}
        anchorEl={fieldsAnchor}
        onClose={handleFieldsClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <Box sx={{ p: 2, minWidth: 200 }}>
          {/* Display fields for search if available */}
          {availableFields && selectedFields && onFieldsChange ? (
            <>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Search Fields
              </Typography>
              <FormGroup>
                {availableFields.map((field) => (
                  <FormControlLabel
                    key={field.name}
                    control={
                      <Checkbox
                        checked={selectedFields.includes(field.name)}
                        onChange={(e) => {
                          const newSelectedFields = e.target.checked
                            ? [...selectedFields, field.name]
                            : selectedFields.filter(
                                (name) => name !== field.name,
                              );

                          onFieldsChange({
                            target: { value: newSelectedFields },
                          });
                        }}
                        size="small"
                      />
                    }
                    label={field.displayName}
                    sx={{
                      "& .MuiFormControlLabel-label": {
                        fontSize: "0.875rem",
                      },
                    }}
                  />
                ))}
              </FormGroup>
            </>
          ) : (
            <>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {viewMode === "card" ? "Show Fields" : "Show Columns"}
              </Typography>
              <FormGroup>
                {fields.map((field) => (
                  <FormControlLabel
                    key={field.id}
                    control={
                      <Checkbox
                        checked={field.visible}
                        onChange={() => onFieldToggle(field.id)}
                        size="small"
                      />
                    }
                    label={field.label}
                    sx={{
                      "& .MuiFormControlLabel-label": {
                        fontSize: "0.875rem",
                      },
                    }}
                  />
                ))}
              </FormGroup>
            </>
          )}
        </Box>
      </Menu>

      {/* Appearance Menu */}
      <Menu
        open={Boolean(appearanceAnchor)}
        anchorEl={appearanceAnchor}
        onClose={handleAppearanceClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <Box sx={{ p: 2, minWidth: 300 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Appearance
          </Typography>

          {viewMode === "card" && (
            <>
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Card Size
                </Typography>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <ToggleButton
                    value="small"
                    selected={cardSize === "small"}
                    onChange={() => onCardSizeChange("small")}
                    size="small"
                  >
                    <PhotoSizeSelectSmallIcon />
                  </ToggleButton>
                  <ToggleButton
                    value="medium"
                    selected={cardSize === "medium"}
                    onChange={() => onCardSizeChange("medium")}
                    size="small"
                  >
                    <ViewModuleIcon />
                  </ToggleButton>
                  <ToggleButton
                    value="large"
                    selected={cardSize === "large"}
                    onChange={() => onCardSizeChange("large")}
                    size="small"
                  >
                    <PhotoSizeSelectLargeIcon />
                  </ToggleButton>
                </Box>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Aspect Ratio
                </Typography>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <ToggleButton
                    value="vertical"
                    selected={aspectRatio === "vertical"}
                    onChange={() => onAspectRatioChange("vertical")}
                    size="small"
                  >
                    <CropPortraitIcon />
                  </ToggleButton>
                  <ToggleButton
                    value="square"
                    selected={aspectRatio === "square"}
                    onChange={() => onAspectRatioChange("square")}
                    size="small"
                  >
                    <CropSquareIcon />
                  </ToggleButton>
                  <ToggleButton
                    value="horizontal"
                    selected={aspectRatio === "horizontal"}
                    onChange={() => onAspectRatioChange("horizontal")}
                    size="small"
                  >
                    <CropLandscapeIcon />
                  </ToggleButton>
                </Box>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Thumbnail Scale
                </Typography>
                <Box sx={{ display: "flex", gap: 1 }}>
                  <ToggleButton
                    value="fit"
                    selected={thumbnailScale === "fit"}
                    onChange={() => onThumbnailScaleChange("fit")}
                    size="small"
                  >
                    <FitScreenIcon />
                  </ToggleButton>
                  <ToggleButton
                    value="fill"
                    selected={thumbnailScale === "fill"}
                    onChange={() => onThumbnailScaleChange("fill")}
                    size="small"
                  >
                    <FullscreenIcon />
                  </ToggleButton>
                </Box>
              </Box>
            </>
          )}

          <Box sx={{ display: "flex", gap: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={groupByType}
                  onChange={(e) => onGroupByTypeChange(e.target.checked)}
                  size="small"
                />
              }
              label="Group by Type"
              sx={{
                "& .MuiFormControlLabel-label": {
                  fontSize: "0.875rem",
                },
              }}
            />
            {viewMode === "card" && (
              <FormControlLabel
                control={
                  <Switch
                    checked={showMetadata}
                    onChange={(e) => onShowMetadataChange(e.target.checked)}
                    size="small"
                  />
                }
                label="Metadata"
                sx={{
                  "& .MuiFormControlLabel-label": {
                    fontSize: "0.875rem",
                  },
                }}
              />
            )}
          </Box>
        </Box>
      </Menu>
    </Box>
  );
};

export default AssetViewControls;
