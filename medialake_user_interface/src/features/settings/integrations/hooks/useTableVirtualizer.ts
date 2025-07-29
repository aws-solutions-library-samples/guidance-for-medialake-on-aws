import { useVirtualizer } from "@tanstack/react-virtual";
import { Row } from "@tanstack/react-table";
import { Integration } from "../components/IntegrationList/types";

interface UseTableVirtualizerOptions {
  rowHeight?: number;
  overscan?: number;
}

export const useTableVirtualizer = (
  rows: Row<Integration>[],
  containerRef: React.RefObject<HTMLDivElement>,
  options: UseTableVirtualizerOptions = {},
) => {
  const { rowHeight = 52, overscan = 10 } = options;

  return useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => rowHeight,
    overscan,
  });
};
