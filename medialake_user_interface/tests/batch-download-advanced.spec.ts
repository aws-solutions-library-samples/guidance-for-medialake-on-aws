import { test, expect } from './fixtures/auth.fixtures';
import { AssetSelector, BatchOperationsHelper, ApiMockHelper } from './helpers/batch-download.helpers';

/**
 * Advanced Batch Download Tests
 * 
 * Comprehensive tests for bulk download functionality using helper utilities:
 * 1. Select 1000 files and download batch
 * 2. Select a single file and download batch  
 * 3. Select 1 large file (>1024MB) and one small file and download batch
 * 4. Error handling and edge cases
 */

test.describe('Advanced Batch Download Tests', () => {
  let assetSelector: AssetSelector;
  let batchOpsHelper: BatchOperationsHelper;
  let apiMockHelper: ApiMockHelper;

  test.beforeEach(async ({ authenticatedPage }) => {
    // Initialize helpers
    assetSelector = new AssetSelector(authenticatedPage);
    batchOpsHelper = new BatchOperationsHelper(authenticatedPage);
    apiMockHelper = new ApiMockHelper(authenticatedPage);

    // Wait for authentication to complete - wait for redirect to home page
    await authenticatedPage.waitForURL('http://localhost:5173/', { timeout: 15000 });
    
    // Wait for the main content to load
    await authenticatedPage.waitForSelector('h1:has-text("MediaLake"), .main-content, [data-testid="home-page"]', { timeout: 10000 });
    
    // Add a small delay to ensure session is fully established
    await authenticatedPage.waitForTimeout(2000);
    
    // Navigate to the search page with all assets (200 per page)
    await authenticatedPage.goto('http://localhost:5173/search?q=*&semantic=false&page=1&pageSize=200');
    await assetSelector.waitForAssetsToLoad();
  });

  test.afterEach(async ({ authenticatedPage }) => {
    // Clean up any API mocks
    await apiMockHelper.clearMocks();
  });

  test('should select 1000 files and download batch', async ({ authenticatedPage }) => {
    // Use "Select Page" control to select assets across multiple pages
    const selectedCount = await assetSelector.selectAssetsByCriteria({
      count: 1000,
      useSelectPage: true
    });
    
    // Verify we have selected assets
    expect(selectedCount).toBeGreaterThan(0);
    console.log(`Successfully selected ${selectedCount} assets using Select Page control`);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Verify the selection count matches
    const uiSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(uiSelectionCount).toBe(selectedCount);
    
    // Verify the batch tab shows the correct count
    await expect(authenticatedPage.locator('#batch-tab')).toContainText(`(${selectedCount})`);
    
    // Initiate batch download
    await batchOpsHelper.initiateBatchDownload();
    
    // Verify download success
    await batchOpsHelper.verifyDownloadSuccess();
    
    // Verify selection is cleared after successful download
    await expect(authenticatedPage.locator('#batch-tab')).toBeDisabled();
  });

  test('should select a single file and download batch', async ({ authenticatedPage }) => {
    // Select exactly one asset
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 1 });
    expect(selectedCount).toBe(1);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Verify single selection is displayed
    const uiSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(uiSelectionCount).toBe(1);
    
    // Verify the selected asset is shown in the batch operations panel
    const selectedAssets = await batchOpsHelper.getSelectedAssetsList();
    expect(selectedAssets).toHaveLength(1);
    
    // Initiate batch download
    await batchOpsHelper.initiateBatchDownload();
    
    // Verify download success
    await batchOpsHelper.verifyDownloadSuccess();
    
    // Verify selection is cleared
    await expect(authenticatedPage.locator('#batch-tab')).toBeDisabled();
  });

  test('should select 1 large file (>1024MB) and one small file and download batch', async ({ authenticatedPage }) => {
    // Select one large and one small file
    const { large, small } = await assetSelector.selectLargeAndSmallFiles();
    const totalSelected = large + small;
    
    expect(totalSelected).toBeGreaterThanOrEqual(2);
    console.log(`Selected ${large} large file(s) and ${small} small file(s)`);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Verify selection count
    const uiSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(uiSelectionCount).toBe(totalSelected);
    
    // Verify multiple assets are shown in the batch operations panel
    const selectedAssets = await batchOpsHelper.getSelectedAssetsList();
    expect(selectedAssets).toHaveLength(totalSelected);
    
    // Initiate batch download
    await batchOpsHelper.initiateBatchDownload();
    
    // Verify download success
    await batchOpsHelper.verifyDownloadSuccess();
    
    // Verify selection is cleared
    await expect(authenticatedPage.locator('#batch-tab')).toBeDisabled();
  });

  test('should handle batch download server errors gracefully', async ({ authenticatedPage }) => {
    // Select some assets
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 3 });
    expect(selectedCount).toBeGreaterThan(0);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Mock a server error
    await apiMockHelper.mockBulkDownloadError(500, 'Internal server error');
    
    // Attempt batch download
    const downloadButton = authenticatedPage.locator('button:has-text("Download")').first();
    await downloadButton.click();
    
    // Verify error handling
    await expect(authenticatedPage.locator('text="Download Failed", [data-testid="error-modal"]')).toBeVisible({ timeout: 10000 });
    
    // Verify selection is still maintained after error
    const uiSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(uiSelectionCount).toBe(selectedCount);
  });

  test('should handle network timeout errors', async ({ authenticatedPage }) => {
    // Select some assets
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 2 });
    expect(selectedCount).toBeGreaterThan(0);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Mock a timeout error
    await authenticatedPage.route('**/api/assets/download/bulk/**', route => {
      // Simulate timeout by not responding
      setTimeout(() => {
        route.fulfill({
          status: 408,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Request timeout' })
        });
      }, 1000);
    });
    
    // Attempt batch download
    const downloadButton = authenticatedPage.locator('button:has-text("Download")').first();
    await downloadButton.click();
    
    // Verify error handling
    await expect(authenticatedPage.locator('text="Download Failed", [data-testid="error-modal"]')).toBeVisible({ timeout: 15000 });
  });

  test('should clear selection using clear button', async ({ authenticatedPage }) => {
    // Select some assets
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 5 });
    expect(selectedCount).toBeGreaterThan(0);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Clear selection
    await batchOpsHelper.clearSelection();
    
    // Verify we're back to filter tab
    await expect(authenticatedPage.locator('#filter-tab')).toHaveAttribute('aria-selected', 'true');
  });

  test('should remove individual items from selection', async ({ authenticatedPage }) => {
    // Select multiple assets
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 4 });
    expect(selectedCount).toBeGreaterThanOrEqual(2);
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Get initial list of selected assets
    const initialAssets = await batchOpsHelper.getSelectedAssetsList();
    expect(initialAssets).toHaveLength(selectedCount);
    
    // Remove first item
    await batchOpsHelper.removeItemFromSelection(0);
    
    // Verify count decreased
    const newSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(newSelectionCount).toBe(selectedCount - 1);
    
    // Verify the item was removed from the list
    const remainingAssets = await batchOpsHelper.getSelectedAssetsList();
    expect(remainingAssets).toHaveLength(selectedCount - 1);
  });

  test('should handle empty selection gracefully', async ({ authenticatedPage }) => {
    // Navigate to search page without selecting anything
    await authenticatedPage.goto('http://localhost:5173/search?q=*&semantic=false&page=1&pageSize=200');
    await assetSelector.waitForAssetsToLoad();
    
    // Verify batch operations tab is disabled
    await expect(authenticatedPage.locator('#batch-tab')).toBeDisabled();
    
    // Verify filter tab is active
    await expect(authenticatedPage.locator('#filter-tab')).toHaveAttribute('aria-selected', 'true');
  });

  test('should maintain selection across page navigation', async ({ authenticatedPage }) => {
    // Select some assets
    const selectedCount = await assetSelector.selectAssetsByCriteria({ count: 3 });
    expect(selectedCount).toBeGreaterThan(0);
    
    // Navigate away and back
    await authenticatedPage.goto('http://localhost:5173/dashboard');
    await authenticatedPage.goto('http://localhost:5173/search?q=*&semantic=false&page=1&pageSize=200');
    await assetSelector.waitForAssetsToLoad();
    
    // Verify selection is maintained (from localStorage)
    await expect(authenticatedPage.locator('#batch-tab')).not.toBeDisabled();
    
    // Navigate to batch operations
    await batchOpsHelper.navigateToBatchOperations();
    
    // Verify selection count is maintained
    const uiSelectionCount = await batchOpsHelper.getSelectionCount();
    expect(uiSelectionCount).toBe(selectedCount);
  });

  test('should handle large selection counts efficiently', async ({ authenticatedPage }) => {
    // Select a large number of assets (limited by what's available)
    const selectedCount = await assetSelector.selectAssetsAcrossPages(500);
    
    if (selectedCount > 0) {
      console.log(`Selected ${selectedCount} assets for large selection test`);
      
      // Navigate to batch operations
      await batchOpsHelper.navigateToBatchOperations();
      
      // Verify UI can handle large selection
      const uiSelectionCount = await batchOpsHelper.getSelectionCount();
      expect(uiSelectionCount).toBe(selectedCount);
      
      // Verify batch operations panel loads without issues
      await expect(authenticatedPage.locator('#batch-panel')).toBeVisible();
      
      // Clear selection to clean up
      await batchOpsHelper.clearSelection();
    } else {
      console.log('No assets available for large selection test');
    }
  });

  test('should filter assets by type before selection', async ({ authenticatedPage }) => {
    // Get all available assets
    const allAssets = await assetSelector.getVisibleAssets();
    console.log(`Found ${allAssets.length} total assets`);
    
    // Try to select only video assets
    const videoSelected = await assetSelector.selectAssetsByCriteria({
      count: 3,
      types: ['video', 'mp4', 'mov', 'avi']
    });
    
    if (videoSelected > 0) {
      // Navigate to batch operations
      await batchOpsHelper.navigateToBatchOperations();
      
      // Verify selection
      const selectedAssets = await batchOpsHelper.getSelectedAssetsList();
      expect(selectedAssets).toHaveLength(videoSelected);
      
      console.log(`Selected ${videoSelected} video assets:`, selectedAssets);
    } else {
      console.log('No video assets found for type filtering test');
    }
  });
});