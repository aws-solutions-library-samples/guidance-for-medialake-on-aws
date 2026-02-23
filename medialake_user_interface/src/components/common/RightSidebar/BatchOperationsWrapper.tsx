import React from "react";
import { Box } from "@mui/material";
import BatchOperations from "./BatchOperations";

interface BatchOperationsWrapperProps {
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
  onBatchPipelineExecution?: (pipelineId: string) => void;
  onBatchPipelineExecutionRequest?: (pipelineId: string, pipelineName: string) => void;
  isPipelineExecutionLoading?: boolean;
}

const BatchOperationsWrapper: React.FC<BatchOperationsWrapperProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,
  onBatchShare,
  isDownloadLoading,
  isDeleteLoading,
  onClearSelection,
  onRemoveItem,
  onBatchPipelineExecution,
  onBatchPipelineExecutionRequest,
  isPipelineExecutionLoading,
}) => {
  return (
    <Box sx={{ height: "100%" }}>
      {selectedAssets.length > 0 && (
        <BatchOperations
          selectedAssets={selectedAssets}
          onBatchDelete={onBatchDelete}
          onBatchDownload={onBatchDownload}
          onBatchShare={onBatchShare}
          isDownloadLoading={isDownloadLoading}
          isDeleteLoading={isDeleteLoading}
          onClearSelection={onClearSelection}
          onRemoveItem={onRemoveItem}
          onBatchPipelineExecution={onBatchPipelineExecution}
          onBatchPipelineExecutionRequest={onBatchPipelineExecutionRequest}
          isPipelineExecutionLoading={isPipelineExecutionLoading}
        />
      )}
    </Box>
  );
};

export default BatchOperationsWrapper;
