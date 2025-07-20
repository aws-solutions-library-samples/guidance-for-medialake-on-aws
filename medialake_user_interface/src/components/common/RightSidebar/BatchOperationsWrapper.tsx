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
  onClearSelection?: () => void;
  onRemoveItem?: (assetId: string) => void;
}

const BatchOperationsWrapper: React.FC<BatchOperationsWrapperProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,
  onBatchShare,
  isDownloadLoading,
  onClearSelection,
  onRemoveItem,
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
          onClearSelection={onClearSelection}
          onRemoveItem={onRemoveItem}
        />
      )}
    </Box>
  );
};

export default BatchOperationsWrapper;
