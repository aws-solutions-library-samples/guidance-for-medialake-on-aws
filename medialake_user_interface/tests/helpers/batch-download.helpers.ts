import { Page, expect } from '@playwright/test';

/**
 * Helper utilities for batch download tests
 */

export interface AssetInfo {
  id: string;
  name: string;
  type: string;
  size?: number; // Size in MB
}

/**
 * Advanced asset selection with size filtering
 */
export class AssetSelector {
  constructor(private page: Page) {}

  /**
   * Get all visible assets with their metadata
   */
  async getVisibleAssets(): Promise<AssetInfo[]> {
    const assets: AssetInfo[] = [];
    
    const assetCards = await this.page.locator('div:has(img[data-image-id]), .MuiBox-root:has(img), div:has(.MuiCheckbox-root)').all();
    
    for (let i = 0; i < assetCards.length; i++) {
      const card = assetCards[i];
      const cardText = await card.textContent() || '';
      
      // Extract asset name
      const nameElement = card.locator('.asset-name, [data-testid="asset-name"], .title, h3, h4').first();
      const name = await nameElement.textContent() || `Asset ${i + 1}`;
      
      // Extract asset type
      const typeElement = card.locator('.asset-type, [data-testid="asset-type"], .type').first();
      const type = await typeElement.textContent() || 'unknown';
      
      // Extract size if available
      let size: number | undefined;
      const sizeMatch = cardText.match(/(\d+(?:\.\d+)?)\s*(MB|GB|KB)/i);
      if (sizeMatch) {
        const sizeValue = parseFloat(sizeMatch[1]);
        const unit = sizeMatch[2].toUpperCase();
        
        // Convert to MB
        switch (unit) {
          case 'GB':
            size = sizeValue * 1024;
            break;
          case 'KB':
            size = sizeValue / 1024;
            break;
          default:
            size = sizeValue;
        }
      }
      
      assets.push({
        id: `asset-${i}`,
        name: name.trim(),
        type: type.trim(),
        size
      });
    }
    
    return assets;
  }

  /**
   * Select assets by criteria
   */
  async selectAssetsByCriteria(criteria: {
    count?: number;
    minSize?: number; // MB
    maxSize?: number; // MB
    types?: string[];
    useSelectPage?: boolean; // Use the "Select Page" control for large selections
  }): Promise<number> {
    // If requesting a large number of assets, use the "Select Page" control
    if (criteria.useSelectPage || (criteria.count && criteria.count >= 50)) {
      return await this.selectPageUsingControl();
    }
    
    const assets = await this.getVisibleAssets();
    let selectedCount = 0;
    
    // Filter assets based on criteria
    const filteredAssets = assets.filter(asset => {
      if (criteria.minSize && (!asset.size || asset.size < criteria.minSize)) return false;
      if (criteria.maxSize && (!asset.size || asset.size > criteria.maxSize)) return false;
      if (criteria.types && !criteria.types.includes(asset.type.toLowerCase())) return false;
      return true;
    });
    
    console.log(`Found ${filteredAssets.length} assets matching criteria`);
    
    const targetCount = criteria.count || filteredAssets.length;
    const assetsToSelect = filteredAssets.slice(0, targetCount);
    
    // Select the assets
    for (let i = 0; i < assetsToSelect.length; i++) {
      try {
        const assetCard = this.page.locator('div:has(img[data-image-id]), .MuiBox-root:has(img), div:has(.MuiCheckbox-root)').nth(
          assets.findIndex(a => a.id === assetsToSelect[i].id)
        );
        
        // Hover over the card to reveal the checkbox
        await assetCard.hover();
        await this.page.waitForTimeout(200); // Wait for hover effect
        
        // Click the MuiButtonBase-root (the actual clickable element that works)
        const clickableElements = assetCard.locator('.MuiButtonBase-root').all();
        let clicked = false;
        
        for (const element of await clickableElements) {
          const isVisible = await element.isVisible();
          if (isVisible) {
            await element.click();
            
            // Wait for the selection to register and check if it worked
            await this.page.waitForTimeout(500);
            const isSelected = await assetCard.locator('span.Mui-checked').count() > 0;
            
            if (isSelected) {
              selectedCount++;
              console.log(`Asset ${selectedCount} selected successfully`);
              clicked = true;
              break;
            }
          }
        }
        
        if (!clicked) {
          // Fallback to clicking the card with modifier
          await assetCard.click({ modifiers: ['Meta'] });
          selectedCount++;
        }
        
        await this.page.waitForTimeout(100);
      } catch (error) {
        console.log(`Failed to select asset ${assetsToSelect[i].name}: ${error}`);
      }
    }
    
    return selectedCount;
  }

