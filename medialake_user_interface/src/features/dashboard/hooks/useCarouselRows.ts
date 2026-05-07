import { useRef, useEffect, useState, useCallback } from "react";

const DEFAULT_CARD_GAP = 16;
const DEFAULT_PADDING = 16;

interface UseCarouselRowsOptions {
  cardHeight: number;
  cardGap?: number;
  padding?: number;
  maxRows?: number;
}

interface UseCarouselRowsResult {
  rowCount: number;
  containerRef: React.RefObject<HTMLDivElement>;
  availableHeight: number;
}

/**
 * Hook to calculate the number of rows that fit in a container
 * based on card height and available space.
 */
export function useCarouselRows({
  cardHeight,
  cardGap = DEFAULT_CARD_GAP,
  padding = DEFAULT_PADDING,
  maxRows = 3,
}: UseCarouselRowsOptions): UseCarouselRowsResult {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rowCount, setRowCount] = useState(1);
  const [availableHeight, setAvailableHeight] = useState(0);

  const calculateRowCount = useCallback(() => {
    if (!containerRef.current) return { rows: 1, height: 0 };

    const containerHeight = containerRef.current.offsetHeight;
    const available = containerHeight - padding * 2;

    // Calculate how many rows fit
    let rows = 1;
    for (let r = maxRows; r >= 1; r--) {
      const requiredHeight = cardHeight * r + cardGap * (r - 1);
      if (available >= requiredHeight) {
        rows = r;
        break;
      }
    }

    return { rows, height: available };
  }, [cardHeight, cardGap, padding, maxRows]);

  useEffect(() => {
    const updateRowCount = () => {
      const { rows, height } = calculateRowCount();
      setRowCount(rows);
      setAvailableHeight(height);
    };

    updateRowCount();

    const resizeObserver = new ResizeObserver(updateRowCount);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, [calculateRowCount]);

  return {
    rowCount,
    containerRef,
    availableHeight,
  };
}
