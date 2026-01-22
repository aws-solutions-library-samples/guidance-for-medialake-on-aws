import React from "react";
import { Box, Container, Stack, Typography, Paper, Grid, useTheme } from "@mui/material";
import { SmartFolders } from "@/features/home/SmartFolders";
import { ConnectedStorage } from "@/features/home/ConnectedStorage";
import { SharedWithMeWidget } from "@/features/home/SharedWithMeWidget";
import { SharedByMeWidget } from "@/features/home/SharedByMeWidget";

const Home: React.FC = () => {
  const theme = useTheme();

  const paperStyles = {
    p: { xs: 2, sm: 3 },
    borderRadius: 2,
    backgroundColor: "rgba(255, 255, 255, 0.8)",
    backdropFilter: "blur(10px)",
    border: "1px solid",
    borderColor: "divider",
    transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
    "&:hover": {
      transform: "translateY(-2px)",
      boxShadow: theme.shadows[4],
    },
  };

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
          gap: 4,
        }}
      >
        <Box sx={{ mb: 2 }}>
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

        <Stack
          spacing={4}
          sx={{
            width: "100%",
          }}
        >
          {/* Shared Collections Section */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={paperStyles}>
                <SharedWithMeWidget maxItems={3} />
              </Paper>
            </Grid>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={paperStyles}>
                <SharedByMeWidget maxItems={3} />
              </Paper>
            </Grid>
          </Grid>

          <Paper elevation={0} sx={paperStyles}>
            <SmartFolders />
          </Paper>

          <Paper elevation={0} sx={paperStyles}>
            <ConnectedStorage />
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
};

export default Home;
