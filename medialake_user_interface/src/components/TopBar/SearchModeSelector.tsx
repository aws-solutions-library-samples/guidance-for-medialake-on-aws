import React, { useState, useRef, useEffect } from "react";
import { Box, IconButton, Tooltip, Popper, ClickAwayListener, Fade } from "@mui/material";
import { useTheme as useMuiTheme, alpha } from "@mui/material/styles";
import {
  Visibility as VisualIcon,
  VolumeUp as AudioIcon,
  Description as TranscriptIcon,
  Check as CheckIcon,
  TuneRounded as TuneIcon,
} from "@mui/icons-material";
import { useTheme } from "../../hooks/useTheme";
import { useSearchModes, useDomainActions } from "../../stores/searchStore";
import type { SearchMode } from "../../stores/searchStore";

interface SearchModeSelectorProps {
  isVisible: boolean;
}

const MODES: { key: SearchMode; label: string; icon: React.ReactNode; tooltip: string }[] = [
  {
    key: "visual",
    label: "Visual",
    icon: <VisualIcon sx={{ fontSize: 16 }} />,
    tooltip: "Search by visual content (video frames, images)",
  },
  {
    key: "audio",
    label: "Audio",
    icon: <AudioIcon sx={{ fontSize: 16 }} />,
    tooltip: "Search by audio content",
  },
  {
    key: "transcript",
    label: "Transcript",
    icon: <TranscriptIcon sx={{ fontSize: 16 }} />,
    tooltip: "Search by speech transcription",
  },
];

