import React from "react";
import { useTranslation } from "react-i18next";
import { Box, Tooltip } from "@mui/material";
import { useTheme as useMuiTheme } from "@mui/material/styles";
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
        backgroundColor: isDark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.05)",
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
                transition: "all 0.15s ease",
                backgroundColor: isSelected
                  ? isDark
                    ? "rgba(255,255,255,0.14)"
                    : "#fff"
                  : "transparent",
                color: isSelected
                  ? isDark
                    ? "#fff"
                    : muiTheme.palette.text.primary
                  : isDark
                    ? "rgba(255,255,255,0.45)"
                    : "rgba(0,0,0,0.42)",
                boxShadow: isSelected
                  ? isDark
                    ? "0 1px 2px rgba(0,0,0,0.3)"
                    : "0 1px 2px rgba(0,0,0,0.1), 0 0 0 1px rgba(0,0,0,0.06)"
                  : "none",
                "&:hover": {
                  color: isSelected
                    ? undefined
                    : isDark
                      ? "rgba(255,255,255,0.65)"
                      : "rgba(0,0,0,0.6)",
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
