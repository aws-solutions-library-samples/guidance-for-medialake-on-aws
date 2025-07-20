import React, { useState, useEffect, useRef } from "react";
import { useFeatureFlag } from "@/utils/featureFlags";
import {
  Box,
  Typography,
  IconButton,
  Button,
  CircularProgress,
  Checkbox,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderIcon from "@mui/icons-material/FavoriteBorder";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import { PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import { AssetAudio } from "../asset";
import { InlineTextEditor } from "../common/InlineTextEditor";

export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

export interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType?: string;
  fields: AssetField[];
  isRenaming?: boolean;
  renderField: (fieldId: string) => string | React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (event: React.MouseEvent<HTMLElement>) => void;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  placeholderImage?: string;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  isEditing?: boolean;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean, value?: string) => void;
  cardSize?: "small" | "medium" | "large";
  aspectRatio?: "vertical" | "square" | "horizontal";
  thumbnailScale?: "fit" | "fill";
  showMetadata?: boolean;
  menuOpen?: boolean; // Add prop to track menu state from parent
  isFavorite?: boolean; // Whether the asset is favorited
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void; // Callback when favorite is toggled
  isSelected?: boolean; // Whether the asset is selected for bulk operations
  onSelectToggle?: (id: string, event: React.MouseEvent<HTMLElement>) => void; // Callback when selection is toggled
  selectedSearchFields?: string[]; // Selected search fields
}