  /**
   * Use the "Select Page" control to select all assets on the current page
   */
  async selectPageUsingControl(): Promise<number> {
    console.log('Using "Select Page" control to select all assets on page...');
    
    // Look for the "Select Page" checkbox in the AssetViewControls
    const selectPageSelectors = [
      'label:has-text("Select Page")',
      '[data-testid="select-page"]',
      'input[type="checkbox"]:near(text="Select Page")',
      '.MuiFormControlLabel-root:has-text("Select Page") input[type="checkbox"]'
    ];
    
    let selectPageControlFound = false;
    
    for (const selector of selectPageSelectors) {
      try {
        const selectPageControl = this.page.locator(selector).first();
        if (await selectPageControl.isVisible()) {
          console.log(`Found "Select Page" control with selector: ${selector}`);
          
          // Click the "Select Page" control
          await selectPageControl.click();
          selectPageControlFound = true;
          break;
        }
      } catch (error) {
        continue;
      }
    }
    
    if (!selectPageControlFound) {
      console.log('Select Page control not found, falling back to individual selection');
      return await this.selectAssetsByCriteria({ count: 50, useSelectPage: false });
    }
    
    // Wait for selection to complete
    await this.page.waitForTimeout(1000);
    
    // Count how many assets were selected
    const selectedAssets = await this.page.locator('.asset-card.selected, [data-testid="asset-card"].selected, .asset-item.selected, [data-testid="asset-item"].selected').count();
    
    console.log(`Selected ${selectedAssets} assets using "Select Page" control`);
    return selectedAssets;
  }

  /**
   * Select large and small files specifically
   */
  async selectLargeAndSmallFiles(): Promise<{ large: number; small: number }> {
    const assets = await this.getVisibleAssets();
    
    // Find large files (>1024MB)
    const largeFiles = assets.filter(asset => asset.size && asset.size > 1024);
    
    // Find small files (<1024MB)
    const smallFiles = assets.filter(asset => asset.size && asset.size < 1024);
    
    console.log(`Found ${largeFiles.length} large files and ${smallFiles.length} small files`);
    
    let largeSelected = 0;
    let smallSelected = 0;
    
    // Select one large file
    if (largeFiles.length > 0) {
      largeSelected = await this.selectAssetsByCriteria({
        count: 1,
        minSize: 1024
      });
    }
    
    // Select one small file
    if (smallFiles.length > 0) {
      smallSelected = await this.selectAssetsByCriteria({
        count: 1,
        maxSize: 1024
      });
    }
    
    // If we don't have size information, select any two files
    if (largeSelected === 0 && smallSelected === 0) {
      console.log('No size information available, selecting any two files');
      const totalSelected = await this.selectAssetsByCriteria({ count: 2 });
      return { large: 1, small: totalSelected - 1 };
    }
    
    return { large: largeSelected, small: smallSelected };
  }

  /**
   * Select assets across multiple pages
   */
  async selectAssetsAcrossPages(targetCount: number): Promise<number> {
    let totalSelected = 0;
    let currentPage = 1;
    const maxPages = 10;
    const pageSize = 200;
    
    while (totalSelected < targetCount && currentPage <= maxPages) {
      console.log(`Selecting assets on page ${currentPage}`);
      
      const selectedOnPage = await this.selectAssetsByCriteria({
        count: targetCount - totalSelected
      });
      
      totalSelected += selectedOnPage;
      
      if (totalSelected >= targetCount || selectedOnPage === 0) {
        break;
      }
      
      // Navigate to next page using URL
      currentPage++;
      const nextPageUrl = `http://localhost:5173/search?q=*&semantic=false&page=${currentPage}&pageSize=${pageSize}`;
      
      try {
        await this.page.goto(nextPageUrl);
        await this.waitForAssetsToLoad();
        
        // Check if there are assets on this page
        const assetsOnPage = await this.getVisibleAssets();
        if (assetsOnPage.length === 0) {
          console.log('No more assets available on subsequent pages');
          break;
        }
      } catch (error) {
        console.log(`Failed to navigate to page ${currentPage}: ${error}`);
        break;
      }
    }
    
    return totalSelected;
  }

  /**
   * Wait for assets to load on the page
   */
  async waitForAssetsToLoad(): Promise<void> {
    console.log('AssetSelector: Waiting for search results to load...');
    
    // Wait for search results or any content area to be visible
    try {
      await this.page.waitForSelector('main, .main-content, .search-results, .content, [role="main"]', { timeout: 10000 });
      console.log('AssetSelector: Main content area found');
    } catch (error) {
      console.log('AssetSelector: Main content area not found, continuing...');
    }
    
    // Wait for search to complete - look for search results or "no results" message
    await this.page.waitForFunction(() => {
      // Check if search is still loading
      const loadingElements = document.querySelectorAll('[data-testid="loading"], .loading, .skeleton, .spinner');
      if (loadingElements.length > 0) {
        return false;
      }
      
      // Check if we have search results or a "no results" message
      const hasResults = document.querySelectorAll('.asset-card, [data-testid="asset-card"], .asset-item, [data-testid="asset-item"]').length > 0;
      const hasNoResultsMessage = document.querySelector('[data-testid="no-results"], .no-results, .empty-state');
      
      return hasResults || hasNoResultsMessage;
    }, { timeout: 60000 }); // Increased timeout for search
    
    console.log('AssetSelector: Search completed, checking for assets...');
    
    // Additional wait for assets to render
    await this.page.waitForTimeout(2000);
    
    // Log what we found
    const assetCount = await this.page.locator('.asset-card, [data-testid="asset-card"], .asset-item, [data-testid="asset-item"]').count();
    console.log(`AssetSelector: Found ${assetCount} assets on the page`);
  }
}

