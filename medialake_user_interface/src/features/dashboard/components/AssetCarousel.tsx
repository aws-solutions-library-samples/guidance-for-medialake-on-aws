import React, { useRef, useEffect, useState, useCallback } from "react";
import { Box, Skeleton } from "@mui/material";

// Carousel configuration constants
const CARD_WIDTH = 240;
const CARD_HEIGHT = 280; // Height including metadata area
const CARD_GAP = 16;
const PADDING = 16;

interface AssetCarouselProps<T> {
  items: T[];
  renderCard: (item: T, index: number) => React.ReactNode;
  getItemKey: (item: T) => string;
  isLoading?: boolean;
  emptyState?: React.ReactNode;
  cardWidth?: number;
  cardHeight?: number;
}

export function AssetCarousel<T>({
  items,
  renderCard,
  getItemKey,
  isLoading = false,
  emptyState,
  cardWidth = CARD_WIDTH,
  cardHeight = CARD_HEIGHT,
}: AssetCarouselProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [rowCount, setRowCount] = useState(1);
  const [prevRowCount, setPrevRowCount] = useState(1);

  // Calculate row count based on container height
  const calculateRowCount = useCallback(() => {
    if (!containerRef.current) return 1;

    const containerHeight = containerRef.current.offsetHeight;
    const availableHeight = containerHeight - PADDING * 2;

    // Calculate how many rows fit
    const twoRowsHeight = cardHeight * 2 + CARD_GAP;
    const threeRowsHeight = cardHeight * 3 + CARD_GAP * 2;

    if (availableHeight >= threeRowsHeight) return 3;
    if (availableHeight >= twoRowsHeight) return 2;
    return 1;
  }, [cardHeight]);

  // Update row count on resize
  useEffect(() => {
    const updateRowCount = () => {
      const newRowCount = calculateRowCount();
      setPrevRowCount(rowCount);
      setRowCount(newRowCount);
    };

    updateRowCount();

    const resizeObserver = new ResizeObserver(updateRowCount);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, [calculateRowCount, rowCount]);

  // Reset scroll position when row count changes
  useEffect(() => {
    if (prevRowCount !== rowCount && scrollRef.current) {
      scrollRef.current.scrollLeft = 0;
    }
  }, [rowCount, prevRowCount]);

  if (isLoading) {
    return (
      <Box
        ref={containerRef}
        sx={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Box
          sx={{
            flex: 1,
            overflowX: "auto",
            overflowY: "hidden",
            p: 2,
          }}
        >
          <Box
            sx={{
              display: "grid",
              gridTemplateRows: `repeat(${rowCount}, ${cardHeight}px)`,
              gridAutoFlow: "column",
              gridAutoColumns: `${cardWidth}px`,
              gap: `${CARD_GAP}px`,
              width: "max-content",
            }}
          >
            {Array.from({ length: rowCount * 3 }).map((_, i) => (
              <Skeleton
                key={i}
                variant="rectangular"
                width={cardWidth}
                height={cardHeight}
                sx={{ borderRadius: 2 }}
              />
            ))}
          </Box>
        </Box>
      </Box>
    );
  }

  if (!items || items.length === 0) {
    return (
      <Box
        ref={containerRef}
        sx={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {emptyState}
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box
        ref={scrollRef}
        sx={{
          flex: 1,
          overflowX: "auto",
          overflowY: "hidden",
          p: 2,
          // Always show horizontal scrollbar
          "&::-webkit-scrollbar": {
            height: "8px",
            display: "block",
          },
          "&::-webkit-scrollbar-track": {
            backgroundColor: "rgba(0,0,0,0.05)",
            borderRadius: "4px",
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: "rgba(0,0,0,0.2)",
            borderRadius: "4px",
            "&:hover": {
              backgroundColor: "rgba(0,0,0,0.3)",
            },
          },
          scrollbarWidth: "thin",
        }}
      >
        <Box
          sx={{
            display: "grid",
            gridTemplateRows: `repeat(${rowCount}, ${cardHeight}px)`,
            gridAutoFlow: "column",
            gridAutoColumns: `${cardWidth}px`,
            gap: `${CARD_GAP}px`,
            width: "max-content",
          }}
        >
          {items.map((item, index) => (
            <Box
              key={getItemKey(item)}
              sx={{
                width: cardWidth,
                height: cardHeight,
                overflow: "hidden",
              }}
            >
              {renderCard(item, index)}
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
}
