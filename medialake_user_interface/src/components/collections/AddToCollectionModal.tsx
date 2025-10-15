import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Divider,
} from "@mui/material";
import {
  Folder as FolderIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Share as SharedIcon,
} from "@mui/icons-material";
import { useGetCollections } from "../../api/hooks/useCollections";

interface AddToCollectionModalProps {
  open: boolean;
  onClose: () => void;
  assetId: string;
  assetName: string;
  assetType: string;
  onAddToCollection: (collectionId: string) => Promise<void>;
}

export const AddToCollectionModal: React.FC<AddToCollectionModalProps> = ({
  open,
  onClose,
  assetId,
  assetName,
  assetType,
  onAddToCollection,
}) => {
  const { t } = useTranslation();
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get user's collections
  const { data: collectionsResponse, isLoading } = useGetCollections();
  const collections = collectionsResponse?.data || [];

  // Filter collections that can accept assets
  const availableCollections = collections.filter(
    (collection) =>
      collection.status === "ACTIVE" &&
      (collection.userRole === "owner" ||
        collection.userRole === "admin" ||
        collection.userRole === "editor"),
  );

  const handleSubmit = async () => {
    if (!selectedCollectionId) {
      return;
    }

    setIsAdding(true);
    setError(null);

    try {
      await onAddToCollection(selectedCollectionId);

      // Reset state and close modal
      setSelectedCollectionId("");
      setError(null);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to add asset to collection");
    } finally {
      setIsAdding(false);
    }
  };

  const handleClose = () => {
    if (!isAdding) {
      setSelectedCollectionId("");
      setError(null);
      onClose();
    }
  };

  const getCollectionTypeIcon = (collection: any) => {
    if (collection.isPublic) return <PublicIcon fontSize="small" />;
    if (collection.userRole === "owner")
      return <PrivateIcon fontSize="small" />;
    return <SharedIcon fontSize="small" />;
  };

  const getCollectionTypeBadge = (collection: any) => {
    if (collection.isPublic) {
      return (
        <Chip
          label="Public"
          size="small"
          sx={{
            backgroundColor: "#e8f5e8",
            color: "#2e7d32",
            fontSize: "0.75rem",
          }}
        />
      );
    }
    if (collection.userRole === "owner") {
      return (
        <Chip
          label="Private"
          size="small"
          sx={{
            backgroundColor: "#e3f2fd",
            color: "#1976d2",
            fontSize: "0.75rem",
          }}
        />
      );
    }
    return (
      <Chip
        label="Shared"
        size="small"
        sx={{
          backgroundColor: "#fff3e0",
          color: "#ed6c02",
          fontSize: "0.75rem",
        }}
      />
    );
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
          Add to Collection
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Add "{assetName}" to a collection
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ pb: 2 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          {isLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
              <CircularProgress />
            </Box>
          ) : availableCollections.length === 0 ? (
            <Box sx={{ textAlign: "center", py: 4 }}>
              <FolderIcon
                sx={{ fontSize: 48, color: "text.secondary", mb: 2 }}
              />
              <Typography variant="body1" color="text.secondary">
                No collections available
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Create a collection first to organize your assets
              </Typography>
            </Box>
          ) : (
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 2 }}>
                Select a collection:
              </Typography>

              <List sx={{ maxHeight: 300, overflow: "auto" }}>
                {availableCollections.map((collection) => (
                  <ListItem key={collection.id} disablePadding>
                    <ListItemButton
                      selected={selectedCollectionId === collection.id}
                      onClick={() => setSelectedCollectionId(collection.id)}
                      sx={{
                        borderRadius: 1,
                        mb: 1,
                        "&.Mui-selected": {
                          backgroundColor: "primary.main",
                          color: "primary.contrastText",
                          "&:hover": {
                            backgroundColor: "primary.dark",
                          },
                          "& .MuiListItemIcon-root": {
                            color: "primary.contrastText",
                          },
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 40 }}>
                        {getCollectionTypeIcon(collection)}
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                            }}
                          >
                            <Typography variant="body1">
                              {collection.name}
                            </Typography>
                            {getCollectionTypeBadge(collection)}
                          </Box>
                        }
                        secondary={
                          <Box sx={{ mt: 0.5 }}>
                            <Typography variant="caption">
                              {collection.itemCount} items
                              {collection.childCollectionCount > 0 &&
                                ` • ${collection.childCollectionCount} subcollections`}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={handleClose} disabled={isAdding}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={
            !selectedCollectionId ||
            isAdding ||
            availableCollections.length === 0
          }
          startIcon={isAdding ? <CircularProgress size={20} /> : null}
        >
          {isAdding ? "Adding..." : "Add to Collection"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
