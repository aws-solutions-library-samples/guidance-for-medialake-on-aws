import React from "react";
import { Box, InputBase, useTheme, alpha } from "@mui/material";
import { Search as SearchIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";

interface SearchFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export const SearchField: React.FC<SearchFieldProps> = ({
  value,
  onChange,
  placeholder,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        backgroundColor:
          theme.palette.mode === "dark"
            ? alpha(theme.palette.common.white, 0.1)
            : alpha(theme.palette.common.black, 0.04),
        borderRadius: "8px",
        padding: "8px 12px",
        height: "40px", // Match button height
        minWidth: "300px",
      }}
    >
      <SearchIcon
        sx={{
          color:
            theme.palette.mode === "dark"
              ? alpha(theme.palette.common.white, 0.7)
              : theme.palette.text.secondary,
          mr: 1,
        }}
      />
      <InputBase
        placeholder={placeholder || t("common.search")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        fullWidth
        sx={{
          fontSize: "14px",
          color:
            theme.palette.mode === "dark"
              ? theme.palette.common.white
              : theme.palette.text.primary,
          "& input": {
            padding: "0",
            "&::placeholder": {
              color:
                theme.palette.mode === "dark"
                  ? alpha(theme.palette.common.white, 0.7)
                  : "inherit",
              opacity: 1,
            },
          },
        }}
      />
    </Box>
  );
};
