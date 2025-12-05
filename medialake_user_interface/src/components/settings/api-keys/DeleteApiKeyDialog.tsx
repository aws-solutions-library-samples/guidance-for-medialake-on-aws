import React from "react";
import { ConfirmationModal } from "@/components/common/ConfirmationModal";
import { useDeleteApiKey } from "@/api/hooks/useApiKeys";
import { ApiKey } from "@/api/types/apiKey.types";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
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
      title={t("common.deleteApiKey")}
      message={
        apiKey
          ? t("common.deleteApiKeyConfirmation", { name: apiKey.name })
          : t("common.deleteApiKeyConfirmationGeneric")
      }
      onConfirm={handleConfirm}
      onCancel={onClose}
      confirmText={t("common.delete")}
      cancelText={t("common.dialogs.cancel")}
      isLoading={deleteMutation.isPending}
    />
  );
};

export default DeleteApiKeyDialog;
