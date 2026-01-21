import React, { useState, useMemo } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Autocomplete,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  Avatar,
  IconButton,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Share as ShareIcon,
  PersonAdd as PersonAddIcon,
  Delete as DeleteIcon,
  Visibility as ViewerIcon,
  Edit as EditorIcon,
  Close as CloseIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetUsers } from "@/api/hooks/useUsers";
import {
  useShareCollection,
  useUnshareCollection,
  useGetCollectionShares,
  type Collection,
  type ShareCollectionRequest,
} from "@/api/hooks/useCollections";
import type { User } from "@/api/types/api.types";

interface ShareManagementModalProps {
  open: boolean;
  onClose: () => void;
  collection: Collection | null;
}

export const ShareManagementModal: React.FC<ShareManagementModalProps> = ({
  open,
  onClose,
  collection,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  // State
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<"VIEWER" | "EDITOR">("VIEWER");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  // API hooks
  const { data: users, isLoading: isLoadingUsers } = useGetUsers();
  const { data: sharesResponse, isLoading: isLoadingShares } = useGetCollectionShares(
    collection?.id || "",
    open && !!collection?.id
  );
  const shareCollectionMutation = useShareCollection();
  const unshareCollectionMutation = useUnshareCollection();

  const existingShares = sharesResponse?.data || [];

  // Filter out users who are already shared with
  const availableUsers = useMemo(() => {
    if (!users) return [];
    const sharedUserIds = new Set(existingShares.map((s) => s.userId || s.targetId));
    return users.filter(
      (user) => !sharedUserIds.has(user.username) && user.username !== collection?.ownerId
    );
  }, [users, existingShares, collection?.ownerId]);

  const handleShare = async () => {
    if (!selectedUser || !collection?.id) return;

    setError(null);

    const shareData: ShareCollectionRequest = {
      targetUserId: selectedUser.username,
      accessLevel: selectedRole,
      message: message || undefined,
    };

    try {
      await shareCollectionMutation.mutateAsync({
        id: collection.id,
        data: shareData,
      });

      // Reset form
      setSelectedUser(null);
      setSelectedRole("VIEWER");
      setMessage("");
    } catch (err: any) {
      setError(err.message || t("collections.sharing.shareFailed", "Failed to share collection"));
    }
  };

  const handleUnshare = async (userId: string) => {
    if (!collection?.id) return;

    try {
      await unshareCollectionMutation.mutateAsync({
        id: collection.id,
        userId,
      });
    } catch (err: any) {
      setError(err.message || t("collections.sharing.unshareFailed", "Failed to remove share"));
    }
  };

  const handleClose = () => {
    setSelectedUser(null);
    setSelectedRole("VIEWER");
    setMessage("");
    setError(null);
    onClose();
  };

  const getRoleIcon = (role: string) => {
    switch (role?.toUpperCase()) {
      case "EDITOR":
      case "WRITE":
        return <EditorIcon sx={{ fontSize: 16 }} />;
      default:
        return <ViewerIcon sx={{ fontSize: 16 }} />;
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role?.toUpperCase()) {
      case "EDITOR":
      case "WRITE":
        return t("collections.roles.editor", "Editor");
      default:
        return t("collections.roles.viewer", "Viewer");
    }
  };

  if (!collection) return null;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 },
      }}
    >
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <ShareIcon color="primary" />
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">{t("collections.sharing.title", "Share Collection")}</Typography>
          <Typography variant="body2" color="text.secondary">
            {collection.name}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Add New Share Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
            <PersonAddIcon sx={{ fontSize: 18, mr: 0.5, verticalAlign: "text-bottom" }} />
            {t("collections.sharing.addPeople", "Add People")}
          </Typography>

          <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
            <Autocomplete
              sx={{ flex: 2 }}
              options={availableUsers}
              getOptionLabel={(user) =>
                user.name ||
                `${user.given_name || ""} ${user.family_name || ""}`.trim() ||
                user.email ||
                user.username
              }
              renderOption={(props, user) => (
                <li {...props}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Avatar
                      sx={{
                        width: 32,
                        height: 32,
                        fontSize: "0.875rem",
                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                        color: "primary.main",
                      }}
                    >
                      {(user.given_name?.[0] || user.email?.[0] || user.username[0]).toUpperCase()}
                    </Avatar>
                    <Box>
                      <Typography variant="body2">
                        {user.name ||
                          `${user.given_name || ""} ${user.family_name || ""}`.trim() ||
                          user.username}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {user.email}
                      </Typography>
                    </Box>
                  </Box>
                </li>
              )}
              value={selectedUser}
              onChange={(_, newValue) => setSelectedUser(newValue)}
              loading={isLoadingUsers}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label={t("collections.sharing.selectUser", "Select user")}
                  size="small"
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {isLoadingUsers ? <CircularProgress color="inherit" size={20} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />

            <FormControl sx={{ minWidth: 120 }} size="small">
              <InputLabel>{t("collections.sharing.role", "Role")}</InputLabel>
              <Select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value as "VIEWER" | "EDITOR")}
                label={t("collections.sharing.role", "Role")}
              >
                <MenuItem value="VIEWER">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <ViewerIcon sx={{ fontSize: 18 }} />
                    {t("collections.roles.viewer", "Viewer")}
                  </Box>
                </MenuItem>
                <MenuItem value="EDITOR">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <EditorIcon sx={{ fontSize: 18 }} />
                    {t("collections.roles.editor", "Editor")}
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Box>

          <TextField
            fullWidth
            size="small"
            label={t("collections.sharing.message", "Message (optional)")}
            placeholder={t("collections.sharing.messagePlaceholder", "Add a message...")}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            multiline
            rows={2}
            sx={{ mb: 2 }}
          />

          <Button
            variant="contained"
            startIcon={<ShareIcon />}
            onClick={handleShare}
            disabled={!selectedUser || shareCollectionMutation.isPending}
            fullWidth
          >
            {shareCollectionMutation.isPending
              ? t("common.sharing", "Sharing...")
              : t("collections.sharing.share", "Share")}
          </Button>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Existing Shares Section */}
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
            {t("collections.sharing.sharedWith", "Shared With")} ({existingShares.length})
          </Typography>

          {isLoadingShares ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : existingShares.length === 0 ? (
            <Box
              sx={{
                textAlign: "center",
                py: 3,
                px: 2,
                backgroundColor: alpha(theme.palette.grey[500], 0.04),
                borderRadius: 1,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                {t("collections.sharing.notShared", "This collection hasn't been shared yet")}
              </Typography>
            </Box>
          ) : (
            <List dense sx={{ bgcolor: "background.paper", borderRadius: 1 }}>
              {existingShares.map((share, index) => (
                <ListItem
                  key={share.userId || share.targetId || index}
                  sx={{
                    borderBottom:
                      index < existingShares.length - 1
                        ? `1px solid ${theme.palette.divider}`
                        : "none",
                  }}
                >
                  <ListItemAvatar>
                    <Avatar
                      sx={{
                        width: 36,
                        height: 36,
                        fontSize: "0.875rem",
                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                        color: "primary.main",
                      }}
                    >
                      {(share.userId || share.targetId || "U")[0].toUpperCase()}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={share.userId || share.targetId}
                    secondary={
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
                        <Chip
                          icon={getRoleIcon(share.role)}
                          label={getRoleLabel(share.role)}
                          size="small"
                          variant="outlined"
                          sx={{ height: 22, fontSize: "0.7rem" }}
                        />
                        {share.sharedBy && (
                          <Typography variant="caption" color="text.secondary">
                            by {share.sharedBy}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      size="small"
                      onClick={() => handleUnshare(share.userId || share.targetId || "")}
                      disabled={unshareCollectionMutation.isPending}
                      sx={{
                        color: "error.main",
                        "&:hover": {
                          backgroundColor: alpha(theme.palette.error.main, 0.1),
                        },
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose}>{t("common.close", "Close")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ShareManagementModal;
