import React, { useEffect } from 'react';
import { Box, Typography, Divider, Paper, Tabs, Tab } from '@mui/material';
import BatchOperations from './BatchOperations';
import { useRightSidebar } from './SidebarContext';

interface FilterAndBatchOperationsProps {
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
  filterComponent?: React.ReactNode;
}

const FilterAndBatchOperations: React.FC<FilterAndBatchOperationsProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,
  onBatchShare,
  isDownloadLoading,
  onClearSelection,
  onRemoveItem,
  filterComponent
}) => {
  const { setHasSelectedItems } = useRightSidebar();
  const [activeTab, setActiveTab] = React.useState<'filter' | 'batch'>(
    selectedAssets.length > 0 ? 'batch' : 'filter'
  );

  // Auto-switch to batch tab when items are first selected,
  // but don't force it if user manually switches to filter tab
  useEffect(() => {
    // Only auto-switch when going from 0 to some selected items
    if (selectedAssets.length > 0) {
      setHasSelectedItems(true);
      
      // Only switch to batch tab if this is the initial selection
      // (when going from 0 selected to some selected)
      if (selectedAssets.length === 1) {
        setActiveTab('batch');
      }
    } else {
      setHasSelectedItems(false);
      setActiveTab('filter');
    }
  }, [selectedAssets.length, setHasSelectedItems]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: 'filter' | 'batch') => {
    setActiveTab(newValue);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}>
      {/* Tabs directly at the top of the sidebar */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs 
          value={activeTab} 
          onChange={handleTabChange}
          aria-label="search options tabs"
          variant="fullWidth"
          sx={{
            '& .MuiTab-root': {
              py: 1.5,
              fontWeight: 500
            },
            '& .Mui-selected': {
              fontWeight: 600
            }
          }}
        >
          <Tab 
            label="FILTER OPTIONS" 
            value="filter"
            id="filter-tab"
            aria-controls="filter-panel"
          />
          <Tab 
            label={`BATCH OPERATIONS ${selectedAssets.length > 0 ? `(${selectedAssets.length})` : ''}`}
            value="batch"
            id="batch-tab"
            aria-controls="batch-panel"
            disabled={selectedAssets.length === 0}
          />
        </Tabs>
      </Box>

      {/* Content area that fills the remaining height */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <Box
          role="tabpanel"
          hidden={activeTab !== 'filter'}
          id="filter-panel"
          aria-labelledby="filter-tab"
          sx={{ height: '100%', display: activeTab === 'filter' ? 'block' : 'none' }}
        >
          {filterComponent}
        </Box>

        <Box
          role="tabpanel"
          hidden={activeTab !== 'batch'}
          id="batch-panel"
          aria-labelledby="batch-tab"
          sx={{ height: '100%', display: activeTab === 'batch' ? 'block' : 'none' }}
        >
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
      </Box>
    </Box>
  );
};

export default FilterAndBatchOperations;