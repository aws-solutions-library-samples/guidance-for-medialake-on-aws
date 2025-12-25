import React from "react";
import { Box, Container, Typography } from "@mui/material";
import { DashboardGrid, ExpandedWidgetModal } from "@/features/dashboard";

const Home: React.FC = () => {
  return (
    <Box
      sx={{
        flexGrow: 1,
        minHeight: "100vh",
        background: "linear-gradient(145deg, #f6f8fc 0%, #ffffff 100%)",
        p: { xs: 2, sm: 3 },
        mt: 8,
      }}
    >
      <Container
        maxWidth="lg"
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        <Box sx={{ mb: 1 }}>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontWeight: 600,
              color: "primary.main",
              mb: 1,
            }}
          >
            Welcome to MediaLake
          </Typography>
          <Typography variant="subtitle1" color="text.secondary" sx={{ maxWidth: "800px" }}>
            Manage and organize your media files efficiently
          </Typography>
        </Box>

        <DashboardGrid />
        <ExpandedWidgetModal />
      </Container>
    </Box>
  );
};

export default Home;
