import React from "react";
import { useTranslation } from "react-i18next";
import { Box, Tooltip } from "@mui/material";
import { useTheme as useMuiTheme, alpha } from "@mui/material/styles";
import { useTheme } from "../../hooks/useTheme";
import { useSemanticMode, useDomainActions } from "../../stores/searchStore";

interface SemanticModeToggleProps {
  isVisible: boolean;
}

/**
 * Compact segmented control matching Mantine SegmentedControl size="xs" radius="xl".
 * Renders Full / Clip toggle inside the search pill when semantic search is active.
 */
const SemanticModeToggle: React.FC<SemanticModeToggleProps> = ({ isVisible }) => {
  const { t } = useTranslation();
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const semanticMode = useSemanticMode();
  const { setSemanticMode } = useDomainActions();

  if (!isVisible) return null;

  const isDark = theme === "dark";

  const tooltips: Record<"full" | "clip", string> = {
    full: t("search.mode.fullTooltip", "Group all matches under each asset"),
    clip: t("search.mode.clipTooltip", "Show each match as a separate result"),
  };

  return (
    <Box
      role="radiogroup"
      aria-label="Search mode"
      sx={{
        display: "flex",
        alignItems: "center",
        borderRadius: "9999px",
        backgroundColor: alpha(muiTheme.palette.action.active, isDark ? 0.07 : 0.05),
        padding: "2px",
        flexShrink: 0,
      }}
    >
      {(["full", "clip"] as const).map((mode) => {
        const isSelected = semanticMode === mode;
        return (
          <Tooltip key={mode} title={tooltips[mode]} arrow placement="bottom" enterDelay={400}>
            <Box
              component="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => setSemanticMode(mode)}
              sx={{
                all: "unset",
                boxSizing: "border-box",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                px: 1.2,
                py: "3px",
                fontSize: "12px",
                fontWeight: 600,
                lineHeight: 1,
                borderRadius: "9999px",
                textTransform: "capitalize",
                transition: "background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease",
                backgroundColor: isSelected
                  ? isDark
                    ? alpha(muiTheme.palette.common.white, 0.14)
                    : muiTheme.palette.background.paper
                  : "transparent",
                color: isSelected
                  ? muiTheme.palette.text.primary
                  : alpha(muiTheme.palette.text.secondary, 0.7),
                boxShadow: isSelected
                  ? `0 1px 2px ${alpha(muiTheme.palette.common.black, isDark ? 0.3 : 0.1)}${
                      isDark ? "" : `, 0 0 0 1px ${alpha(muiTheme.palette.common.black, 0.06)}`
                    }`
                  : "none",
                "&:hover": {
                  color: isSelected ? undefined : muiTheme.palette.text.secondary,
                },
                "&:focus-visible": {
                  outline: `2px solid ${muiTheme.palette.primary.main}`,
                  outlineOffset: "1px",
                },
              }}
            >
              {t(`common.${mode}`)}
            </Box>
          </Tooltip>
        );
      })}
    </Box>
  );
};

export default SemanticModeToggle;
