import React, { useState } from "react";
import { IconButton, Menu, MenuItem } from "@mui/material";
import { MoreVert as MoreVertIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { Environment } from "@/features/settings/environments/types/environments.types";
import { useDeleteEnvironment } from "@/features/settings/environments/api/environmentsController";
import { useSnackbar } from "notistack";

interface ActionsCellProps {
  environment: Environment;
  onEdit: (environment: Environment) => void;
}

export const ActionsCell: React.FC<ActionsCellProps> = ({
  environment,
  onEdit,
}) => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const deleteEnvironment = useDeleteEnvironment();

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleEdit = () => {
    onEdit(environment);
    handleClose();
  };

  const handleDelete = async () => {
    try {
      await deleteEnvironment.mutateAsync(environment.environment_id);
      enqueueSnackbar(t("settings.environments.deleteSuccess"), {
        variant: "success",
      });
    } catch (error) {
      enqueueSnackbar(
        error instanceof Error
          ? error.message
          : t("settings.environments.deleteError"),
        { variant: "error" },
      );
    }
    handleClose();
  };

  return (
    <>
      <IconButton
        onClick={handleClick}
        size="small"
        aria-label={t("common.actions")}
        aria-controls={open ? "environment-actions-menu" : undefined}
        aria-haspopup="true"
        aria-expanded={open ? "true" : undefined}
      >
        <MoreVertIcon />
      </IconButton>
      <Menu
        id="environment-actions-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          "aria-labelledby": "environment-actions-button",
        }}
      >
        <MenuItem onClick={handleEdit}>
          {t("settings.environments.actions.edit")}
        </MenuItem>
        <MenuItem onClick={handleDelete}>
          {t("settings.environments.actions.delete")}
        </MenuItem>
      </Menu>
    </>
  );
};
