/**
 * AssetCardSelection — checkbox overlay for bulk selection (top-left of thumbnail).
 */
import React from "react";
import { Box, Checkbox } from "@mui/material";
import { alpha } from "@mui/material/styles";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import CheckBoxIcon from "@mui/icons-material/CheckBox";

interface AssetCardSelectionProps {
  id: string;
  isSelected: boolean;
  visible: boolean;
  onSelectToggle?: (id: string, event: React.MouseEvent<HTMLElement>) => void;
}

const AssetCardSelection: React.FC<AssetCardSelectionProps> = React.memo(
  ({ id, isSelected, visible, onSelectToggle }) => (
    <Box
      sx={{
        position: "absolute",
        top: 12,
        left: 12,
        zIndex: 10,
        opacity: visible || isSelected ? 1 : 0,
        transition: "opacity 0.2s ease-in-out",
        pointerEvents: visible || isSelected ? "auto" : "none",
      }}
      tabIndex={visible || isSelected ? undefined : -1}
      aria-hidden={!(visible || isSelected)}
      onClick={(e) => e.stopPropagation()}
    >
      <Box
        sx={(theme) => ({
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          bgcolor: isSelected
            ? alpha(theme.palette.primary.main, 0.9)
            : alpha(theme.palette.background.paper, 0.85),
          borderRadius: "50%",
          width: 26,
          height: 26,
          backdropFilter: "blur(4px)",
          transition: "background-color 0.2s ease-in-out, opacity 0.2s ease-in-out",
          "&:hover": { bgcolor: alpha(theme.palette.background.default, 0.95) },
        })}
        onClick={(e) => {
          e.stopPropagation();
          onSelectToggle?.(id, e);
        }}
      >
        <Checkbox
          size="small"
          disableRipple
          checked={isSelected}
          disabled={!(visible || isSelected)}
          tabIndex={visible || isSelected ? 0 : -1}
          data-testid="asset-checkbox"
          onClick={(e) => {
            // Stop propagation so the card's onAssetClick doesn't fire,
            // then trigger the toggle directly (the parent Box is a fallback)
            e.stopPropagation();
            onSelectToggle?.(id, e as unknown as React.MouseEvent<HTMLElement>);
          }}
          icon={<CheckBoxOutlineBlankIcon />}
          checkedIcon={<CheckBoxIcon />}
          sx={{
            padding: 0,
            color: isSelected ? "common.white" : undefined,
            "&.Mui-checked": { color: "common.white" },
            "& .MuiSvgIcon-root": { fontSize: 16 },
          }}
        />
      </Box>
    </Box>
  )
);

AssetCardSelection.displayName = "AssetCardSelection";
export default AssetCardSelection;
