import React, { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Popover,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  Bookmark as SavedIcon,
  BookmarkBorder as SaveIcon,
  DeleteOutline as DeleteIcon,
  Edit as RenameIcon,
} from "@mui/icons-material";
import { isBlankDefinition, suggestSearchName, type SearchDefinition } from "../searchDefinition";
import { useMatchingSavedSearch } from "../hooks";
import { useCreateSavedSearch, useDeleteSavedSearch, useRenameSavedSearch } from "../api";

const MAX_NAME_LENGTH = 100;

interface SaveSearchButtonProps {
  /** The search currently on screen. */
  definition: SearchDefinition;
}

/**
 * "Save search" on the results page. Once the current search is saved it
 * turns into "Saved", with rename and remove in a menu.
 *
 * Hidden for a browse-everything search with no filters, which there is no
 * point saving. Shown for zero-result searches: a saved search is also a way
 * to check back later for new matches.
 */
export const SaveSearchButton: React.FC<SaveSearchButtonProps> = ({ definition }) => {
  const { t } = useTranslation();
  const titleId = useId();
  const { match, isReady } = useMatchingSavedSearch(definition);
  const create = useCreateSavedSearch();
  const rename = useRenameSavedSearch();
  const remove = useDeleteSavedSearch();

  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [mode, setMode] = useState<"save" | "rename" | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [name, setName] = useState("");

  if (isBlankDefinition(definition)) return null;

  const openEditor = (target: HTMLElement, nextMode: "save" | "rename") => {
    setName(
      nextMode === "rename" && match
        ? match.name
        : suggestSearchName(definition, t, t("search.saved.untitled", "Untitled search"))
    );
    setMode(nextMode);
    setAnchor(target);
  };

  const closeEditor = () => {
    setAnchor(null);
    setMode(null);
  };

  const trimmed = name.trim();
  const nameError =
    trimmed.length > MAX_NAME_LENGTH
      ? t("search.saved.nameTooLong", "Use at most {{max}} characters", { max: MAX_NAME_LENGTH })
      : null;
  const canSubmit = !!trimmed && !nameError && !create.isPending && !rename.isPending;

  const submit = () => {
    if (!canSubmit) return;
    if (mode === "rename" && match) {
      rename.mutate({ id: match.id, name: trimmed }, { onSuccess: closeEditor });
    } else {
      create.mutate({ name: trimmed, definition }, { onSuccess: closeEditor });
    }
  };

  return (
    <Box>
      {match ? (
        <Button
          variant="contained"
          color="primary"
          size="small"
          startIcon={<SavedIcon />}
          onClick={(e) => setMenuAnchor(e.currentTarget)}
          aria-haspopup="menu"
          aria-label={t("search.saved.savedAs", "Saved as “{{name}}”", { name: match.name })}
        >
          {t("search.saved.savedButton", "Saved")}
        </Button>
      ) : (
        <Button
          variant="outlined"
          size="small"
          startIcon={<SaveIcon />}
          onClick={(e) => openEditor(e.currentTarget, "save")}
          disabled={!isReady}
        >
          {t("search.saved.saveButton", "Save search")}
        </Button>
      )}

      <Menu anchorEl={menuAnchor} open={!!menuAnchor} onClose={() => setMenuAnchor(null)}>
        <MenuItem
          onClick={() => {
            const target = menuAnchor;
            setMenuAnchor(null);
            if (target) openEditor(target, "rename");
          }}
        >
          <ListItemIcon>
            <RenameIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t("search.saved.rename", "Rename")}</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            setMenuAnchor(null);
            if (match) remove.mutate(match.id);
          }}
        >
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t("search.saved.remove", "Remove from saved searches")}</ListItemText>
        </MenuItem>
      </Menu>

      <Popover
        open={!!anchor}
        anchorEl={anchor}
        onClose={closeEditor}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { role: "dialog", "aria-labelledby": titleId } as object }}
      >
        <Box
          component="form"
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault();
            submit();
          }}
          sx={{ p: 2, width: 340 }}
        >
          <Typography id={titleId} variant="subtitle1" sx={{ mb: 1.5, fontWeight: 600 }}>
            {mode === "rename"
              ? t("search.saved.renameTitle", "Rename saved search")
              : t("search.saved.saveTitle", "Save this search")}
          </Typography>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label={t("search.saved.nameLabel", "Name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={!!nameError}
            helperText={
              nameError ??
              t(
                "search.saved.nameHelp",
                "Saved searches keep the query, semantic options and filters."
              )
            }
            onFocus={(e) => e.target.select()}
          />
          <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 2 }}>
            <Button onClick={closeEditor} size="small">
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" variant="contained" size="small" disabled={!canSubmit}>
              {t("common.save", "Save")}
            </Button>
          </Stack>
        </Box>
      </Popover>
    </Box>
  );
};

export default SaveSearchButton;
