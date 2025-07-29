import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  CircularProgress,
  Alert,
  Typography,
  Box,
  useTheme,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { Node, NodesError } from "@/shared/nodes/types/nodes.types";

interface SelectNodeModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (nodeId: string) => void;
  nodes: Node[];
  isLoading: boolean;
  error: NodesError | null;
}

const SelectNodeModal: React.FC<SelectNodeModalProps> = ({
  open,
  onClose,
  onSelect,
  nodes,
  isLoading,
  error,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: "12px",
        },
      }}
    >
      <DialogTitle
        sx={{
          borderBottom: `1px solid ${theme.palette.divider}`,
          pb: 2,
        }}
      >
        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
          {t("integrations.selectNode.title")}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {t("integrations.selectNode.description")}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ p: 0 }}>
        {isLoading ? (
          <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error" sx={{ m: 2 }}>
            {error.message}
          </Alert>
        ) : nodes.length === 0 ? (
          <Box sx={{ p: 3, textAlign: "center" }}>
            <Typography color="text.secondary">
              {t("integrations.selectNode.noNodes")}
            </Typography>
          </Box>
        ) : (
          <List sx={{ pt: 0 }}>
            {nodes
              .filter((node) => node.info?.enabled)
              .map((node) => (
                <ListItem key={node.info.title} disablePadding>
                  <ListItemButton
                    onClick={() => onSelect(node.nodeId || node.info.title)}
                    sx={{
                      py: 2,
                      borderBottom: `1px solid ${theme.palette.divider}`,
                      "&:hover": {
                        backgroundColor: theme.palette.action.hover,
                      },
                    }}
                  >
                    <ListItemText
                      primary={
                        <Typography
                          variant="subtitle1"
                          sx={{ fontWeight: 500 }}
                        >
                          {node.info.title}
                        </Typography>
                      }
                      secondary={
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mt: 0.5 }}
                        >
                          {node.info.description}
                        </Typography>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
          </List>
        )}
      </DialogContent>
      <DialogActions
        sx={{
          borderTop: `1px solid ${theme.palette.divider}`,
          p: 2,
        }}
      >
        <Button
          onClick={onClose}
          sx={{
            textTransform: "none",
            fontWeight: 500,
          }}
        >
          {t("common.cancel")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SelectNodeModal;
