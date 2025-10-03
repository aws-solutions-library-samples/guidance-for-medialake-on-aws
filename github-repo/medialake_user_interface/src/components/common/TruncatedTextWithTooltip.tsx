import React, { useRef, useState, useEffect } from "react";
import { Tooltip, Typography } from "@mui/material";

export const TruncatedTextWithTooltip: React.FC<{
  text: string;
  maxWidth?: string;
}> = ({ text, maxWidth = "100%" }) => {
  const textElementRef = useRef<HTMLSpanElement>(null);
  const [isTruncated, setIsTruncated] = useState(false);

  useEffect(() => {
    const checkTruncation = () => {
      if (textElementRef.current) {
        const { offsetWidth, scrollWidth } = textElementRef.current;
        setIsTruncated(scrollWidth > offsetWidth);
      }
    };

    checkTruncation();
    window.addEventListener("resize", checkTruncation);

    return () => {
      window.removeEventListener("resize", checkTruncation);
    };
  }, [text]);

  return (
    <Tooltip title={text} arrow disableHoverListener={!isTruncated}>
      <Typography
        variant="body2"
        ref={textElementRef}
        sx={{
          maxWidth: maxWidth,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </Typography>
    </Tooltip>
  );
};
