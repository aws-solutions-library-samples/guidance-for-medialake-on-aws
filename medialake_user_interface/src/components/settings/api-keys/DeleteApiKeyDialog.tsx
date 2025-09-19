import React from "react";
import { ConfirmationModal } from "@/components/common/ConfirmationModal";
import { useDeleteApiKey } from "@/api/hooks/useApiKeys";
import { ApiKey } from "@/api/types/apiKey.types";

interface DeleteApiKeyDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  apiKey: ApiKey | null;
}

const DeleteApiKeyDialog: React.FC<DeleteApiKeyDialogProps> = ({
  open,
  onClose,
  onSuccess,
  apiKey,
}) => {
  const deleteMutation = useDeleteApiKey();

  const handleConfirm = async () => {
    if (!apiKey) return;

    try {
      await deleteMutation.mutateAsync(apiKey.id);
      onSuccess();
    } catch (error) {
      console.error("Failed to delete API key:", error);
      // Error handling is managed by the mutation hook and parent component
      onClose();
    }
  };

  return (
    <ConfirmationModal
      open={open}
      title="Delete API Key"
      message={
        apiKey
          ? `Are you sure you want to delete the API key "${apiKey.name}"? This action cannot be undone and will immediately invalidate any applications using this key.`
          : "Are you sure you want to delete this API key?"
      }
      onConfirm={handleConfirm}
      onCancel={onClose}
      confirmText="Delete"
      cancelText="Cancel"
      isLoading={deleteMutation.isPending}
    />
  );
};

export default DeleteApiKeyDialog;
