import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo } from "react";

interface UseTableVirtualizerOptions {
  rowHeight?: number;
  overscan?: number;
}

export const useTableVirtualizer = <T extends HTMLElement>(
  rows: any[],
  containerRef: React.RefObject<T>,
  options: UseTableVirtualizerOptions = {},
) => {
  const { rowHeight = 53, overscan = 20 } = options;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => rowHeight,
    overscan,
  });

  return virtualizer;
};
