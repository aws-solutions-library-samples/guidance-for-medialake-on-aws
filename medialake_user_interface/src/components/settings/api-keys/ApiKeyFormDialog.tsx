import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Box,
  Typography,
  IconButton,
  FormHelperText,
  Alert,
  Divider,
  Checkbox,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useTranslation } from "react-i18next";
import { ActionButton } from "@/components/common/button/ActionButton";
import { useCreateApiKey, useUpdateApiKey } from "@/api/hooks/useApiKeys";
import { ApiKey, CreateApiKeyRequest, UpdateApiKeyRequest } from "@/api/types/apiKey.types";

interface ApiKeyFormDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
  apiKey?: ApiKey | null;
  isEditMode?: boolean;
}

const ApiKeyFormDialog: React.FC<ApiKeyFormDialogProps> = ({
  open,
  onClose,
  onSuccess,
  apiKey,
  isEditMode = false,
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    isEnabled: true,
  });
  const [rotateKey, setRotateKey] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const createMutation = useCreateApiKey();
  const updateMutation = useUpdateApiKey();

  // Initialize form data when editing
  useEffect(() => {
    if (isEditMode && apiKey) {
      setFormData({
        name: apiKey.name,
        description: apiKey.description,
        isEnabled: apiKey.isEnabled,
      });
    } else {
      setFormData({
        name: "",
        description: "",
        isEnabled: true,
      });
    }
    setRotateKey(false);
    setErrors({});
    setNewSecret(null);
  }, [isEditMode, apiKey, open]);

  // Validate form
  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = "API key name is required";
    } else if (formData.name.trim().length < 3) {
      newErrors.name = "API key name must be at least 3 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async () => {
    if (!validateForm()) return;

    try {
      if (isEditMode && apiKey) {
        // Update existing API key
        const updateData: UpdateApiKeyRequest = {
          name: formData.name.trim(),
          description: formData.description.trim(),
          isEnabled: formData.isEnabled,
        };

        if (rotateKey) {
          updateData.rotateKey = true;
        }

        const response = await updateMutation.mutateAsync({
          id: apiKey.id,
          updates: updateData,
        });

        // Check if key was rotated and new secret is returned
        if (rotateKey && response.data && "apiKey" in response.data) {
          setNewSecret(response.data.apiKey);
          return; // Don't close dialog yet, show the new secret
        }

        onSuccess("API key updated successfully");
      } else {
        // Create new API key
        const createData: CreateApiKeyRequest = {
          name: formData.name.trim(),
          description: formData.description.trim(),
          isEnabled: formData.isEnabled,
        };

        const response = await createMutation.mutateAsync(createData);

        // Show the new secret
        if (response.data && response.data.apiKey) {
          setNewSecret(response.data.apiKey);
          return; // Don't close dialog yet, show the new secret
        }

        onSuccess("API key created successfully");
      }
    } catch (error: any) {
      console.error("Failed to save API key:", error);
      setErrors({
        general: error.message || "Failed to save API key. Please try again.",
      });
    }
  };

  // Handle form input changes
  const handleInputChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));

    // Clear specific field error
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  // Handle dialog close
  const handleClose = () => {
    if (newSecret) {
      // If showing new secret, just close and call success
      onSuccess(isEditMode ? "API key updated successfully" : "API key created successfully");
      setNewSecret(null);
    } else {
      onClose();
    }
  };

  // Copy secret to clipboard
  const handleCopySecret = async () => {
    if (newSecret) {
      try {
        await navigator.clipboard.writeText(newSecret);
        // Could show a toast notification here
      } catch (error) {
        console.error("Failed to copy to clipboard:", error);
      }
    }
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          minHeight: "400px",
        },
      }}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            {newSecret ? "API Key Created" : isEditMode ? "Edit API Key" : "Create API Key"}
          </Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ overflow: "visible" }}>
        {/* Show new secret if available */}
        {newSecret && (
          <Box sx={{ mb: 3 }}>
            <Alert severity="success" sx={{ mb: 2 }}>
              {isEditMode ? "API key rotated successfully!" : "API key created successfully!"}
            </Alert>
            <Typography variant="subtitle2" gutterBottom>
              Your API Key Secret (save this securely):
            </Typography>
            <TextField
              fullWidth
              value={newSecret}
              InputProps={{
                readOnly: true,
                sx: {
                  fontFamily: "monospace",
                  fontSize: "0.875rem",
                },
              }}
              sx={{ mb: 2 }}
            />
            <ActionButton variant="outlined" size="small" onClick={handleCopySecret}>
              Copy to Clipboard
            </ActionButton>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              {t("settings.apiKeys.form.importantNotice")}
            </Typography>
          </Box>
        )}

        {/* Show form if not displaying secret */}
        {!newSecret && (
          <Box>
            {/* General Error */}
            {errors.general && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {errors.general}
              </Alert>
            )}

            {/* Name Field */}
            {/* Name Field */}
            <TextField
              label={t("apiKeys.form.name")}
              fullWidth
              required
              value={formData.name}
              onChange={(e) => handleInputChange("name", e.target.value)}
              error={!!errors.name}
              helperText={errors.name || t("common.placeholders.apiKeyDescription")}
              sx={{ mb: 2 }}
            />

            {/* Description Field */}
            <TextField
              label={t("apiKeys.form.description")}
              fullWidth
              multiline
              rows={3}
              value={formData.description}
              onChange={(e) => handleInputChange("description", e.target.value)}
              helperText={t("apiKeys.form.descriptionHelper")}
              sx={{ mb: 2 }}
            />

            {/* Enabled Switch */}
            <FormControlLabel
              control={
                <Switch
                  checked={formData.isEnabled}
                  onChange={(e) => handleInputChange("isEnabled", e.target.checked)}
                />
              }
              label={t("apiKeys.form.enabled")}
              sx={{ mb: 2 }}
            />
            <FormHelperText sx={{ mt: -1, mb: 2 }}>
              {t(
                "apiKeys.form.disabledHelperText",
                "Disabled API keys cannot be used for authentication"
              )}
            </FormHelperText>

            {/* Rotate Key Option (Edit Mode Only) */}
            {isEditMode && (
              <>
                <Divider sx={{ my: 2 }} />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={rotateKey}
                      onChange={(e) => setRotateKey(e.target.checked)}
                    />
                  }
                  label={t("apiKeys.form.rotateApiKey")}
                />
                <FormHelperText>
                  {t(
                    "apiKeys.form.rotateHelperText",
                    "Generate a new secret for this API key. The old secret will become invalid."
                  )}
                </FormHelperText>
              </>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        {newSecret ? (
          <ActionButton variant="contained" onClick={handleClose}>
            Done
          </ActionButton>
        ) : (
          <>
            <ActionButton variant="text" onClick={onClose} disabled={isLoading}>
              Cancel
            </ActionButton>
            <ActionButton variant="contained" onClick={handleSubmit} loading={isLoading}>
              {isEditMode ? t("common.actions.update") : t("common.actions.create")}
            </ActionButton>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyFormDialog;
