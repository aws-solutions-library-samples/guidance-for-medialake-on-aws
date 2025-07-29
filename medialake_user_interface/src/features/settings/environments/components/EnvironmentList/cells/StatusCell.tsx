import React from "react";
import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface StatusCellProps {
  status: "active" | "disabled";
}

export const StatusCell: React.FC<StatusCellProps> = ({ status }) => {
  const { t } = useTranslation();

  return (
    <Chip
      label={t(`settings.environments.status.${status}`)}
      color={status === "active" ? "success" : "default"}
      size="small"
      sx={{
        fontWeight: 500,
        textTransform: "capitalize",
      }}
    />
  );
};
