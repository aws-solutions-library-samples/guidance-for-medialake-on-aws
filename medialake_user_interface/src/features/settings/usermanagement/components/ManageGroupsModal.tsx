import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Typography,
  Box,
  Tabs,
  Tab,
  Card,
  CardContent,
  CardActions,
  TextField,
  Button,
  IconButton,
  CircularProgress,
  Snackbar,
  Alert,
  Tooltip,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { useTranslation } from "react-i18next";
import { useGetGroups, useUpdateGroup, useDeleteGroup } from "@/api/hooks/useGroups";
import { Group, UpdateGroupRequest } from "@/api/types/group.types";

interface ManageGroupsModalProps {
  open: boolean;
  onClose: () => void;
}

interface EditGroupFormData {
  name: string;
  description: string;
  department: string;
}

const ManageGroupsModal: React.FC<ManageGroupsModalProps> = ({ open, onClose }) => {
  const { t } = useTranslation();
  const [selectedTab, setSelectedTab] = useState(0);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [editFormData, setEditFormData] = useState<EditGroupFormData>({
    name: "",
    description: "",
    department: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmDeleteGroup, setConfirmDeleteGroup] = useState<Group | null>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({
    open: false,
    message: "",
    severity: "success",
  });

  // Queries
  const { data: groups, isLoading: isLoadingGroups } = useGetGroups(true);

  const updateGroupMutation = useUpdateGroup();
  const deleteGroupMutation = useDeleteGroup();

  // Reset editing state when modal closes
  useEffect(() => {
    if (!open) {
      setEditingGroup(null);
      setEditFormData({ name: "", description: "", department: "" });
      setErrors({});
      setConfirmDeleteGroup(null);
    }
  }, [open]);

  // Update form data when editing group changes
  useEffect(() => {
    if (editingGroup) {
      setEditFormData({
        name: editingGroup.name,
        description: editingGroup.description,
        department: editingGroup.department || "",
      });
    }
  }, [editingGroup]);

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
    setEditingGroup(null);
    setConfirmDeleteGroup(null);
  };

  const handleEditGroup = (group: Group) => {
    setEditingGroup(group);
  };

  const handleCancelEdit = () => {
    setEditingGroup(null);
    setErrors({});
  };

  const handleEditFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEditFormData((prev) => ({ ...prev, [name]: value }));

    // Clear error when user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }));
    }
  };

  const validateEditForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!editFormData.name.trim()) {
      newErrors.name = t("validation.required");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSaveGroup = async () => {
    if (!editingGroup || !validateEditForm()) return;

    const updates: UpdateGroupRequest = {};
    if (editFormData.name !== editingGroup.name) {
      updates.name = editFormData.name;
    }
    if (editFormData.description !== editingGroup.description) {
      updates.description = editFormData.description;
    }
    if (editFormData.department !== (editingGroup.department || "")) {
      updates.department = editFormData.department;
    }

    try {
      await updateGroupMutation.mutateAsync({
        id: editingGroup.id,
        updates,
      });

      setSnackbar({
        open: true,
        message: t("groups.messages.updateSuccess"),
        severity: "success",
      });

      setEditingGroup(null);
    } catch (error) {
      setSnackbar({
        open: true,
        message: t("groups.messages.updateError"),
        severity: "error",
      });
    }
  };

  const handleConfirmDeleteGroup = (group: Group) => {
    setConfirmDeleteGroup(group);
  };

  const handleCancelDelete = () => {
    setConfirmDeleteGroup(null);
  };

  const handleDeleteGroup = async () => {
    if (!confirmDeleteGroup) return;

    try {
      await deleteGroupMutation.mutateAsync(confirmDeleteGroup.id);

      setSnackbar({
        open: true,
        message: t("groups.messages.deleteSuccess"),
        severity: "success",
      });

      setConfirmDeleteGroup(null);

      // If we deleted the currently selected tab, switch to the first tab
      if (groups && selectedTab >= groups.length - 1) {
        setSelectedTab(Math.max(0, groups.length - 2));
      }
    } catch (error) {
      setSnackbar({
        open: true,
        message: t("groups.messages.deleteError"),
        severity: "error",
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" fontWeight={600}>
              {t("groups.actions.manageGroups")}
            </Typography>
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          {isLoadingGroups ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress />
            </Box>
          ) : groups && groups.length > 0 ? (
            <Box sx={{ width: "100%" }}>
              <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
                <Tabs
                  value={selectedTab}
                  onChange={handleTabChange}
                  variant="scrollable"
                  scrollButtons="auto"
                >
                  {groups.map((group) => (
                    <Tab key={group.id} label={group.name} />
                  ))}
                </Tabs>
              </Box>

              {groups.map((group, index) => (
                <Box
                  key={group.id}
                  role="tabpanel"
                  hidden={selectedTab !== index}
                  id={`group-tabpanel-${index}`}
                  aria-labelledby={`group-tab-${index}`}
                >
                  {selectedTab === index && (
                    <Box>
                      {confirmDeleteGroup?.id === group.id ? (
                        <Card variant="outlined" sx={{ mb: 3, p: 2 }}>
                          <CardContent>
                            <Typography variant="h6" color="error" gutterBottom>
                              {t("groups.messages.confirmDelete")}
                            </Typography>
                            <Typography>
                              {t("groups.messages.deleteWarning", {
                                name: group.name,
                              })}
                            </Typography>
                          </CardContent>
                          <CardActions>
                            <Button onClick={handleCancelDelete} variant="outlined">
                              {t("common.actions.cancel")}
                            </Button>
                            <Button
                              onClick={handleDeleteGroup}
                              variant="contained"
                              color="error"
                              disabled={deleteGroupMutation.isPending}
                              startIcon={
                                deleteGroupMutation.isPending ? (
                                  <CircularProgress size={20} />
                                ) : null
                              }
                            >
                              {t("common.actions.delete")}
                            </Button>
                          </CardActions>
                        </Card>
                      ) : editingGroup?.id === group.id ? (
                        <Card variant="outlined" sx={{ mb: 3, p: 2 }}>
                          <CardContent>
                            <Typography variant="h6" gutterBottom>
                              {t("groups.actions.editGroup")}
                            </Typography>
                            <TextField
                              name="name"
                              label={t("groups.fields.name")}
                              value={editFormData.name}
                              onChange={handleEditFormChange}
                              fullWidth
                              margin="normal"
                              error={!!errors.name}
                              helperText={errors.name}
                              required
                            />
                            <TextField
                              name="description"
                              label={t("groups.fields.description")}
                              value={editFormData.description}
                              onChange={handleEditFormChange}
                              fullWidth
                              margin="normal"
                              multiline
                              rows={3}
                            />
                            <TextField
                              name="department"
                              label={t("groups.fields.department")}
                              value={editFormData.department}
                              onChange={handleEditFormChange}
                              fullWidth
                              margin="normal"
                            />
                          </CardContent>
                          <CardActions>
                            <Button onClick={handleCancelEdit} variant="outlined">
                              {t("common.actions.cancel")}
                            </Button>
                            <Button
                              onClick={handleSaveGroup}
                              variant="contained"
                              disabled={updateGroupMutation.isPending}
                              startIcon={
                                updateGroupMutation.isPending ? (
                                  <CircularProgress size={20} />
                                ) : null
                              }
                            >
                              {t("common.actions.save")}
                            </Button>
                          </CardActions>
                        </Card>
                      ) : (
                        <Card variant="outlined" sx={{ mb: 3, p: 2 }}>
                          <CardContent>
                            <Box
                              display="flex"
                              justifyContent="space-between"
                              alignItems="flex-start"
                            >
                              <Box>
                                <Typography variant="h6" gutterBottom>
                                  {group.name}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  {group.description || t("groups.noDescription")}
                                </Typography>
                                {group.department && (
                                  <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{ mt: 0.5 }}
                                  >
                                    <strong>{t("groups.fields.department")}:</strong>{" "}
                                    {group.department}
                                  </Typography>
                                )}
                              </Box>
                              <Box>
                                <Tooltip title={t("common.actions.edit")}>
                                  <IconButton onClick={() => handleEditGroup(group)} size="small">
                                    <EditIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title={t("common.actions.delete")}>
                                  <IconButton
                                    onClick={() => handleConfirmDeleteGroup(group)}
                                    size="small"
                                    color="error"
                                  >
                                    <DeleteIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            </Box>
                          </CardContent>
                        </Card>
                      )}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          ) : (
            <Box textAlign="center" py={4}>
              <Typography variant="body1" gutterBottom>
                {t("groups.noGroups")}
              </Typography>
              <Button variant="contained" startIcon={<AddIcon />} onClick={onClose} sx={{ mt: 2 }}>
                {t("groups.actions.createGroup")}
              </Button>
            </Box>
          )}
        </DialogContent>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: "100%" }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default ManageGroupsModal;
