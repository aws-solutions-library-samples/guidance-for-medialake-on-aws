import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  useTheme,
  alpha,
} from "@mui/material";
import { ConnectorResponse } from "@/api/types/api.types";

interface ConnectorEditModalProps {
  open: boolean;
  connector: ConnectorResponse;
  onClose: () => void;
  onSave: (connector: ConnectorResponse) => void;
}

const ConnectorEditModal: React.FC<ConnectorEditModalProps> = ({
  open,
  connector,
  onClose,
  onSave,
}) => {
  const theme = useTheme();
  const [editedConnector, setEditedConnector] =
    useState<ConnectorResponse>(connector);

  useEffect(() => {
    setEditedConnector(connector);
  }, [connector]);

  const handleSave = () => {
    onSave(editedConnector);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Edit Connector</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField
            label="Name"
            value={editedConnector.name}
            onChange={(e) =>
              setEditedConnector({
                ...editedConnector,
                name: e.target.value,
              })
            }
            fullWidth
          />
          <TextField
            label="Description"
            value={editedConnector.description || ""}
            onChange={(e) =>
              setEditedConnector({
                ...editedConnector,
                description: e.target.value,
              })
            }
            fullWidth
            multiline
            rows={4}
          />
          <TextField
            label="Bucket"
            value={editedConnector.storageIdentifier || ""}
            disabled
            fullWidth
          />
          {editedConnector.settings?.region && (
            <TextField
              label="Region"
              value={editedConnector.region}
              disabled
              fullWidth
            />
          )}
          {editedConnector.settings?.path && (
            <TextField
              label="Path"
              value={editedConnector.settings.path}
              onChange={(e) =>
                setEditedConnector({
                  ...editedConnector,
                  settings: {
                    ...editedConnector.settings,
                    path: e.target.value,
                  },
                })
              }
              fullWidth
            />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={onClose}
          sx={{
            color: theme.palette.text.secondary,
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.main, 0.1),
            },
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          sx={{
            backgroundColor: theme.palette.primary.main,
            "&:hover": {
              backgroundColor: theme.palette.primary.dark,
            },
          }}
        >
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConnectorEditModal;
