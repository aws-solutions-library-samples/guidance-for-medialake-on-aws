import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Box, Snackbar, Alert } from "@mui/material";
import { Add as AddIcon } from "@mui/icons-material";
import ConnectorCard from "@/features/settings/connectors/components/ConnectorCard";
import ConnectorModal from "@/features/settings/connectors/components/ConnectorModal";
import { PageHeader, PageContent } from "@/components/common/layout";
import {
  useGetConnectors,
  useDeleteConnector,
  useToggleConnector,
  useCreateS3Connector,
  useSyncConnector,
} from "@/api/hooks/useConnectors";
import { ConnectorResponse, CreateConnectorRequest } from "@/api/types/api.types";
import queryClient from "@/api/queryClient";

const ConnectorsPage: React.FC = () => {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingConnector, setEditingConnector] = useState<ConnectorResponse | undefined>();
  const [alert, setAlert] = useState<{
    message: string;
    severity: "success" | "error";
  } | null>(null);

  const {
    data: connectorsResponse,
    isLoading,
    // isError,
    error,
  } = useGetConnectors();

  const { mutateAsync: deleteConnector } = useDeleteConnector();
  const { mutateAsync: toggleConnector } = useToggleConnector();
  const { mutateAsync: syncConnector } = useSyncConnector();
  const { mutateAsync: createS3Connector, isPending: isCreatingConnector } = useCreateS3Connector();

  // Safely pull out the connectors array
  const rawConnectors = connectorsResponse?.data?.connectors;
  const connectors = Array.isArray(rawConnectors) ? rawConnectors.filter(Boolean) : [];

  const handleAddClick = () => {
    setEditingConnector(undefined);
    setIsModalOpen(true);
  };

  const handleEditClick = (connector: ConnectorResponse) => {
    setEditingConnector(connector);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setEditingConnector(undefined);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConnector(id);
      await queryClient.invalidateQueries({ queryKey: ["connectors"] });
      setAlert({
        message: t("common.messages.connectorDeletedSuccessfully"),
        severity: "success",
      });
    } catch (error) {
      setAlert({
        message: t("connectors.apiMessages.deleting.error"),
        severity: "error",
      });
    }
  };

  const handleToggleStatus = async (id: string, enabled: boolean) => {
    try {
      await toggleConnector({ id, enabled });
      await queryClient.invalidateQueries({ queryKey: ["connectors"] });
      setAlert({
        message: `Connector ${enabled ? "enabled" : "disabled"} successfully`,
        severity: "success",
      });
    } catch (error) {
      setAlert({
        message: `Failed to ${enabled ? "enable" : "disable"} connector`,
        severity: "error",
      });
    }
  };

  const handleSync = async (id: string) => {
    try {
      await syncConnector(id);
      setAlert({
        message: t("common.messages.connectorSyncInitiated"),
        severity: "success",
      });
    } catch (error) {
      setAlert({
        message: t("common.messages.failedToSyncConnector"),
        severity: "error",
      });
    }
  };

  const handleSave = async (connectorData: CreateConnectorRequest): Promise<void> => {
    try {
      if (connectorData.type === "s3") {
        const response = await createS3Connector(connectorData);

        // console.log('API Response:', response);

        if (Number(response.status) >= 400) {
          throw new Error(response.message || "Failed to create connector");
        }

        handleModalClose();
        setAlert({
          message: t("common.messages.connectorCreatedSuccessfully"),
          severity: "success",
        });

        // Re-fetch connectors so new one appears immediately
        await queryClient.invalidateQueries({ queryKey: ["connectors"] });
      }
    } catch (error: any) {
      // console.error('Error creating connector:', error);

      let errorMessage = "Failed to create connector";

      if (error.message) {
        errorMessage = error.message;
      } else if (error.response?.data?.body?.message) {
        errorMessage = error.response.data.body.message;
      }

      setAlert({
        message: errorMessage,
        severity: "error",
      });
    }
  };

  const handleAlertClose = () => {
    setAlert(null);
  };

  return (
    <Box sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title={t("connectors.title")}
        description={t("connectors.description")}
        action={
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleAddClick}>
            {t("connectors.addConnector")}
          </Button>
        }
      />

      <PageContent isLoading={isLoading} error={error as Error}>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(auto-fill, minmax(300px, 1fr))",
              md: "repeat(auto-fill, minmax(350px, 1fr))",
            },
            gap: 3,
          }}
        >
          {connectors.map((connector, index) => {
            if (!connector) return null;

            return (
              <Box key={connector.id ?? index}>
                <ConnectorCard
                  connector={connector}
                  onEdit={handleEditClick}
                  onDelete={handleDelete}
                  onToggleStatus={handleToggleStatus}
                  onSync={handleSync}
                />
              </Box>
            );
          })}
        </Box>
      </PageContent>

      <ConnectorModal
        open={isModalOpen}
        onClose={handleModalClose}
        editingConnector={editingConnector}
        onSave={handleSave}
        isCreating={isCreatingConnector}
      />

      <Snackbar
        open={!!alert}
        autoHideDuration={6000}
        onClose={handleAlertClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert onClose={handleAlertClose} severity={alert?.severity} sx={{ width: "100%" }}>
          {alert?.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ConnectorsPage;
