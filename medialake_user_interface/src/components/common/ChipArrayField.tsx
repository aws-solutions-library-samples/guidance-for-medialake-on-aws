import React, { useRef, useState, useEffect, useCallback } from "react";
import { Box, Chip, Tooltip } from "@mui/material";
import { useTranslation } from "react-i18next";

interface ChipArrayFieldProps {
  values: string[];
  maxRows?: number;
  moreLabelFormatter?: (hidden: number) => string;
}

export const ChipArrayField: React.FC<ChipArrayFieldProps> = ({
  values,
  maxRows = 2,
  moreLabelFormatter,
}) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(values.length);

  const computeVisible = useCallback(() => {
    const container = containerRef.current;
    const summaryChip = summaryRef.current;
    if (!container || !summaryChip) return;

    const allChildren = Array.from(container.children) as HTMLElement[];
    // The last child is the summary chip — exclude it from the value chips list
    const chips = allChildren.slice(0, -1);
    if (chips.length === 0) return;

    // Temporarily show all chips and hide the summary to measure natural layout
    chips.forEach((c) => (c.style.display = ""));
    summaryChip.style.display = "none";

    // Determine the row height from the first chip
    const firstTop = chips[0].offsetTop;
    const rowHeight = chips[0].offsetHeight;
    const maxBottom = firstTop + rowHeight * maxRows;

    let count = chips.length;
    for (let i = 0; i < chips.length; i++) {
      if (chips[i].offsetTop + chips[i].offsetHeight > maxBottom) {
        count = i;
        break;
      }
    }

    // If all chips fit, no summary needed
    if (count >= chips.length) {
      setVisibleCount(chips.length);
      return;
    }

    // Measure with the real summary chip: hide chips beyond candidate count,
    // show the summary chip with the actual label, and verify it fits.
    while (count > 0) {
      // Hide chips beyond current candidate count
      chips.forEach((c, idx) => (c.style.display = idx < count ? "" : "none")); // i18n-ignore

      // Update summary chip text and show it for measurement
      const remaining = chips.length - count;
      const measureLabel = moreLabelFormatter
        ? moreLabelFormatter(remaining)
        : t("common.chipMore", { count: remaining });
      const labelEl = summaryChip.querySelector(".MuiChip-label");
      if (labelEl) labelEl.textContent = measureLabel;
      summaryChip.style.display = "";

      if (summaryChip.offsetTop + summaryChip.offsetHeight <= maxBottom) {
        break; // summary fits
      }
      count--;
    }

    setVisibleCount(count);
  }, [values, maxRows, t, moreLabelFormatter]);

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
  const moreLabel = moreLabelFormatter
    ? moreLabelFormatter(hidden)
    : t("common.chipMore", { count: hidden });

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
      <Tooltip title={hidden > 0 ? values.join(", ") : ""}>
        <Chip
          ref={summaryRef}
          label={moreLabel}
          size="small"
          variant="outlined"
          sx={{ display: hidden > 0 ? "inline-flex" : "none" }}
        />
      </Tooltip>
    </Box>
  );
};