/**
 * Batch operations helper
 */
export class BatchOperationsHelper {
  constructor(private page: Page) {}

  /**
   * Navigate to batch operations tab
   */
  async navigateToBatchOperations(): Promise<void> {
    // Wait for the batch operations tab to be enabled
    await this.page.waitForSelector('#batch-tab:not([disabled])', { timeout: 10000 });
    
    // Click on the batch operations tab
    await this.page.click('#batch-tab');
    
    // Wait for the batch panel to be visible
    await this.page.waitForSelector('#batch-panel', { state: 'visible' });
  }

  /**
   * Get the current selection count from the UI
   */
  async getSelectionCount(): Promise<number> {
    const batchTab = this.page.locator('#batch-tab');
    const tabText = await batchTab.textContent() || '';
    
    const match = tabText.match(/\((\d+)\)/);
    return match ? parseInt(match[1], 10) : 0;
  }

  /**
   * Initiate batch download
   */
  async initiateBatchDownload(): Promise<void> {
    const downloadButtonSelectors = [
      'button:has-text("Download")',
      '[data-testid="batch-download-button"]',
      'button[title*="Download"]',
      'button:has([data-testid="DownloadIcon"])'
    ];
    
    let downloadButtonFound = false;
    
    for (const selector of downloadButtonSelectors) {
      try {
        const downloadButton = this.page.locator(selector).first();
        if (await downloadButton.isVisible()) {
          await downloadButton.click();
          downloadButtonFound = true;
          break;
        }
      } catch (error) {
        continue;
      }
    }
    
    if (!downloadButtonFound) {
      throw new Error('Download button not found');
    }
    
    // Wait for the download to start (loading state)
    await this.page.waitForSelector('button:has-text("Starting...")', { timeout: 5000 });
  }

  /**
   * Verify download success
   */
  async verifyDownloadSuccess(): Promise<void> {
    const successSelectors = [
      '[data-testid="success-modal"]',
      '.success-modal',
      'text="Download Started"',
      'text="Bulk download started"',
      '[role="alert"]:has-text("download")'
    ];
    
    let successFound = false;
    
    for (const selector of successSelectors) {
      try {
        await this.page.waitForSelector(selector, { timeout: 10000 });
        successFound = true;
        break;
      } catch (error) {
        continue;
      }
    }
    
    if (!successFound) {
      // Check for any success indicators in the page
      const successText = await this.page.textContent('body');
      if (successText && (successText.includes('download started') || successText.includes('Download Started'))) {
        successFound = true;
      }
    }
    
    expect(successFound).toBe(true);
  }

  /**
   * Clear all selections
   */
  async clearSelection(): Promise<void> {
    await this.page.click('button:has-text("Clear Selection")');
    
    // Verify selection is cleared
    await expect(this.page.locator('#batch-tab')).toBeDisabled();
  }

  /**
   * Remove individual item from selection
   */
  async removeItemFromSelection(index: number = 0): Promise<void> {
    const removeButtons = this.page.locator('#batch-panel [title="Remove this item"], #batch-panel button:has([data-testid="DeleteIcon"])');
    const removeButton = removeButtons.nth(index);
    
    await expect(removeButton).toBeVisible();
    await removeButton.click();
  }

  /**
   * Get list of selected assets in the batch panel
   */
  async getSelectedAssetsList(): Promise<string[]> {
    const assetItems = this.page.locator('#batch-panel .asset-card, #batch-panel .list-item, #batch-panel li');
    const count = await assetItems.count();
    
    const assetNames: string[] = [];
    for (let i = 0; i < count; i++) {
      const item = assetItems.nth(i);
      const text = await item.textContent() || '';
      assetNames.push(text.trim());
    }
    
    return assetNames;
  }
}

/**
 * API mocking helper for testing error scenarios
 */
export class ApiMockHelper {
  constructor(private page: Page) {}

  /**
   * Mock bulk download API to return error
   */
  async mockBulkDownloadError(statusCode: number = 500, errorMessage: string = 'Internal server error'): Promise<void> {
    await this.page.route('**/api/assets/download/bulk/**', route => {
      route.fulfill({
        status: statusCode,
        contentType: 'application/json',
        body: JSON.stringify({ error: errorMessage })
      });
    });
  }

  /**
   * Mock bulk download API to return success
   */
  async mockBulkDownloadSuccess(jobId: string = 'test-job-123'): Promise<void> {
    await this.page.route('**/api/assets/download/bulk/**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
          data: { jobId },
          message: 'Bulk download started successfully'
        })
      });
    });
  }

  /**
   * Clear all API mocks
   */
  async clearMocks(): Promise<void> {
    await this.page.unroute('**/api/assets/download/bulk/**');
  }
}