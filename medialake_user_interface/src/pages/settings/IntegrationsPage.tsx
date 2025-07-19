import React, { useState, useMemo, useEffect } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from "@mui/material";
import ApiStatusModal from "@/components/ApiStatusModal";
import AddIcon from "@mui/icons-material/Add";
import WarningIcon from "@mui/icons-material/Warning";
import { useTranslation } from "react-i18next";
import { PageHeader, PageContent } from "@/components/common/layout";
import IntegrationList from "@/features/settings/integrations/components/IntegrationList/index";
import IntegrationForm from "@/features/settings/integrations/components/IntegrationForm/IntegrationForm";
import {
  IntegrationFilters,
  IntegrationSorting,
  IntegrationsResponse,
  Integration,
} from "@/features/settings/integrations/types/integrations.types";
import {
  IntegrationFormResult,
  IntegrationFormData,
} from "@/features/settings/integrations/components/IntegrationForm/types";
import {
  useGetIntegrations,
  useCreateIntegration,
  useUpdateIntegration,
  integrationsController,
} from "@/features/settings/integrations/api/integrations.controller";
import { IntegrationsNodesService } from "@/features/settings/integrations/services/integrations-nodes.service";
import queryClient from "@/api/queryClient";

const IntegrationsPage: React.FC = () => {
  const { t } = useTranslation();
  const [openIntegrationForm, setOpenIntegrationForm] = useState(false);
  const [editingIntegration, setEditingIntegration] =
    useState<Integration | null>(null);
  const [activeFilters, setActiveFilters] = useState<IntegrationFilters[]>([]);
  const [activeSorting, setActiveSorting] = useState<IntegrationSorting[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [integrationToDelete, setIntegrationToDelete] = useState<string | null>(
    null,
  );
  const [apiStatus, setApiStatus] = useState<{
    show: boolean;
    status: "loading" | "success" | "error";
    action: string;
    message?: string;
  }>({
    show: false,
    status: "loading",
    action: "",
  });

  // Fetch nodes using React Query
  const {
    nodes,
    isLoading: isLoadingNodes,
    error: nodesError,
  } = IntegrationsNodesService.useNodes();

  // Filter nodes to only include those with nodeType === "INTEGRATION"
  // and transform them to the expected IntegrationNode format
  const integrationNodes = useMemo(() => {
    return nodes
      .filter((node) => node.info?.nodeType === "INTEGRATION")
      .map((node) => ({
        nodeId: node.nodeId || "",
        info: {
          title: node.info?.title || "",
          description: node.info?.description || "",
        },
        auth: node.auth
          ? {
              authMethod: node.auth.authMethod as "awsIam" | "apiKey",
            }
          : undefined,
      }));
  }, [nodes]);

  // Fetch integrations using React Query
  const {
    data: integrationsData,
    isLoading: isLoadingIntegrations,
    error: integrationsError,
  } = useGetIntegrations();

  // React Query mutations for create/update
  const createIntegrationMutation = useCreateIntegration();
  const updateIntegrationMutation = useUpdateIntegration();

  // Combine loading and error states
  const isLoading = isLoadingNodes || isLoadingIntegrations;
  const error = nodesError || integrationsError;

  // Function to refresh the integrations data
  const refreshIntegrations = () => {
    // Invalidate the integrations query to trigger a refetch
    queryClient.invalidateQueries({ queryKey: ["integrations"] });
  };

  const handleAddIntegration = () => {
    setOpenIntegrationForm(true);
  };

  const handleCloseApiStatus = () => {
    console.log("Closing API status modal");
    setApiStatus((prev) => ({ ...prev, show: false }));
  };

  // Handle form submission with immediate loading state
  const handleSave = async (values: IntegrationFormData) => {
    // 1) Show loading immediately
    setApiStatus({
      show: true,
      status: "loading",
      action: editingIntegration
        ? "Updating integration…"
        : "Creating integration…",
    });

    try {
      let result;

      // 2) Do the create/update API call
      if (editingIntegration) {
        console.log("Starting integration update with data:", values);
        result = await updateIntegrationMutation.mutateAsync({
          id: editingIntegration.id,
          data: values,
        });
        console.log("Integration updated successfully:", result);
      } else {
        console.log("Starting integration creation with data:", values);
        result = await createIntegrationMutation.mutateAsync(values);
        console.log("Integration created successfully:", result);
      }

      // 3) Show success
      const displayName =
        result.data?.name ||
        values.nodeId
          .replace(/_/g, " ")
          .replace(/\b\w/g, (l) => l.toUpperCase());
      setApiStatus({
        show: true,
        status: "success",
        action: editingIntegration
          ? "Integration Updated"
          : "Integration Created",
        message: `Integration "${displayName}" saved.`,
      });

      // Close the form and refresh data
      setOpenIntegrationForm(false);
      setEditingIntegration(null);
      refreshIntegrations();
    } catch (err) {
      console.error(
        `Failed to ${editingIntegration ? "update" : "create"} integration:`,
        err,
      );
      setApiStatus({
        show: true,
        status: "error",
        action: "Save Failed",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const handleCloseIntegrationForm = () => {
    setOpenIntegrationForm(false);
    setEditingIntegration(null);
  };

  const handleEditIntegration = (id: string, integration: Integration) => {
    // Set the integration to edit and open the form
    setEditingIntegration(integration);
    setOpenIntegrationForm(true);
  };

  const handleDeleteIntegration = async (id: string) => {
    // Open the confirmation dialog and set the integration ID to delete
    setIntegrationToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteIntegration = async () => {
    if (integrationToDelete) {
      setDeleteDialogOpen(false);
      setApiStatus({
        show: true,
        status: "loading",
        action: "Deleting integration...",
      });

      try {
        await integrationsController.deleteIntegration(integrationToDelete);
        setApiStatus({
          show: true,
          status: "success",
          action: "Integration Deleted",
          message: "Integration has been successfully deleted",
        });
        setIntegrationToDelete(null);

        // Refresh the integrations data
        refreshIntegrations();
      } catch (error) {
        const errorMessage =
          error instanceof Error
            ? error.message
            : "Failed to delete integration";
        setApiStatus({
          show: true,
          status: "error",
          action: "Integration Deletion Failed",
          message: errorMessage,
        });
        console.error("Failed to delete integration:", error);
      }
    }
  };

  const cancelDeleteIntegration = () => {
    setDeleteDialogOpen(false);
    setIntegrationToDelete(null);
  };

  // Log the current apiStatus state for debugging
  console.log("Current apiStatus state:", apiStatus);

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flex: 1,
        width: "100%",
        position: "relative",
        maxWidth: "100%",
        p: 3,
      }}
    >
      <PageHeader
        title={t("integrations.title")}
        description={t("integrations.description")}
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddIntegration}
            sx={{
              borderRadius: "8px",
              textTransform: "none",
              px: 3,
              height: 40,
            }}
          >
            {t("integrations.addIntegration")}
          </Button>
        }
      />

      <PageContent isLoading={isLoading} error={error as Error}>
        <IntegrationList
          integrations={(integrationsData as IntegrationsResponse)?.data || []}
          onEditIntegration={handleEditIntegration}
          onDeleteIntegration={handleDeleteIntegration}
          activeFilters={activeFilters}
          activeSorting={activeSorting}
          onFilterChange={(columnId, value) => {
            setActiveFilters((filters) => {
              const newFilters = filters.filter((f) => f.columnId !== columnId);
              if (value) {
                newFilters.push({ id: columnId, columnId, value });
              }
              return newFilters;
            });
          }}
          onSortChange={(columnId, desc) => {
            setActiveSorting((sorts) => {
              const newSorts = sorts.filter((s) => s.columnId !== columnId);
              if (desc !== undefined) {
                newSorts.push({ id: columnId, columnId, desc });
              }
              return newSorts;
            });
          }}
          onRemoveFilter={(columnId) => {
            setActiveFilters((filters) =>
              filters.filter((f) => f.columnId !== columnId),
            );
          }}
          onRemoveSort={(columnId) => {
            setActiveSorting((sorts) =>
              sorts.filter((s) => s.columnId !== columnId),
            );
          }}
        />
      </PageContent>

      <IntegrationForm
        open={openIntegrationForm}
        onClose={handleCloseIntegrationForm}
        filteredNodes={integrationNodes}
        onSubmit={handleSave}
        editingIntegration={editingIntegration}
      />

      {/* Confirmation Dialog for Integration Deletion */}
      <Dialog
        open={deleteDialogOpen}
        onClose={cancelDeleteIntegration}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle
          id="alert-dialog-title"
          sx={{ display: "flex", alignItems: "center", gap: 1 }}
        >
          <WarningIcon color="warning" />
          {t("integrations.deleteConfirmation.title")}
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            {t("integrations.deleteConfirmation.message")}
          </DialogContentText>
          <DialogContentText
            sx={{ mt: 2, fontWeight: "bold", color: "error.main" }}
          >
            {t("integrations.deleteConfirmation.warning")}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelDeleteIntegration} color="primary">
            {t("common.cancel")}
          </Button>
          <Button
            onClick={confirmDeleteIntegration}
            color="error"
            variant="contained"
            autoFocus
          >
            {t("common.actions.delete")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Force the ApiStatusModal to be rendered */}
      <ApiStatusModal
        open={apiStatus.show}
        status={apiStatus.status}
        action={apiStatus.action}
        message={apiStatus.message}
        onClose={handleCloseApiStatus}
      />
    </Box>
  );
};

IntegrationsPage.displayName = "IntegrationsPage";

// Fix the TypeScript error by explicitly typing the component
export default React.memo(IntegrationsPage as React.FC);
