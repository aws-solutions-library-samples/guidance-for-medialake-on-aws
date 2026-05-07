import React from "react";
import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface StatusCellProps {
  value: string;
}

export const StatusCell: React.FC<StatusCellProps> = ({ value }) => {
  const { t } = useTranslation();

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "active":
        return "success";
      case "error":
        return "error";
      default:
        return "warning";
    }
  };

  // Translate status values using common.status keys
  const getTranslatedStatus = (status: string) => {
    const statusLower = status.toLowerCase();
    const translationKey = `common.status.${statusLower}`;

    // Try to get translation, fallback to uppercase raw value if not found
    const translated = t(translationKey);
    return translated !== translationKey ? translated.toUpperCase() : status.toUpperCase();
  };

  return (
    <Chip label={getTranslatedStatus(value)} color={getStatusColor(value) as any} size="small" />
  );
};
