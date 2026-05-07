import React, { useState, useEffect } from "react";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import type { ConflictResolutionResult } from "../types/portal.types";

interface Props {
  open: boolean;
  conflictingFilenames: string[];
  onResolve: (result: ConflictResolutionResult) => void;
  onClose: () => void;
}

const ConflictResolutionDialog: React.FC<Props> = ({
  open,
  conflictingFilenames,
  onResolve,
  onClose,
}) => {
  const [applyToAll, setApplyToAll] = useState(true);

  useEffect(() => {
    if (open) setApplyToAll(true);
  }, [open]);

  const { t } = useTranslation();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{t("uploadPortals.conflicts.duplicateFilesDetected")}</DialogTitle>
      <DialogContent>
        <List dense sx={{ maxHeight: 200, overflow: "auto" }}>
          {conflictingFilenames.map((name) => (
            <ListItem key={name}>
              <ListItemText primary={name} />
            </ListItem>
          ))}
        </List>
        <FormControlLabel
          control={
            <Checkbox checked={applyToAll} onChange={(e) => setApplyToAll(e.target.checked)} />
          }
          label={t("uploadPortals.conflicts.applyToAllConflicts")}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => onResolve({ action: "skip", applyToAll })}>
          {t("uploadPortals.conflicts.skipConflictingFiles")}
        </Button>
        <Button variant="contained" onClick={() => onResolve({ action: "overwrite", applyToAll })}>
          {t("uploadPortals.conflicts.overwriteExistingFiles")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConflictResolutionDialog;
