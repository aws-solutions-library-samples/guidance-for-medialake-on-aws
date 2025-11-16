import React from "react";
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useTheme as useMuiTheme } from "@mui/material/styles";
import { useTheme } from "../../hooks/useTheme";
import { useSemanticMode, useDomainActions } from "../../stores/searchStore";

interface SemanticModeToggleProps {
  isVisible: boolean;
}

const SemanticModeToggle: React.FC<SemanticModeToggleProps> = ({
  isVisible,
}) => {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const semanticMode = useSemanticMode();
  const { setSemanticMode } = useDomainActions();

  const handleModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: "full" | "clip" | null,
  ) => {
    if (newMode !== null) {
      setSemanticMode(newMode);
    }
  };

  if (!isVisible) {
    return null;
  }

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 1,
        py: 0.5,
        borderRadius: "16px",
        backgroundColor:
          theme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.02)",
        border: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)"}`,
      }}
    >
      <Typography
        variant="caption"
        sx={{
          color: theme === "dark" ? "rgba(255,255,255,0.7)" : "text.secondary",
          fontSize: "0.75rem",
          fontWeight: 500,
        }}
      >
        Mode:
      </Typography>
      <ToggleButtonGroup
        value={semanticMode}
        exclusive
        onChange={handleModeChange}
        size="small"
        sx={{
          "& .MuiToggleButton-root": {
            px: 1.5,
            py: 0.25,
            fontSize: "0.75rem",
            fontWeight: 500,
            textTransform: "none",
            border: "none",
            borderRadius: "12px !important",
            color:
              theme === "dark" ? "rgba(255,255,255,0.6)" : "text.secondary",
            backgroundColor: "transparent",
            "&:hover": {
              backgroundColor:
                theme === "dark"
                  ? "rgba(255,255,255,0.08)"
                  : "rgba(0,0,0,0.04)",
            },
            "&.Mui-selected": {
              backgroundColor: muiTheme.palette.primary.main,
              color: muiTheme.palette.primary.contrastText,
              "&:hover": {
                backgroundColor: muiTheme.palette.primary.dark,
              },
            },
          },
        }}
      >
        <ToggleButton value="full">Full</ToggleButton>
        <ToggleButton value="clip">Clip</ToggleButton>
      </ToggleButtonGroup>
    </Box>
  );
};

export default SemanticModeToggle;
