import React, { useEffect } from "react";
import { Box, Tabs, Tab } from "@mui/material";
import FilterOperations from "./FilterOperations";
import BatchOperationsWrapper from "./BatchOperationsWrapper";
import { useRightSidebar } from "./SidebarContext";
import { useTranslation } from "react-i18next";

interface TabbedSidebarProps {
  selectedAssets: Array<{
    id: string;
    name: string;
    type: string;
  }>;
  onBatchDelete?: () => void;
  onBatchDownload?: () => void;
  onBatchShare?: () => void;
  isDownloadLoading?: boolean;
  isDeleteLoading?: boolean;
  onClearSelection?: () => void;
  onRemoveItem?: (assetId: string) => void;
  filterComponent?: React.ReactNode;
  onBatchPipelineExecution?: (pipelineId: string) => void;
  onBatchPipelineExecutionRequest?: (pipelineId: string, pipelineName: string) => void;
  isPipelineExecutionLoading?: boolean;
}

const TabbedSidebar: React.FC<TabbedSidebarProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,
  onBatchShare,
  isDownloadLoading,
  isDeleteLoading,
  onClearSelection,
  onRemoveItem,
  filterComponent,
  onBatchPipelineExecution,
  onBatchPipelineExecutionRequest,
  isPipelineExecutionLoading,
}) => {
  const { t } = useTranslation();
  const { setHasSelectedItems, closeSidebar } = useRightSidebar();
  const [activeTab, setActiveTab] = React.useState<"filter" | "batch">(
    selectedAssets.length > 0 ? "batch" : "filter"
  );

  // Update hasSelectedItems when selection changes - this controls sidebar visibility
  useEffect(() => {
    if (selectedAssets.length > 0) {
      setHasSelectedItems(true);
      // Switch to batch tab when first item is selected
      if (selectedAssets.length === 1) {
        setActiveTab("batch");
      }
    } else {
      setHasSelectedItems(false);
      setActiveTab("filter");
    }
  }, [selectedAssets.length, setHasSelectedItems]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: "filter" | "batch") => {
    setActiveTab(newValue);
  };

  // Handle clear selection - close sidebar after clearing
  const handleClearSelection = () => {
    if (onClearSelection) {
      onClearSelection();
    }
    // Sidebar will close automatically via the useEffect when selectedAssets becomes empty
  };

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.paper",
      }}
    >
      {/* Only show tabs when there are selected assets, otherwise show filter directly */}
      {selectedAssets.length > 0 ? (
        <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            aria-label="search options tabs"
            variant="fullWidth"
            sx={{
              "& .MuiTab-root": {
                py: 1.25,
                fontWeight: 500,
                fontSize: "0.8125rem",
                textTransform: "none",
                letterSpacing: "0.01em",
                minHeight: 42,
              },
              "& .Mui-selected": {
                fontWeight: 600,
              },
            }}
          >
            <Tab
              label={t("rightSidebar.filterOptions")}
              value="filter"
              id="filter-tab"
              aria-controls="filter-panel"
            />
            <Tab
              label={`${selectedAssets.length} Selected`}
              value="batch"
              id="batch-tab"
              aria-controls="batch-panel"
            />
          </Tabs>
        </Box>
      ) : null}

      {/* Content area that fills the remaining height */}
      <Box sx={{ flexGrow: 1, overflow: "auto" }}>
        {selectedAssets.length > 0 ? (
          <>
            <Box
              role="tabpanel"
              hidden={activeTab !== "filter"}
              id="filter-panel"
              aria-labelledby="filter-tab"
              sx={{
                height: "100%",
                display: activeTab === "filter" ? "block" : "none",
              }}
            >
              <FilterOperations filterComponent={filterComponent} />
            </Box>

            <Box
              role="tabpanel"
              hidden={activeTab !== "batch"}
              id="batch-panel"
              aria-labelledby="batch-tab"
              sx={{
                height: "100%",
                display: activeTab === "batch" ? "block" : "none",
              }}
            >
              <BatchOperationsWrapper
                selectedAssets={selectedAssets}
                onBatchDelete={onBatchDelete}
                onBatchDownload={onBatchDownload}
                onBatchShare={onBatchShare}
                isDownloadLoading={isDownloadLoading}
                isDeleteLoading={isDeleteLoading}
                onClearSelection={handleClearSelection}
                onRemoveItem={onRemoveItem}
                onBatchPipelineExecution={onBatchPipelineExecution}
                onBatchPipelineExecutionRequest={onBatchPipelineExecutionRequest}
                isPipelineExecutionLoading={isPipelineExecutionLoading}
              />
            </Box>
          </>
        ) : (
          /* Show only filter operations when no assets are selected */
          <FilterOperations filterComponent={filterComponent} />
        )}
      </Box>
    </Box>
  );
};

export default TabbedSidebar;
