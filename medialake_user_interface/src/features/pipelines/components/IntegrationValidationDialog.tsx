import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
  Box,
  Alert,
} from "@mui/material";
import type { Integration } from "@/features/settings/integrations/types/integrations.types";
import type {
  InvalidNodeInfo,
  IntegrationMapping,
} from "../services/integrationValidation.service";

interface IntegrationValidationDialogProps {
  open: boolean;
  invalidNodes: InvalidNodeInfo[];
  availableIntegrations: Integration[];
  onClose: () => void;
  onConfirm: (mappings: IntegrationMapping[]) => void;
}

export const IntegrationValidationDialog: React.FC<
  IntegrationValidationDialogProps
> = ({ open, invalidNodes, availableIntegrations, onClose, onConfirm }) => {
  const [mappings, setMappings] = useState<IntegrationMapping[]>([]);
  const [isValid, setIsValid] = useState(false);

  useEffect(() => {
    // Initialize mappings with empty selections
    const initialMappings = invalidNodes.map((node) => ({
      nodeIndex: node.nodeIndex,
      oldIntegrationId: node.invalidIntegrationId,
      newIntegrationId:
        availableIntegrations.length > 0 ? availableIntegrations[0].id : "",
    }));

    setMappings(initialMappings);
    setIsValid(availableIntegrations.length > 0);
  }, [invalidNodes, availableIntegrations]);

  const handleIntegrationChange = (
    nodeIndex: number,
    integrationId: string,
  ) => {
    const updatedMappings = mappings.map((mapping) =>
      mapping.nodeIndex === nodeIndex
        ? { ...mapping, newIntegrationId: integrationId }
        : mapping,
    );

    setMappings(updatedMappings);

    // Check if all mappings have a selected integration
    const allMappingsValid = updatedMappings.every(
      (mapping) => !!mapping.newIntegrationId,
    );
    setIsValid(allMappingsValid);
  };

  const handleConfirm = () => {
    onConfirm(mappings);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Integration Validation Required</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" paragraph>
            Some nodes in the imported pipeline reference integrations that
            don't exist in this environment. Please select replacement
            integrations for each node:
          </Typography>

          {availableIntegrations.length === 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              No integrations are available in this environment. You'll need to
              create integrations before you can use these nodes.
            </Alert>
          )}
        </Box>

        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Node</TableCell>
                <TableCell>Invalid Integration ID</TableCell>
                <TableCell>Replacement Integration</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invalidNodes.map((node) => (
                <TableRow key={node.nodeId}>
                  <TableCell>{node.nodeLabel}</TableCell>
                  <TableCell>{node.invalidIntegrationId}</TableCell>
                  <TableCell>
                    <FormControl fullWidth>
                      <InputLabel>Select Integration</InputLabel>
                      <Select
                        value={
                          mappings.find((m) => m.nodeIndex === node.nodeIndex)
                            ?.newIntegrationId || ""
                        }
                        onChange={(e) =>
                          handleIntegrationChange(
                            node.nodeIndex,
                            e.target.value as string,
                          )
                        }
                        label="Select Integration"
                        disabled={availableIntegrations.length === 0}
                      >
                        {availableIntegrations.map((integration) => (
                          <MenuItem key={integration.id} value={integration.id}>
                            {integration.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          color="primary"
          variant="contained"
          disabled={!isValid}
        >
          Apply Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default IntegrationValidationDialog;
