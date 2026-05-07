import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import DensitySmallIcon from "@mui/icons-material/DensitySmall";
import DensityLargeIcon from "@mui/icons-material/DensityLarge";
import { useTableDensity } from "../../../contexts/TableDensityContext";
import { useTranslation } from "react-i18next";

export const TableDensityToggle: React.FC = () => {
  const { t } = useTranslation();
  const { mode, toggleMode } = useTableDensity();

  return (
    <Tooltip title={t("common.tableDensity", "Table Density")}>
      <IconButton
        onClick={toggleMode}
        size="small"
        aria-label={t("common.tableDensity", "Table Density")}
        sx={{
          height: "32px",
          width: "32px",
          borderRadius: "6px",
          border: "1px solid",
          borderColor: "divider",
          "& .MuiSvgIcon-root": {
            fontSize: "1.2rem",
          },
        }}
      >
        {mode === "compact" ? (
          <DensitySmallIcon fontSize="small" />
        ) : (
          <DensityLargeIcon fontSize="small" />
        )}
      </IconButton>
    </Tooltip>
  );
};
