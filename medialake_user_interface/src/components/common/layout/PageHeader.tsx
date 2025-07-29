import React from "react";
import { Box, Typography, useTheme } from "@mui/material";
import { useDirection } from "../../../contexts/DirectionContext";

interface PageHeaderProps {
  title: string;
  description: string;
  action?: React.ReactNode;
}
const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  action,
}) => {
  const theme = useTheme();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  return (
    <Box sx={{ mb: 4 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          mb: 3,
        }}
      >
        <Box sx={{ textAlign: isRTL ? "right" : "left" }}>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              mb: 1,
              color: theme.palette.primary.main,
              textAlign: isRTL ? "right" : "left",
            }}
          >
            {title}
          </Typography>
          <Typography
            variant="body1"
            sx={{
              color: theme.palette.text.secondary,
              maxWidth: "600px",
              textAlign: isRTL ? "right" : "left",
              [isRTL ? "marginLeft" : "marginRight"]: "auto",
            }}
          >
            {description}
          </Typography>
        </Box>
        {action}
      </Box>
    </Box>
  );
};

export default PageHeader;
