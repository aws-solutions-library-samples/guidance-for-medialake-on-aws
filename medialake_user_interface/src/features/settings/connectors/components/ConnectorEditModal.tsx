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
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const theme = useTheme();
  const [editedConnector, setEditedConnector] = useState<ConnectorResponse>(connector);

  useEffect(() => {
    setEditedConnector(connector);
  }, [connector]);

  const handleSave = () => {
    onSave(editedConnector);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{t("connectors.editConnector")}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField
            label={t("common.labels.name")}
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
            label={t("common.labels.description")}
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
            label={t("connectors.form.bucket")}
            value={editedConnector.storageIdentifier || ""}
            disabled
            fullWidth
          />
          {editedConnector.settings?.region && (
            <TextField
              label={t("connectors.form.region")}
              value={editedConnector.region}
              disabled
              fullWidth
            />
          )}
          {editedConnector.settings?.path && (
            <TextField
              label={t("connectors.form.path")}
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
          {t("common.dialogs.cancel")}
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
          {t("common.dialogs.save")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConnectorEditModal;
