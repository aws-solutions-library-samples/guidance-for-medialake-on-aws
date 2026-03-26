import React, { useRef, useState, useEffect, useCallback } from "react";
import { Box, Chip, Tooltip } from "@mui/material";

interface ChipArrayFieldProps {
  values: string[];
  maxRows?: number;
}

export const ChipArrayField: React.FC<ChipArrayFieldProps> = ({ values, maxRows = 2 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(values.length);

  const computeVisible = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const chips = Array.from(container.children) as HTMLElement[];
    if (chips.length === 0) return;

    // Temporarily show all chips to measure
    chips.forEach((c) => (c.style.display = ""));

    // Determine the row height from the first chip
    const firstTop = chips[0].offsetTop;
    const rowHeight = chips[0].offsetHeight;
    const maxBottom = firstTop + rowHeight * maxRows;

    let count = chips.length;
    for (let i = 0; i < chips.length; i++) {
      if (chips[i].offsetTop + chips[i].offsetHeight > maxBottom) {
        // The "+N more" chip will take space, so step back one more if needed
        count = Math.max(i - 1, 0);
        break;
      }
    }

    setVisibleCount(count);
  }, [values, maxRows]);

  useEffect(() => {
    computeVisible();
  }, [computeVisible]);

  // Observe container resize
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => computeVisible());
    ro.observe(container);
    return () => ro.disconnect();
  }, [computeVisible]);

  const hidden = values.length - visibleCount;

  return (
    <Box
      ref={containerRef}
      sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, overflow: "hidden" }}
    >
      {values.map((v, i) => (
        <Chip
          key={i}
          label={v}
          size="small"
          sx={{ display: i < visibleCount || hidden <= 0 ? "inline-flex" : "none" }}
        />
      ))}
      {hidden > 0 && (
        <Tooltip title={values.join(", ")}>
          <Chip label={`+${hidden} more`} size="small" variant="outlined" />
        </Tooltip>
      )}
    </Box>
  );
};
