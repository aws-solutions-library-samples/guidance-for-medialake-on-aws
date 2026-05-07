import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  TextField,
  FormControlLabel,
  Switch,
  Box,
  CircularProgress,
  Alert,
  Typography,
  IconButton,
  alpha,
  useTheme,
  Collapse,
  InputBase,
  Chip,
} from "@mui/material";
import {
  Close as CloseIcon,
  Save as SaveIcon,
  Edit as EditIcon,
  Folder as FolderIcon,
  ChevronRight as ChevronRightIcon,
  Search as SearchIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
} from "@mui/icons-material";
import {
  useUpdateCollection,
  useGetCollections,
  useSetCollectionThumbnail,
  useSetCollectionIcon,
  useDeleteCollectionThumbnail,
  type Collection,
} from "../../api/hooks/useCollections";
import { useCollectionCollectionTypes } from "../../api/hooks/useCollectionCollectionTypes";
import { ThumbnailSelector } from "./ThumbnailSelector";

interface EditCollectionModalProps {
  open: boolean;
  onClose: () => void;
  collection: Collection | null;
}

export const EditCollectionModal: React.FC<EditCollectionModalProps> = ({
  open,
  onClose,
  collection,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    parentId: "",
    isPublic: false,
    collectionTypeId: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showParentPicker, setShowParentPicker] = useState(false);
  const [parentSearch, setParentSearch] = useState("");

  // Local thumbnail state for deferred save — changes are stored locally
  // and only sent to the API when the user clicks Save
  const [pendingThumbnail, setPendingThumbnail] = useState<{
    type: "icon" | "upload" | "remove";
    value: string; // icon name or base64 data
  } | null>(null);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState<string | null>(null);

  // API hooks
  const updateCollectionMutation = useUpdateCollection();
  const setThumbnailMutation = useSetCollectionThumbnail();
  const setIconMutation = useSetCollectionIcon();
  const deleteThumbnailMutation = useDeleteCollectionThumbnail();
  const { data: collectionsResponse } = useGetCollections();
  const { data: collectionTypesResponse } = useCollectionCollectionTypes();

  const collections = collectionsResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  const isSaving =
    updateCollectionMutation.isPending ||
    setThumbnailMutation.isPending ||
    setIconMutation.isPending ||
    deleteThumbnailMutation.isPending;

  // Reset form when modal opens for a collection
  useEffect(() => {
    if (collection && open) {
      setFormData({
        name: collection.name || "",
        description: collection.description || "",
        parentId: collection.parentId || "",
        isPublic: collection.isPublic || false,
        collectionTypeId: collection.collectionTypeId || "",
      });
      setErrors({});
      setShowParentPicker(false);
      setParentSearch("");
      setPendingThumbnail(null);
      setUploadPreviewUrl(null);
    }
  }, [collection?.id, open]);

  // Build breadcrumb path for a collection
  const getCollectionPath = useCallback(
    (col: Collection): Collection[] => {
      const path: Collection[] = [];
      let current: Collection | undefined = col;
      while (current) {
        path.unshift(current);
        if (current.parentId) {
          current = collections.find((c) => c.id === current!.parentId);
        } else {
          break;
        }
      }
      return path;
    },
    [collections]
  );

  // Filter parent collections (exclude self and descendants)
  const availableParentCollections = useMemo(() => {
    if (!collection) return collections;
    // Exclude the collection itself
    return collections.filter((c) => c.id !== collection.id);
  }, [collections, collection]);

  const filteredParentCollections = useMemo(() => {
    if (!parentSearch.trim()) return availableParentCollections;
    const query = parentSearch.toLowerCase();
    return availableParentCollections.filter((c) => {
      const path = getCollectionPath(c);
      const fullPath = path.map((p) => p.name).join(" / ");
      return c.name.toLowerCase().includes(query) || fullPath.toLowerCase().includes(query);
    });
  }, [availableParentCollections, parentSearch, getCollectionPath]);

  const selectedParent = collections.find((c) => c.id === formData.parentId);

  const handleInputChange = (field: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  const handleSelectChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) {
      newErrors.name = t("collectionsPage.form.validation.nameRequired", "Name is required");
    } else if (formData.name.trim().length < 2) {
      newErrors.name = t(
        "collectionsPage.form.validation.nameMinLength",
        "Name must be at least 2 characters"
      );
    } else if (formData.name.trim().length > 100) {
      newErrors.name = t(
        "collectionsPage.form.validation.nameMaxLength",
        "Name must be less than 100 characters"
      );
    }
    if (formData.description && formData.description.length > 500) {
      newErrors.description = t(
        "collectionsPage.form.validation.descriptionMaxLength",
        "Description must be less than 500 characters"
      );
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Thumbnail handlers — store locally, apply on save
  const handleSelectIcon = (iconName: string) => {
    setPendingThumbnail({ type: "icon", value: iconName });
    setUploadPreviewUrl(null);
  };

  const handleUploadImage = (base64Data: string) => {
    setPendingThumbnail({ type: "upload", value: base64Data });
    setUploadPreviewUrl(`data:image/png;base64,${base64Data}`);
  };

  const handleRemoveThumbnail = () => {
    setPendingThumbnail({ type: "remove", value: "" });
    setUploadPreviewUrl(null);
  };

  // Resolve what the ThumbnailSelector should display
  const displayThumbnailType = pendingThumbnail
    ? pendingThumbnail.type === "remove"
      ? undefined
      : pendingThumbnail.type
    : collection?.thumbnailType;

  const displayThumbnailValue = pendingThumbnail
    ? pendingThumbnail.type === "icon"
      ? pendingThumbnail.value
      : undefined
    : collection?.thumbnailValue;

  const displayThumbnailUrl = pendingThumbnail
    ? pendingThumbnail.type === "upload"
      ? uploadPreviewUrl || undefined
      : undefined
    : collection?.thumbnailUrl || undefined;

  const handleSubmit = async () => {
    if (!collection || !validateForm()) return;
    try {
      // Save form data changes
      const updateData = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        parentId: formData.parentId || undefined,
        isPublic: formData.isPublic,
        collectionTypeId: formData.collectionTypeId || undefined,
      };

      if (hasFormChanges) {
        await updateCollectionMutation.mutateAsync({ id: collection.id, data: updateData });
      }

      // Apply pending thumbnail change
      if (pendingThumbnail) {
        if (pendingThumbnail.type === "icon") {
          await setIconMutation.mutateAsync({
            collectionId: collection.id,
            iconName: pendingThumbnail.value,
          });
        } else if (pendingThumbnail.type === "upload") {
          await setThumbnailMutation.mutateAsync({
            collectionId: collection.id,
            data: { source: "upload", data: pendingThumbnail.value },
          });
        } else if (pendingThumbnail.type === "remove") {
          await deleteThumbnailMutation.mutateAsync(collection.id);
        }
      }

      onClose();
    } catch {
      // Error surfaced via mutation state
    }
  };

  const handleClose = () => {
    if (!isSaving) {
      setErrors({});
      setShowParentPicker(false);
      setParentSearch("");
      setPendingThumbnail(null);
      setUploadPreviewUrl(null);
      onClose();
    }
  };

  // Detect if form has changes
  const hasFormChanges = collection
    ? formData.name !== (collection.name || "") ||
      formData.description !== (collection.description || "") ||
      formData.parentId !== (collection.parentId || "") ||
      formData.isPublic !== (collection.isPublic || false) ||
      formData.collectionTypeId !== (collection.collectionTypeId || "")
    : false;

  const hasChanges = hasFormChanges || pendingThumbnail !== null;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            borderRadius: 3,
            bgcolor: "background.paper",
            backgroundImage: "none",
            overflow: "hidden",
            maxHeight: "85vh",
          },
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          pt: 2.5,
          pb: 2,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.2 }}>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: 1.5,
                bgcolor: alpha(theme.palette.info.main, isDark ? 0.15 : 0.1),
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <EditIcon sx={{ fontSize: 16, color: "info.main" }} />
            </Box>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                fontSize: "1.1rem",
                letterSpacing: "-0.01em",
              }}
            >
              {t("collectionsPage.editCollection", "Edit Collection")}
            </Typography>
          </Box>
          {collection && (
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                mt: 0.3,
                ml: 5.5,
                fontSize: "0.78rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {collection.name}
            </Typography>
          )}
        </Box>
        <IconButton
          onClick={handleClose}
          disabled={isSaving}
          size="small"
          sx={{
            color: "text.secondary",
            mt: -0.5,
            mr: -0.5,
            "&:hover": { bgcolor: alpha(theme.palette.text.secondary, 0.08) },
          }}
          aria-label="Close dialog"
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <DialogContent sx={{ p: 0, display: "flex", flexDirection: "column" }}>
        <Box sx={{ px: 3, pt: 2.5, pb: 2, display: "flex", flexDirection: "column", gap: 2.5 }}>
          {/* Thumbnail */}
          <ThumbnailSelector
            currentThumbnailType={displayThumbnailType}
            currentThumbnailValue={displayThumbnailValue}
            currentThumbnailUrl={displayThumbnailUrl}
            onSelectIcon={handleSelectIcon}
            onUploadImage={handleUploadImage}
            onRemoveThumbnail={handleRemoveThumbnail}
            isLoading={false}
            disabled={isSaving}
          />

          {/* Name */}
          <TextField
            fullWidth
            label={t("collectionsPage.form.name", "Name")}
            placeholder={t("collectionsPage.form.namePlaceholder", "e.g. Brand Assets Q1")}
            value={formData.name}
            onChange={handleInputChange("name")}
            error={Boolean(errors.name)}
            helperText={errors.name}
            required
            disabled={isSaving}
            size="small"
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
          />

          {/* Description */}
          <TextField
            fullWidth
            label={t("collectionsPage.form.description", "Description")}
            placeholder={t(
              "collectionsPage.form.descriptionPlaceholder",
              "Describe this collection..."
            )}
            value={formData.description}
            onChange={handleInputChange("description")}
            error={Boolean(errors.description)}
            helperText={errors.description}
            multiline
            rows={2}
            disabled={isSaving}
            size="small"
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
          />

          {/* Parent Collection Picker */}
          <Box>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 600,
                fontSize: "0.75rem",
                color: "text.secondary",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                mb: 0.8,
                display: "block",
              }}
            >
              {t("collectionsPage.form.parentCollection", "Parent Collection")}
            </Typography>
            <Box
              onClick={() => !isSaving && setShowParentPicker(!showParentPicker)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                px: 1.5,
                py: 1,
                borderRadius: 1.5,
                border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                cursor: isSaving ? "default" : "pointer",
                transition: "all 0.15s",
                "&:hover": isSaving
                  ? {}
                  : {
                      borderColor: alpha(theme.palette.primary.main, 0.4),
                      bgcolor: alpha(theme.palette.primary.main, 0.02),
                    },
              }}
            >
              <FolderIcon sx={{ fontSize: 18, color: "text.secondary", flexShrink: 0 }} />
              {selectedParent ? (
                <Box sx={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 0.3 }}>
                  {getCollectionPath(selectedParent).map((ancestor, idx, arr) => (
                    <React.Fragment key={ancestor.id}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontSize: "0.82rem",
                          fontWeight: idx === arr.length - 1 ? 600 : 400,
                          color: idx === arr.length - 1 ? "text.primary" : "text.secondary",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ancestor.name}
                      </Typography>
                      {idx < arr.length - 1 && (
                        <ChevronRightIcon
                          sx={{ fontSize: 14, color: "text.secondary", opacity: 0.5, mx: 0.1 }}
                        />
                      )}
                    </React.Fragment>
                  ))}
                </Box>
              ) : (
                <Typography
                  variant="body2"
                  sx={{ flex: 1, fontSize: "0.82rem", color: "text.secondary", opacity: 0.7 }}
                >
                  {t("collectionsPage.form.selectParent", "None (root collection)")}
                </Typography>
              )}
              {selectedParent && (
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelectChange("parentId", "");
                  }}
                  sx={{ p: 0.3 }}
                  aria-label="Clear parent collection"
                >
                  <CloseIcon sx={{ fontSize: 14 }} />
                </IconButton>
              )}
              <ChevronRightIcon
                sx={{
                  fontSize: 18,
                  color: "text.secondary",
                  opacity: 0.5,
                  transform: showParentPicker ? "rotate(90deg)" : "none",
                  transition: "transform 0.2s",
                }}
              />
            </Box>

            <Collapse in={showParentPicker} unmountOnExit>
              <Box
                sx={{
                  mt: 0.8,
                  borderRadius: 1.5,
                  border: `1px solid ${alpha(theme.palette.divider, 0.12)}`,
                  overflow: "hidden",
                }}
              >
                <Box
                  sx={{
                    px: 1.5,
                    py: 0.8,
                    display: "flex",
                    alignItems: "center",
                    gap: 0.8,
                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
                  }}
                >
                  <SearchIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                  <InputBase
                    placeholder={t(
                      "collectionsPage.form.searchParentCollections",
                      "Search collections..."
                    )}
                    value={parentSearch}
                    onChange={(e) => setParentSearch(e.target.value)}
                    sx={{ flex: 1, fontSize: "0.8rem", "& input": { py: 0.2 } }}
                    inputProps={{ "aria-label": "Search parent collections" }}
                  />
                  {parentSearch && (
                    <IconButton size="small" onClick={() => setParentSearch("")} sx={{ p: 0.2 }}>
                      <CloseIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  )}
                </Box>
                <Box sx={{ maxHeight: 180, overflowY: "auto" }}>
                  {filteredParentCollections.length === 0 ? (
                    <Typography
                      variant="caption"
                      sx={{
                        display: "block",
                        textAlign: "center",
                        py: 2,
                        color: "text.secondary",
                      }}
                    >
                      No collections found
                    </Typography>
                  ) : (
                    filteredParentCollections.map((col) => {
                      const path = getCollectionPath(col);
                      const isSelected = formData.parentId === col.id;
                      return (
                        <Box
                          key={col.id}
                          onClick={() => {
                            handleSelectChange("parentId", col.id);
                            setShowParentPicker(false);
                            setParentSearch("");
                          }}
                          sx={{
                            px: 1.5,
                            py: 0.8,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            bgcolor: isSelected
                              ? alpha(theme.palette.primary.main, isDark ? 0.1 : 0.05)
                              : "transparent",
                            "&:hover": {
                              bgcolor: alpha(theme.palette.primary.main, isDark ? 0.08 : 0.04),
                            },
                          }}
                        >
                          <FolderIcon
                            sx={{ fontSize: 16, color: "text.secondary", flexShrink: 0 }}
                          />
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            {path.length > 1 && (
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 0.2,
                                  mb: 0.1,
                                }}
                              >
                                {path.slice(0, -1).map((ancestor, idx) => (
                                  <React.Fragment key={ancestor.id}>
                                    <Typography
                                      variant="caption"
                                      sx={{
                                        fontSize: "0.65rem",
                                        color: "text.secondary",
                                        opacity: 0.65,
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {ancestor.name}
                                    </Typography>
                                    <ChevronRightIcon
                                      sx={{
                                        fontSize: 10,
                                        color: "text.secondary",
                                        opacity: 0.35,
                                      }}
                                    />
                                  </React.Fragment>
                                ))}
                              </Box>
                            )}
                            <Typography
                              variant="body2"
                              sx={{
                                fontSize: "0.8rem",
                                fontWeight: isSelected ? 600 : 400,
                                color: isSelected ? "primary.main" : "text.primary",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {col.name}
                            </Typography>
                          </Box>
                        </Box>
                      );
                    })
                  )}
                </Box>
              </Box>
            </Collapse>
          </Box>

          {/* Collection Type */}
          {collectionTypes.length > 0 && (
            <Box>
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  fontSize: "0.75rem",
                  color: "text.secondary",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  mb: 0.8,
                  display: "block",
                }}
              >
                {t("collectionsPage.form.type", "Collection Type")}
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.8 }}>
                <Chip
                  label={t("common.none", "None")}
                  size="small"
                  variant={formData.collectionTypeId === "" ? "filled" : "outlined"}
                  onClick={() => handleSelectChange("collectionTypeId", "")}
                  sx={{
                    borderRadius: 1.5,
                    fontWeight: 500,
                    fontSize: "0.78rem",
                    ...(formData.collectionTypeId === "" && {
                      bgcolor: alpha(theme.palette.primary.main, isDark ? 0.15 : 0.1),
                      color: "primary.main",
                      borderColor: "primary.main",
                    }),
                  }}
                />
                {collectionTypes
                  .filter((type) => type.isActive)
                  .map((type) => (
                    <Chip
                      key={type.id}
                      label={type.name}
                      size="small"
                      variant={formData.collectionTypeId === type.id ? "filled" : "outlined"}
                      onClick={() => handleSelectChange("collectionTypeId", type.id)}
                      icon={
                        <Box
                          sx={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            bgcolor: type.color,
                            ml: 0.5,
                          }}
                        />
                      }
                      sx={{
                        borderRadius: 1.5,
                        fontWeight: 500,
                        fontSize: "0.78rem",
                        ...(formData.collectionTypeId === type.id && {
                          bgcolor: alpha(type.color, isDark ? 0.2 : 0.12),
                          color: type.color,
                          borderColor: type.color,
                        }),
                      }}
                    />
                  ))}
              </Box>
            </Box>
          )}

          {/* Visibility */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              px: 1.5,
              py: 1,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.text.primary, isDark ? 0.04 : 0.02),
              border: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              {formData.isPublic ? (
                <PublicIcon sx={{ fontSize: 18, color: "success.main" }} />
              ) : (
                <PrivateIcon sx={{ fontSize: 18, color: "info.main" }} />
              )}
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 500, fontSize: "0.82rem" }}>
                  {formData.isPublic
                    ? t("collectionsPage.form.public", "Public")
                    : t("collectionsPage.form.private", "Private")}
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>
                  {formData.isPublic
                    ? "Visible to all users"
                    : "Only visible to you and shared users"}
                </Typography>
              </Box>
            </Box>
            <Switch
              checked={formData.isPublic}
              onChange={handleInputChange("isPublic")}
              disabled={isSaving}
              size="small"
            />
          </Box>

          {/* Error */}
          {updateCollectionMutation.isError && (
            <Alert
              severity="error"
              variant="outlined"
              sx={{ borderRadius: 2, fontSize: "0.82rem" }}
            >
              {t("common.error", "Failed to update collection. Please try again.")}
            </Alert>
          )}
        </Box>

        {/* Footer */}
        <Box
          sx={{
            px: 3,
            py: 2,
            borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1.5,
          }}
        >
          {/* Change indicator */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {hasChanges && (
              <Typography
                variant="caption"
                sx={{
                  color: "warning.main",
                  fontSize: "0.72rem",
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    bgcolor: "warning.main",
                    flexShrink: 0,
                  }}
                />
                Unsaved changes
              </Typography>
            )}
          </Box>

          <Box sx={{ display: "flex", gap: 1, flexShrink: 0 }}>
            <Box
              component="button"
              onClick={handleClose}
              disabled={isSaving}
              sx={{
                px: 2.5,
                py: 0.9,
                border: "none",
                borderRadius: 1.5,
                bgcolor: "transparent",
                color: "text.secondary",
                fontSize: "0.82rem",
                fontWeight: 500,
                cursor: "pointer",
                "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.06) },
                "&:disabled": { opacity: 0.5, cursor: "default" },
              }}
            >
              {t("common.cancel", "Cancel")}
            </Box>
            <Box
              component="button"
              onClick={handleSubmit}
              disabled={isSaving || !formData.name.trim() || !hasChanges}
              sx={{
                px: 3,
                py: 0.9,
                border: "none",
                borderRadius: 1.5,
                bgcolor: "primary.main",
                color: "primary.contrastText",
                fontSize: "0.82rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 0.7,
                transition: "background-color 0.15s ease, opacity 0.15s ease",
                "&:hover": { bgcolor: "primary.dark" },
                "&:disabled": { opacity: 0.4, cursor: "default" },
              }}
            >
              {isSaving ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <SaveIcon sx={{ fontSize: 16 }} />
              )}
              {isSaving ? t("common.saving", "Saving...") : t("common.save", "Save Changes")}
            </Box>
          </Box>
        </Box>
      </DialogContent>
    </Dialog>
  );
};
