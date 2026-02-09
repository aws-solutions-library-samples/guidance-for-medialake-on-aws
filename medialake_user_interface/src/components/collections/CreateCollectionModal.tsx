import React, { useState, useMemo, useCallback } from "react";
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
  Tooltip,
  Chip,
} from "@mui/material";
import {
  Close as CloseIcon,
  Add as AddIcon,
  Folder as FolderIcon,
  ChevronRight as ChevronRightIcon,
  Search as SearchIcon,
  FolderOpen as FolderOpenIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from "@mui/icons-material";
import {
  useCreateCollection,
  useGetCollections,
  useGetCollectionTypes,
  useSetCollectionThumbnail,
  useSetCollectionIcon,
  type Collection,
} from "../../api/hooks/useCollections";
import { ThumbnailSelector } from "./ThumbnailSelector";

interface CreateCollectionModalProps {
  open: boolean;
  onClose: () => void;
  defaultParentId?: string;
}

export const CreateCollectionModal: React.FC<CreateCollectionModalProps> = ({
  open,
  onClose,
  defaultParentId,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    parentId: defaultParentId || "",
    isPublic: false,
    collectionTypeId: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showParentPicker, setShowParentPicker] = useState(false);
  const [parentSearch, setParentSearch] = useState("");

  // Pending thumbnail
  const [pendingThumbnail, setPendingThumbnail] = useState<{
    type: "icon" | "upload";
    value: string;
  } | null>(null);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState<string | null>(null);

  // API hooks
  const createCollectionMutation = useCreateCollection();
  const setThumbnailMutation = useSetCollectionThumbnail();
  const setIconMutation = useSetCollectionIcon();
  const { data: collectionsResponse } = useGetCollections();
  const { data: collectionTypesResponse } = useGetCollectionTypes();

  const collections = collectionsResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  const isPending =
    createCollectionMutation.isPending ||
    setThumbnailMutation.isPending ||
    setIconMutation.isPending;

  // Build breadcrumb path for a collection
  const getCollectionPath = useCallback(
    (collection: Collection): Collection[] => {
      const path: Collection[] = [];
      let current: Collection | undefined = collection;
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

  // Filter parent collections by search
  const filteredParentCollections = useMemo(() => {
    if (!parentSearch.trim()) return collections;
    const query = parentSearch.toLowerCase();
    return collections.filter((c) => {
      const path = getCollectionPath(c);
      const fullPath = path.map((p) => p.name).join(" / ");
      return c.name.toLowerCase().includes(query) || fullPath.toLowerCase().includes(query);
    });
  }, [collections, parentSearch, getCollectionPath]);

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

  const handleSelectIcon = (iconName: string) => {
    setPendingThumbnail({ type: "icon", value: iconName });
    setUploadPreviewUrl(null);
  };

  const handleUploadImage = (base64Data: string) => {
    setPendingThumbnail({ type: "upload", value: base64Data });
    setUploadPreviewUrl(`data:image/png;base64,${base64Data}`);
  };

  const handleRemoveThumbnail = () => {
    setPendingThumbnail(null);
    setUploadPreviewUrl(null);
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    try {
      const createData = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        parentId: formData.parentId || undefined,
        isPublic: formData.isPublic,
        collectionTypeId: formData.collectionTypeId || undefined,
      };
      const result = await createCollectionMutation.mutateAsync(createData);
      const newCollectionId = result?.data?.id || (result as any)?.id;
      if (newCollectionId && pendingThumbnail) {
        try {
          if (pendingThumbnail.type === "icon") {
            await setIconMutation.mutateAsync({
              collectionId: newCollectionId,
              iconName: pendingThumbnail.value,
            });
          } else if (pendingThumbnail.type === "upload") {
            await setThumbnailMutation.mutateAsync({
              collectionId: newCollectionId,
              data: { source: "upload", data: pendingThumbnail.value },
            });
          }
        } catch {
          // Thumbnail failed but collection was created
        }
      }
      resetAndClose();
    } catch {
      // Error surfaced via mutation state
    }
  };

  const resetAndClose = () => {
    setFormData({
      name: "",
      description: "",
      parentId: defaultParentId || "",
      isPublic: false,
      collectionTypeId: "",
    });
    setPendingThumbnail(null);
    setUploadPreviewUrl(null);
    setErrors({});
    setShowParentPicker(false);
    setParentSearch("");
    onClose();
  };

  const handleClose = () => {
    if (!isPending) resetAndClose();
  };

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
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.2 }}>
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.primary.main, isDark ? 0.15 : 0.1),
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <AddIcon sx={{ fontSize: 18, color: "primary.main" }} />
          </Box>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              fontSize: "1.1rem",
              letterSpacing: "-0.01em",
            }}
          >
            {t("collectionsPage.createCollection", "Create Collection")}
          </Typography>
        </Box>
        <IconButton
          onClick={handleClose}
          disabled={isPending}
          size="small"
          sx={{
            color: "text.secondary",
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
            currentThumbnailType={pendingThumbnail?.type}
            currentThumbnailValue={
              pendingThumbnail?.type === "icon" ? pendingThumbnail.value : undefined
            }
            currentThumbnailUrl={uploadPreviewUrl || undefined}
            onSelectIcon={handleSelectIcon}
            onUploadImage={handleUploadImage}
            onRemoveThumbnail={handleRemoveThumbnail}
            isLoading={false}
            disabled={isPending}
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
            disabled={isPending}
            autoFocus
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
            disabled={isPending}
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
              onClick={() => !isPending && setShowParentPicker(!showParentPicker)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                px: 1.5,
                py: 1,
                borderRadius: 1.5,
                border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                cursor: isPending ? "default" : "pointer",
                transition: "all 0.15s",
                "&:hover": isPending
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
                {/* Search within parent picker */}
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
                      sx={{ display: "block", textAlign: "center", py: 2, color: "text.secondary" }}
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
                                sx={{ display: "flex", alignItems: "center", gap: 0.2, mb: 0.1 }}
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
              disabled={isPending}
              size="small"
            />
          </Box>

          {/* Error */}
          {createCollectionMutation.isError && (
            <Alert
              severity="error"
              variant="outlined"
              sx={{ borderRadius: 2, fontSize: "0.82rem" }}
            >
              {t("collectionsPage.createFailed", "Failed to create collection. Please try again.")}
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
            justifyContent: "flex-end",
            gap: 1,
          }}
        >
          <Box
            component="button"
            onClick={handleClose}
            disabled={isPending}
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
              fontFamily: "inherit",
              "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.06) },
              "&:disabled": { opacity: 0.5, cursor: "default" },
            }}
          >
            {t("common.cancel", "Cancel")}
          </Box>
          <Box
            component="button"
            onClick={handleSubmit}
            disabled={isPending || !formData.name.trim()}
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
              fontFamily: "inherit",
              display: "flex",
              alignItems: "center",
              gap: 0.7,
              transition: "all 0.15s ease",
              "&:hover": { bgcolor: "primary.dark" },
              "&:disabled": { opacity: 0.4, cursor: "default" },
            }}
          >
            {isPending ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <AddIcon sx={{ fontSize: 18 }} />
            )}
            {isPending
              ? t("common.creating", "Creating...")
              : t("collectionsPage.createCollection", "Create Collection")}
          </Box>
        </Box>
      </DialogContent>
    </Dialog>
  );
};