const AssetCard: React.FC<AssetCardProps> = ({
  id,
  name,
  thumbnailUrl,
  proxyUrl,
  assetType,
  fields,
  renderField,
  onAssetClick,
  onDeleteClick,
  onDownloadClick,
  onEditClick,
  placeholderImage = PLACEHOLDER_IMAGE,
  onImageError,
  isRenaming = false,
  isEditing,
  editedName,
  onEditNameChange,
  onEditNameComplete,
  cardSize = "medium",
  aspectRatio = "square",
  thumbnailScale = "fill",
  showMetadata = true,
  menuOpen = false, // Default to false
  isFavorite = false,
  onFavoriteToggle,
  isSelected = false,
  onSelectToggle,
  selectedSearchFields,
}) => {
  const [isHovering, setIsHovering] = useState(false);
  const [isMenuClicked, setIsMenuClicked] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const preventCommitRef = useRef<boolean>(false);
  const commitRef = useRef<(() => void) | null>(null);

  // Check if features are enabled
  const multiSelectFeature = useFeatureFlag(
    "search-multi-select-enabled",
    true,
  );
  const favoritesFeature = useFeatureFlag("user-favorites-enabled", true);

  // Update when menuOpen prop changes
  useEffect(() => {
    if (menuOpen) {
      setIsMenuClicked(true);
    }
  }, [menuOpen]);

  // Determine the card dimensions based on props
  const getCardDimensions = () => {
    const baseHeight =
      aspectRatio === "vertical"
        ? 300
        : aspectRatio === "square"
          ? 200
          : aspectRatio === "horizontal"
            ? 150
            : 200;

    const sizeMultiplier =
      cardSize === "small" ? 0.8 : cardSize === "large" ? 1.2 : 1;

    return {
      height: baseHeight * sizeMultiplier,
      width: "100%",
    };
  };
  const dimensions = getCardDimensions();

  // Fallback image error
  const defaultImageErrorHandler = (
    event: React.SyntheticEvent<HTMLImageElement, Event>,
  ) => {
    event.currentTarget.src = placeholderImage;
  };

  const handleDeleteClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    onDeleteClick(event);
  };

  const handleDownloadClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    // Directly trigger download functionality
    onDownloadClick(event);
  };

  // Handle clicks outside to detect when menu should be considered closed
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // If we click outside the card and the menu is open, consider it closed
      if (cardRef.current && !cardRef.current.contains(event.target as Node)) {
        // This is a click outside the card
        // We'll keep the menu clicked state for a short time to allow the menu to close gracefully
        setTimeout(() => {
          setIsMenuClicked(false);
        }, 300);
      }
    };

    // Add event listener for clicks
    document.addEventListener("mousedown", handleClickOutside);

    // Cleanup
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Determine if buttons should be visible
  const shouldShowButtons = isHovering || isMenuClicked;

  // Create a mapping between API field IDs and card field IDs based on the new API response structure
  const fieldMapping: Record<string, string> = {
    // Root level fields (new API structure)
    id: "id",
    assetType: "type",
    format: "format",
    createdAt: "createdAt",
    objectName: "name",
    fileSize: "size",
    fullPath: "fullPath",
    bucket: "bucket",
    FileHash: "hash",

    // Legacy nested fields (for backward compatibility)
    "DigitalSourceAsset.Type": "type",
    "DigitalSourceAsset.MainRepresentation.Format": "format",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate":
      "createdAt",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate":
      "createdAt",
    "DigitalSourceAsset.CreateDate": "createdAt",
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

  // Create a reverse mapping for easier lookup
  // Since multiple API fields can map to the same card field, we need to store arrays
  const reverseFieldMapping: Record<string, string[]> = {};
  Object.entries(fieldMapping).forEach(([apiId, cardId]) => {
    if (!reverseFieldMapping[cardId]) {
      reverseFieldMapping[cardId] = [];
    }
    reverseFieldMapping[cardId].push(apiId);
  });

  // Filter fields based on visibility and selected search fields
  const visibleFields = fields.filter((field) => {
    // First check if the field is marked as visible in cardFields
    if (!field.visible) return false;

    // If no selectedSearchFields are provided, show all visible fields
    if (!selectedSearchFields || selectedSearchFields.length === 0) return true;

    // Special case for name field - check if any selected field contains 'Name' or matches 'objectName'
    if (field.id === "name") {
      return selectedSearchFields.some(
        (field) => field.includes("Name") || field === "objectName",
      );
    }

    // Special case for date field - check if any selected field contains 'CreateDate' or matches 'createdAt'
    if (field.id === "createdAt") {
      return selectedSearchFields.some(
        (field) => field.includes("CreateDate") || field === "createdAt",
      );
    }

    // Special case for file size field - check if any selected field contains 'FileSize', 'Size', or matches 'fileSize'
    if (field.id === "size") {
      return selectedSearchFields.some(
        (field) =>
          field.includes("FileSize") ||
          field.includes("Size") ||
          field === "fileSize",
      );
    }

    // Special case for fullPath field - check if any selected field contains 'FullPath' or 'Path'
    if (field.id === "fullPath") {
      return selectedSearchFields.some(
        (field) =>
          field.includes("FullPath") ||
          field.includes("Path") ||
          field === "fullPath",
      );
    }

    // For other fields, check if any of their mapped API field IDs are in the selectedSearchFields
    const apiFieldIds = reverseFieldMapping[field.id] || [];
    return apiFieldIds.some((apiFieldId) =>
      selectedSearchFields.includes(apiFieldId),
    );
  });

  return (
    <Box
      ref={cardRef}
      sx={{
        position: "relative",
        transition: "all 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-4px)",
        },
      }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <Box
        sx={{
          borderRadius: 4, // Increased from 2 to 4 for more curved corners
          overflow: "hidden",
          bgcolor: "background.paper",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          position: "relative", // Ensure this is a positioning context
          "&:hover": {
            boxShadow: "0 8px 16px rgba(0,0,0,0.1)",
          },
        }}
      >
        {/* Render appropriate content based on asset type */}
        {assetType === "Video" ? (
          <video
            onClick={(event) => {
              event.preventDefault();
              onAssetClick();
            }}
            style={{
              width: dimensions.width,
              height: dimensions.height,
              backgroundColor: "rgba(0,0,0,0.03)",
              objectFit: "cover",
            }}
            controls
            src={proxyUrl}
          />
        ) : assetType === "Audio" ? (
          <Box
            onClick={onAssetClick}
            sx={{
              cursor: "pointer",
              width: dimensions.width,
              height: dimensions.height,
              backgroundColor: "rgba(0,0,0,0.03)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
            }}
          >
            <AssetAudio src={proxyUrl || ""} alt={name} compact={true} />
          </Box>
        ) : (
          <Box
            onClick={onAssetClick}
            component="img"
            src={thumbnailUrl || placeholderImage}
            alt={name}
            onError={onImageError || defaultImageErrorHandler}
            data-image-id={id}
            sx={{
              cursor: "pointer",
              width: dimensions.width,
              height: dimensions.height,
              backgroundColor: "rgba(0,0,0,0.03)",
              objectFit: thumbnailScale === "fit" ? "contain" : "cover",
              transition: "all 0.2s ease-in-out",
            }}
          />
        )}

        {/* Position checkbox and favorite buttons at the top left of the card */}
        <Box
          sx={{
            position: "absolute",
            top: 8,
            left: 8,
            display: "flex",
            gap: 1,
            zIndex: 1000, // Keep high z-index to ensure it's above other elements
            opacity: shouldShowButtons || isSelected || isFavorite ? 1 : 0, // Visible when hovering, selected, or favorited
            transition: "opacity 0.2s ease-in-out",
            pointerEvents:
              shouldShowButtons || isSelected || isFavorite ? "auto" : "none", // Ensure buttons are clickable when visible
            "&:hover": {
              opacity: shouldShowButtons || isSelected || isFavorite ? 1 : 0,
            },
          }}
          onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
        >
          {/* Checkbox for bulk selection - only show if feature flag is enabled */}
          {multiSelectFeature.value && (
            <Box
              sx={(theme) => ({
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                // if selected and not hovered, make it transparent; otherwise show the light circle
                bgcolor: isSelected
                  ? "transparent"
                  : alpha(theme.palette.background.paper, 0.7),
                borderRadius: "50%",
                width: 28,
                height: 28,
                transition: "all 0.2s ease-in-out",
                "&:hover": {
                  // on hover always show the background
                  bgcolor: alpha(theme.palette.background.default, 0.9),
                },
              })}
              onClick={(e) => {
                e.stopPropagation();
                onSelectToggle?.(id, e);
              }}
            >
              <Checkbox
                size="small"
                disableRipple
                checked={isSelected}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectToggle?.(id, e);
                }}
                icon={<CheckBoxOutlineBlankIcon />}
                checkedIcon={<CheckBoxIcon />}
                sx={{
                  padding: 0,
                  "& .MuiSvgIcon-root": {
                    fontSize: 18,
                  },
                }}
              />
            </Box>
          )}

          {/* Favorite button - only show if feature flag is enabled */}
          {favoritesFeature.value && (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                if (onFavoriteToggle) {
                  onFavoriteToggle(e);
                }
              }}
              sx={{
                padding: "4px",
              }}
            >
              {isFavorite ? (
                <FavoriteIcon fontSize="small" color="error" />
              ) : (
                <FavoriteBorderIcon fontSize="small" />
              )}
            </IconButton>
          )}
        </Box>

        {/* Position buttons at the top right of the card, visible on hover or when menu is open */}
        <Box
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            display: "flex",
            gap: 1,
            zIndex: 10, // Increased z-index to ensure buttons are above other elements
            opacity: shouldShowButtons ? 1 : 0, // Visible when hovering or menu is clicked
            transition: "opacity 0.2s ease-in-out",
            pointerEvents: shouldShowButtons ? "auto" : "none", // Ensure buttons are clickable when visible
          }}
          onClick={(e) => e.stopPropagation()} // Stop propagation at the container level
        >
          <IconButton
            size="small"
            onClick={handleDeleteClick}
            sx={(theme) => ({
              bgcolor: alpha(theme.palette.background.paper, 0.7),
              padding: "4px",
              "&:hover": {
                bgcolor: alpha(theme.palette.background.default, 0.9),
              },
            })}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleDownloadClick}
            sx={(theme) => ({
              bgcolor: alpha(theme.palette.background.paper, 0.7),
              padding: "4px",
              "&:hover": {
                bgcolor: alpha(theme.palette.background.default, 0.9),
              },
            })}
          >
            <DownloadIcon fontSize="small" />
          </IconButton>
        </Box>

        {/* Metadata section */}
        {showMetadata && (
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              {visibleFields.map((field) => (
                <Box
                  key={field.id}
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "100px 1fr",
                    alignItems: "center",
                    width: "100%",
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      flexShrink: 0,
                      paddingRight: 1,
                    }}
                  >
                    {field.label}:
                  </Typography>
                  {field.id === "name" && onEditClick ? (
                    isEditing ? (
                      <Box
                        sx={{
                          gridColumn: "1 / span 2",
                          display: "flex",
                          flexDirection: "column",
                          gap: 1,
                          width: "100%",
                          mt: 1,
                        }}
                      >
                        <InlineTextEditor
                          initialValue={editedName || ""}
                          editingCellId={id} // ← pass a stable ID (e.g. asset ID)
                          preventCommitRef={preventCommitRef} // ← pass the ref to prevent commit
                          commitRef={commitRef} // ← pass the ref to expose commit function
                          onChangeCommit={(value) => {
                            // Update parent state
                            onEditNameChange({
                              target: { value },
                            } as React.ChangeEvent<HTMLInputElement>);
                          }}
                          onComplete={(save, value) => {
                            console.log(
                              "🎯 AssetCard onComplete - save:",
                              save,
                              "value:",
                              value,
                            );
                            console.log(
                              "🎯 Calling onEditNameComplete with save:",
                              save,
                              "value:",
                              value,
                            );
                            onEditNameComplete?.(save, value);
                          }}
                          isEditing={true}
                          disabled={isRenaming}
                          autoFocus
                          size="small"
                          fullWidth
                          multiline
                          rows={2}
                          sx={{
                            width: "100%",
                            "& .MuiInputBase-root": {
                              width: "100%",
                            },
                            "& .MuiInputBase-input": {
                              whiteSpace: "normal",
                              wordBreak: "break-word",
                            },
                          }}
                          InputProps={{
                            endAdornment: isRenaming && (
                              <CircularProgress size={16} />
                            ),
                          }}
                        />
                        <Box
                          sx={{
                            display: "flex",
                            justifyContent: "flex-end",
                            gap: 1,
                          }}
                        >
                          <Button
                            size="small"
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              console.log("💾 AssetCard Save mousedown");
                              // Set flag to prevent blur from canceling
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              console.log("💾 AssetCard Save clicked");
                              console.log(
                                "💾 AssetCard commitRef.current:",
                                commitRef.current,
                              );
                              // Reset the prevent flag
                              preventCommitRef.current = false;
                              // Call the commit function directly via ref
                              if (commitRef.current) {
                                console.log(
                                  "💾 AssetCard calling commitRef.current()",
                                );
                                commitRef.current();
                              } else {
                                console.error(
                                  "💾 AssetCard commitRef.current is null!",
                                );
                              }
                            }}
                            variant="contained"
                            disabled={isRenaming}
                          >
                            Save
                          </Button>
                          <Button
                            size="small"
                            disabled={isRenaming}
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              console.log("🚫 AssetCard Cancel clicked");
                              // Set flag to prevent InlineTextEditor commit from being called
                              // Use onMouseDown instead of onClick to set the flag before onBlur
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditNameComplete?.(false, undefined);
                            }}
                          >
                            Cancel
                          </Button>
                        </Box>
                      </Box>
                    ) : (
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          width: "100%",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography
                          sx={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "normal",
                            wordBreak: "break-word",
                            flexGrow: 1,
                            userSelect: "text", // Allow text selection
                            maxHeight: "2.4em", // Limit to exactly 2 lines
                            lineHeight: "1.2em",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            position: "relative",
                            "&:after": {
                              content: '"..."',
                              position: "absolute",
                              bottom: 0,
                              right: 0,
                              paddingLeft: "4px",
                              backgroundColor: "inherit",
                              boxShadow: "-8px 0 8px rgba(255,255,255,0.8)",
                              display: "none",
                            },
                            "&.truncated:after": {
                              display: "inline",
                            },
                            "&:hover": {
                              maxHeight: "none", // Remove height limit on hover
                              WebkitLineClamp: "unset",
                              "&:after": {
                                display: "none",
                              },
                            },
                          }}
                          className={
                            String(renderField(field.id)).length > 60
                              ? "truncated"
                              : ""
                          }
                          display="inline"
                          variant="body2"
                          title={String(renderField(field.id))}
                        >
                          {renderField(field.id)}
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditClick(e);
                          }}
                          disabled={isRenaming}
                        >
                          {isRenaming ? (
                            <CircularProgress size={16} />
                          ) : (
                            <EditIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Box>
                    )
                  ) : (
                    <Box sx={{ width: "100%" }}>
                      <Typography
                        variant="body2"
                        sx={{
                          userSelect: "text",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                          width: "100%",
                          maxHeight: "2.4em", // Limit to exactly 2 lines
                          lineHeight: "1.2em",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          position: "relative",
                          "&:after": {
                            content: '"..."',
                            position: "absolute",
                            bottom: 0,
                            right: 0,
                            paddingLeft: "4px",
                            backgroundColor: "inherit",
                            boxShadow: "-8px 0 8px rgba(255,255,255,0.8)",
                            display: "none",
                          },
                          "&.truncated:after": {
                            display: "inline",
                          },
                          "&:hover": {
                            maxHeight: "none", // Remove height limit on hover
                            WebkitLineClamp: "unset",
                            "&:after": {
                              display: "none",
                            },
                          },
                        }}
                        className={
                          String(renderField(field.id)).length > 60
                            ? "truncated"
                            : ""
                        }
                        title={String(renderField(field.id))}
                      >
                        {renderField(field.id)}
                      </Typography>
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AssetCard;
