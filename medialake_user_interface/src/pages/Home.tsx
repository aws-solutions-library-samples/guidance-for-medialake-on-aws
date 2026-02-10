import React from "react";
import {
  Box,
  Typography,
  useTheme,
  useMediaQuery,
  Fade,
  Button,
  IconButton,
  Tooltip,
} from "@mui/material";
import { Add as AddIcon, RestartAlt as ResetIcon, Edit as EditIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useDirection } from "../contexts/DirectionContext";
import { useSidebar } from "../contexts/SidebarContext";
import { drawerWidth, collapsedDrawerWidth } from "../constants";
import {
  DashboardGrid,
  ExpandedWidgetModal,
  DashboardSelector,
  useDashboardSync,
  DashboardSelectionProvider,
  useDashboardSelectionRequired,
} from "@/features/dashboard";
import {
  useDashboardStore,
  useAvailableWidgets,
  useDashboardSyncState,
} from "@/features/dashboard/store/dashboardStore";
import { RightSidebar, RightSidebarProvider } from "../components/common/RightSidebar";
import TabbedSidebar from "../components/common/RightSidebar/TabbedSidebar";
import { BulkDeleteDialog } from "@/components/assets/BulkDeleteDialog";
import ApiStatusModal from "../components/ApiStatusModal";

// Inner component that uses the selection context
const HomeContent: React.FC = () => {
  const theme = useTheme();
  const isSmall = useMediaQuery(theme.breakpoints.down("sm"));
  const { t } = useTranslation();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";
  const { isCollapsed } = useSidebar();

  const setWidgetSelectorOpen = useDashboardStore((state) => state.setWidgetSelectorOpen);
  const availableWidgets = useAvailableWidgets();
  const { hasPendingChanges } = useDashboardSyncState();

  // Initialize dashboard sync with API
  const { isLoading, resetLayout } = useDashboardSync();

  // Get selection state from context
  const assetSelection = useDashboardSelectionRequired();

  const handleOpenWidgetSelector = () => {
    setWidgetSelectorOpen(true);
  };

  const handleReset = () => {
    resetLayout();
  };

  return (
    <>
      <Box
        component="main"
        sx={{
          position: "fixed",
          top: 64,
          ...(isRTL
            ? { left: 0, right: isCollapsed ? collapsedDrawerWidth : drawerWidth }
            : {
                left: isCollapsed ? collapsedDrawerWidth : drawerWidth,
                right: 0,
              }),
          bottom: 0,
          backgroundColor: "transparent",
          overflowY: "auto",
          overflowX: "hidden",
          transition: theme.transitions.create(["left", "right"], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Box sx={{ py: 3, px: { xs: 2, sm: 3, md: 4 }, width: "100%" }}>
          <Fade in={true} timeout={800}>
            <Box sx={{ mb: 4 }}>
              {/* Header Section */}
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  mb: 3,
                }}
              >
                {/* Left side - Dashboard Selector */}
                <Box sx={{ flex: 1 }}>
                  <DashboardSelector />
                </Box>

                {/* Centered Title */}
                <Box sx={{ textAlign: "center" }}>
                  <Typography
                    variant={isSmall ? "h4" : "h3"}
                    component="h1"
                    sx={{
                      fontWeight: 700,
                      background: `linear-gradient(45deg, ${theme.palette.primary.main} 20%, ${theme.palette.secondary.main} 80%)`,
                      backgroundClip: "text",
                      WebkitBackgroundClip: "text",
                      color: "transparent",
                    }}
                  >
                    {t("app.branding.name")}
                  </Typography>
                </Box>

                {/* Right side controls */}
                <Box
                  sx={{
                    flex: 1,
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: 1,
                    alignItems: "center",
                  }}
                >
                  {/* Unsaved changes indicator */}
                  {hasPendingChanges && (
                    <Tooltip title={t("dashboard.status.unsavedChanges")}>
                      <Box sx={{ display: "flex", alignItems: "center", mr: 1 }}>
                        <EditIcon fontSize="small" sx={{ color: "warning.main" }} />
                      </Box>
                    </Tooltip>
                  )}

                  <Tooltip title={t("dashboard.actions.resetLayout")}>
                    <IconButton
                      onClick={handleReset}
                      size="small"
                      disabled={isLoading}
                      sx={{
                        color: "text.secondary",
                        "&:hover": {
                          color: "warning.main",
                        },
                      }}
                    >
                      <ResetIcon />
                    </IconButton>
                  </Tooltip>

                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<AddIcon />}
                    onClick={handleOpenWidgetSelector}
                    disabled={availableWidgets.length === 0 || isLoading}
                  >
                    {t("dashboard.actions.addWidget")}
                  </Button>
                </Box>
              </Box>

              {/* Dashboard Grid */}
              <DashboardGrid showHeader={false} />
            </Box>
          </Fade>
        </Box>

        {/* Right Sidebar for batch operations */}
        <RightSidebar>
          <TabbedSidebar
            selectedAssets={assetSelection.selectedAssets}
            onBatchDelete={assetSelection.handleBatchDelete}
            onBatchDownload={assetSelection.handleBatchDownload}
            onBatchShare={assetSelection.handleBatchShare}
            onClearSelection={assetSelection.handleClearSelection}
            onRemoveItem={assetSelection.handleRemoveAsset}
          />
        </RightSidebar>

        {/* Expanded Widget Modal */}
        <ExpandedWidgetModal />
      </Box>

      {/* Bulk Delete Dialog */}
      <BulkDeleteDialog
        open={assetSelection.isDeleteDialogOpen}
        onClose={assetSelection.handleDeleteDialogClose}
        onConfirm={assetSelection.handleConfirmDelete}
        selectedCount={assetSelection.selectedAssets.length}
        confirmationText={assetSelection.deleteConfirmationText}
        onConfirmationTextChange={assetSelection.setDeleteConfirmationText}
        isLoading={assetSelection.isDeleteLoading}
      />

      {/* API Status Modal */}
      <ApiStatusModal
        open={assetSelection.modalState.open}
        onClose={assetSelection.handleModalClose}
        status={assetSelection.modalState.status}
        action={assetSelection.modalState.action}
        message={assetSelection.modalState.message}
        progress={assetSelection.modalState.progress}
      />
    </>
  );
};

const Home: React.FC = () => {
  return (
    <RightSidebarProvider>
      <DashboardSelectionProvider>
        <HomeContent />
      </DashboardSelectionProvider>
    </RightSidebarProvider>
  );
};

export default Home;