const SearchModeSelector: React.FC<SearchModeSelectorProps> = ({ isVisible }) => {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const searchModes = useSearchModes();
  const { toggleSearchMode } = useDomainActions();
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);

  const isDark = theme === "dark";
  const activeCount = searchModes.length;
  const allSelected = activeCount === MODES.length;

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    if (open) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  if (!isVisible) return null;

  return (
    <>
      <Tooltip
        title={`Search modes: ${searchModes.join(", ")}`}
        arrow
        placement="bottom"
        enterDelay={400}
      >
        <IconButton
          ref={anchorRef}
          size="small"
          onClick={() => setOpen((prev) => !prev)}
          sx={{
            padding: "5px",
            flexShrink: 0,
            position: "relative",
            color: open
              ? muiTheme.palette.primary.main
              : alpha(muiTheme.palette.text.secondary, 0.7),
            "&:hover": {
              backgroundColor: alpha(muiTheme.palette.action.active, 0.06),
              color: muiTheme.palette.text.secondary,
            },
          }}
          aria-label="Select search modes"
          aria-haspopup="true"
          aria-expanded={open}
        >
          <TuneIcon sx={{ fontSize: 20 }} />
          {/* Badge showing count when not all selected */}
          {!allSelected && (
            <Box
              sx={{
                position: "absolute",
                top: -2,
                right: -2,
                backgroundColor: muiTheme.palette.primary.main,
                color: muiTheme.palette.primary.contrastText,
                borderRadius: "50%",
                width: 14,
                height: 14,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.55rem",
                fontWeight: 700,
                lineHeight: 1,
                border: `2px solid ${muiTheme.palette.background.paper}`,
                boxSizing: "content-box",
              }}
            >
              {activeCount}
            </Box>
          )}
        </IconButton>
      </Tooltip>

      <Popper
        open={open}
        anchorEl={anchorRef.current}
        placement="bottom-end"
        transition
        sx={{ zIndex: muiTheme.zIndex.modal + 1 }}
      >
        {({ TransitionProps }) => (
          <Fade {...TransitionProps} timeout={150}>
            <Box>
              <ClickAwayListener onClickAway={() => setOpen(false)}>
                <Box
                  sx={{
                    mt: 1,
                    borderRadius: "12px",
                    overflow: "hidden",
                    backgroundColor: muiTheme.palette.background.paper,
                    border: `1px solid ${alpha(muiTheme.palette.divider, isDark ? 0.1 : 0.08)}`,
                    boxShadow: `0 8px 24px ${alpha(
                      muiTheme.palette.common.black,
                      isDark ? 0.5 : 0.12
                    )}`,
                    minWidth: 200,
                  }}
                >
                  {/* Header */}
                  <Box
                    sx={{
                      px: 1.5,
                      py: 1,
                      borderBottom: `1px solid ${alpha(muiTheme.palette.divider, 0.08)}`,
                    }}
                  >
                    <Box
                      component="span"
                      sx={{
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: alpha(muiTheme.palette.text.secondary, 0.6),
                      }}
                    >
                      Search by
                    </Box>
                  </Box>

                  {/* Options */}
                  {MODES.map((mode) => {
                    const isSelected = searchModes.includes(mode.key);
                    return (
                      <Tooltip
                        key={mode.key}
                        title={mode.tooltip}
                        placement="left"
                        enterDelay={600}
                        arrow
                      >
                        <Box
                          component="button"
                          role="checkbox"
                          aria-checked={isSelected}
                          onClick={() => toggleSearchMode(mode.key)}
                          sx={{
                            all: "unset",
                            boxSizing: "border-box",
                            display: "flex",
                            alignItems: "center",
                            gap: 1.25,
                            width: "100%",
                            px: 1.5,
                            py: 1,
                            cursor: "pointer",
                            transition: "background-color 0.1s",
                            backgroundColor: "transparent",
                            "&:hover": {
                              backgroundColor: alpha(
                                muiTheme.palette.action.active,
                                isDark ? 0.05 : 0.03
                              ),
                            },
                            "&:focus-visible": {
                              outline: `2px solid ${muiTheme.palette.primary.main}`,
                              outlineOffset: "-2px",
                            },
                          }}
                        >
                          {/* Icon */}
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              width: 28,
                              height: 28,
                              borderRadius: "8px",
                              backgroundColor: isSelected
                                ? alpha(muiTheme.palette.primary.main, isDark ? 0.2 : 0.1)
                                : alpha(muiTheme.palette.action.active, isDark ? 0.06 : 0.04),
                              color: isSelected
                                ? muiTheme.palette.primary.main
                                : alpha(muiTheme.palette.text.secondary, 0.6),
                              transition: "background-color 0.15s, color 0.15s",
                            }}
                          >
                            {mode.icon}
                          </Box>

                          {/* Label */}
                          <Box
                            component="span"
                            sx={{
                              flex: 1,
                              fontSize: "13px",
                              fontWeight: isSelected ? 600 : 400,
                              color: isSelected
                                ? isDark
                                  ? "#fff"
                                  : muiTheme.palette.text.primary
                                : muiTheme.palette.text.secondary,
                              transition: "color 0.15s",
                            }}
                          >
                            {mode.label}
                          </Box>

                          {/* Checkmark */}
                          <Box
                            sx={{
                              width: 18,
                              height: 18,
                              borderRadius: "5px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              backgroundColor: isSelected
                                ? muiTheme.palette.primary.main
                                : "transparent",
                              border: isSelected
                                ? "none"
                                : `1.5px solid ${alpha(muiTheme.palette.divider, 0.2)}`,
                              transition: "background-color 0.15s, border-color 0.15s",
                            }}
                          >
                            {isSelected && (
                              <CheckIcon
                                sx={{ fontSize: 13, color: muiTheme.palette.primary.contrastText }}
                              />
                            )}
                          </Box>
                        </Box>
                      </Tooltip>
                    );
                  })}

                  {/* Footer hint */}
                  <Box
                    sx={{
                      px: 1.5,
                      py: 0.75,
                      borderTop: `1px solid ${alpha(muiTheme.palette.divider, 0.08)}`,
                    }}
                  >
                    <Box
                      component="span"
                      sx={{
                        fontSize: "10.5px",
                        color: alpha(muiTheme.palette.text.secondary, 0.5),
                        lineHeight: 1.4,
                      }}
                    >
                      Select multiple to search across modes
                    </Box>
                  </Box>
                </Box>
              </ClickAwayListener>
            </Box>
          </Fade>
        )}
      </Popper>
    </>
  );
};

export default SearchModeSelector;
