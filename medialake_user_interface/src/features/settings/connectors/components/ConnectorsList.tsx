import { Suspense } from "react";
import { Box, CircularProgress, Typography, Grid, Button } from "@mui/material";
import {
  useGetConnectors,
  useDeleteConnector,
  useToggleConnector,
  useSyncConnector,
} from "@/api/hooks/useConnectors";
import {
  ConnectorResponse,
  ConnectorListResponse,
} from "@/api/types/api.types";
import ConnectorCard from "./ConnectorCard";
import { UseQueryResult } from "@tanstack/react-query";

interface ConnectorsListProps {
  onAddConnector: () => void;
}

export const ConnectorsList: React.FC<ConnectorsListProps> = ({
  onAddConnector,
}) => {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <ConnectorsListContent onAddConnector={onAddConnector} />
    </Suspense>
  );
};

const LoadingSpinner = () => (
  <Box
    display="flex"
    justifyContent="center"
    alignItems="center"
    minHeight="200px"
  >
    <CircularProgress />
  </Box>
);

interface ConnectorsListContentProps {
  onAddConnector: () => void;
}

const ConnectorsListContent: React.FC<ConnectorsListContentProps> = ({
  onAddConnector,
}) => {
  const {
    data: connectorsData,
    isLoading,
    error,
  }: UseQueryResult<ConnectorListResponse, Error> = useGetConnectors();

  const deleteConnector = useDeleteConnector();
  const toggleConnector = useToggleConnector();
  const syncConnector = useSyncConnector();

  const handleEdit = (connector: ConnectorResponse) => {
    // TODO: Implement edit functionality
    console.log("Edit connector:", connector);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConnector.mutateAsync(id);
    } catch (error) {
      console.error("Failed to delete connector:", error);
    }
  };

  const handleToggleStatus = async (id: string, enabled: boolean) => {
    try {
      await toggleConnector.mutateAsync({ id, enabled });
    } catch (error) {
      console.error("Failed to toggle connector status:", error);
    }
  };

  const handleSync = async (id: string) => {
    try {
      await syncConnector.mutateAsync(id);
    } catch (error) {
      console.error("Failed to sync connector:", error);
    }
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <Box p={3}>
        <Typography color="error">
          Error loading connectors: {error.message}
        </Typography>
      </Box>
    );
  }

  const connectors = connectorsData?.data?.connectors || [];

  return (
    <Box p={3}>
      <Box display="flex" justifyContent="flex-end" mb={2}>
        <Button variant="contained" color="primary" onClick={onAddConnector}>
          Add Connector
        </Button>
      </Box>
      {connectors.length === 0 ? (
        <Typography>No connectors found.</Typography>
      ) : (
        <Grid container spacing={3}>
          {connectors.map((connector) => (
            <Grid item xs={12} sm={6} md={4} key={connector.id}>
              <ConnectorCard
                connector={connector}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onToggleStatus={handleToggleStatus}
                onSync={handleSync}
              />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};
