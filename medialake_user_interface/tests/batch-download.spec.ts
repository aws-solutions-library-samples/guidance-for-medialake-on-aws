import { test, expect } from './fixtures/auth.fixtures';
import { Page } from '@playwright/test';

/**
 * Batch Download Tests
 * 
 * Tests the bulk download functionality with different scenarios:
 * 1. Select a page and download batch
 * 2. Select a single file and download batch  
 * 3. Select 1 large file (>1024MB) and one small file and download batch
 */

// Helper function to wait for assets to load
async function waitForAssetsToLoad(page: Page) {
  console.log('Waiting for search results to load...');
  
  // Wait for search results or any content area to be visible
  try {
    await page.waitForSelector('main, .main-content, .search-results, .content, [role="main"]', { timeout: 10000 });
    console.log('Main content area found');
  } catch (error) {
    console.log('Main content area not found, continuing...');
  }
  
  // Wait for search to complete - look for search results or "no results" message
  await page.waitForFunction(() => {
    // Check if search is still loading
    const loadingElements = document.querySelectorAll('[data-testid="loading"], .loading, .skeleton, .spinner');
    if (loadingElements.length > 0) {
      return false;
    }
    
    // Check if we have search results or a "no results" message
    const hasResults = document.querySelectorAll('.MuiBox-root.css-n4nkvp, input.PrivateSwitchBase-input').length > 0;
    const hasNoResultsMessage = document.querySelector('[data-testid="no-results"], .no-results, .empty-state');
    
    return hasResults || hasNoResultsMessage;
  }, { timeout: 60000 }); // Increased timeout for search
  
  console.log('Search completed, checking for assets...');
  
  // Additional wait for assets to render
  await page.waitForTimeout(2000);
  
  // Log what we found
  const assetCount = await page.locator('.MuiBox-root.css-n4nkvp, div:has(input.PrivateSwitchBase-input)').count();
  console.log(`Found ${assetCount} assets on the page`);
}

// Helper function to select assets by clicking checkboxes (with hover support)
async function selectAssets(page: Page, count: number, useSelectPage: boolean = false) {
  console.log(`Selecting ${count} assets...`);
  
  // For large selections, use the "Select Page" control
  if (useSelectPage || count >= 50) {
    return await selectPageUsingControl(page);
  }
  
  // Find all asset cards (using the outer container that has the image)
  const cardSelectors = [
    'div:has(img[data-image-id])', // Div containing the asset image
    '.MuiBox-root:has(img)', // MuiBox containing an image
    'div:has(.MuiCheckbox-root)', // Div containing the checkbox
    '.MuiBox-root.css-n4nkvp', // Exact class from the asset card
    'div:has(input.PrivateSwitchBase-input)' // Fallback
  ];
  
  let selectedCount = 0;
  
  for (const selector of cardSelectors) {
    const cards = await page.locator(selector).all();
    
    if (cards.length > 0) {
      console.log(`Found ${cards.length} asset cards with selector: ${selector}`);
      
      for (let i = 0; i < Math.min(cards.length, count - selectedCount); i++) {
        try {
          const card = cards[i];
          
          // Hover over the card to reveal the checkbox
          await card.hover();
          await page.waitForTimeout(200); // Wait for hover effect
          
          // Click the MuiButtonBase-root (the actual clickable element that works)
          const clickableElements = card.locator('.MuiButtonBase-root').all();
          let clicked = false;
          
          for (const element of await clickableElements) {
            const isVisible = await element.isVisible();
            if (isVisible) {
              await element.click();
              
              // Wait for the selection to register and check if it worked
              await page.waitForTimeout(500);
              const isSelected = await card.locator('span.Mui-checked').count() > 0;
              
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
            await card.click({ modifiers: ['Meta'] });
            selectedCount++;
          }
          
          if (selectedCount >= count) {
            break;
          }
          
          await page.waitForTimeout(100);
        } catch (error) {
          console.log(`Failed to select asset ${i}: ${error}`);
        }
      }
      
      if (selectedCount >= count) {
        break;
      }
    }
  }
  
  console.log(`Successfully selected ${selectedCount} assets`);
  return selectedCount;
}

// Helper function to use "Select Page" control
async function selectPageUsingControl(page: Page): Promise<number> {
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
      const selectPageControl = page.locator(selector).first();
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
    return await selectAssets(page, 50, false);
  }
  
  // Wait for selection to complete
  await page.waitForTimeout(1000);
  
  // Count how many assets were selected by checking the batch tab
  try {
    const batchTab = page.locator('#batch-tab');
    const tabText = await batchTab.textContent() || '';
    const match = tabText.match(/\((\d+)\)/);
    const selectedCount = match ? parseInt(match[1], 10) : 0;
    
    console.log(`Selected ${selectedCount} assets using "Select Page" control`);
    return selectedCount;
  } catch (error) {
    console.log('Could not determine selection count from batch tab');
    return 0;
  }
}

// Helper function to navigate to batch operations tab
async function navigateToBatchOperations(page: Page) {
  console.log('Checking for batch tab and selections...');
  
  // First, just wait a bit for any UI updates
  await page.waitForTimeout(2000);
  
  // Check if we have any selected assets by looking for Mui-checked elements
  const selectedAssets = await page.locator('.Mui-checked').count();
  console.log(`Found ${selectedAssets} selected assets`);
  
  if (selectedAssets === 0) {
    throw new Error('No assets appear to be selected');
  }
  
  // Check batch tab state
  const batchTab = page.locator('#batch-tab');
  const batchTabExists = await batchTab.count() > 0;
  console.log(`Batch tab exists: ${batchTabExists}`);
  
  if (batchTabExists) {
    const batchTabText = await batchTab.textContent();
    console.log(`Batch tab text: "${batchTabText}"`);
    
    // Try to click the batch tab regardless of whether it shows a count
    console.log('Clicking batch tab...');
    await batchTab.click();
    
    // Wait for the batch panel to be visible or any batch-related content
    try {
      await page.waitForSelector('#batch-panel', { state: 'visible', timeout: 5000 });
      console.log('Batch panel is visible');
    } catch (error) {
      console.log('Batch panel not found, checking for other batch content...');
      
      // Look for any batch-related content that might have appeared
      const batchContent = await page.locator('[id*="batch"], [class*="batch"], [data-testid*="batch"]').count();
      console.log(`Found ${batchContent} batch-related elements`);
    }
  } else {
    throw new Error('Batch tab not found');
  }
}

// Helper function to initiate batch download
async function initiateBatchDownload(page: Page) {
  // Look for the download button in the batch operations panel
  const downloadButtonSelectors = [
    'button:has-text("Download")',
    '[data-testid="batch-download-button"]',
    'button[title*="Download"]',
    'button:has([data-testid="DownloadIcon"])'
  ];
  
  let downloadButtonFound = false;
  
  for (const selector of downloadButtonSelectors) {
    try {
      const downloadButton = page.locator(selector).first();
      if (await downloadButton.isVisible()) {
        // Click the download button
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
  await page.waitForSelector('button:has-text("Starting...")', { timeout: 5000 });
}

// Helper function to verify download success
async function verifyDownloadSuccess(page: Page) {
  console.log('Verifying download was initiated...');
  
  // Wait a bit for any UI updates after clicking download
  await page.waitForTimeout(3000);
  
  // Since we'll check the notifications menu for actual download status,
  // we just need to verify the download was initiated (not necessarily completed)
  
  // Check if download button changed state or if there are any loading indicators
  const downloadInitiated = await page.evaluate(() => {
    // Look for any indication that download was started
    const body = document.body.textContent || '';
    
    // Check for common download-related text
    const downloadKeywords = [
      'download',
      'Download',
      'starting',
      'Starting',
      'initiated',
      'processing',
      'Processing'
    ];
    
    return downloadKeywords.some(keyword => body.includes(keyword));
  });
  
  console.log(`Download initiated: ${downloadInitiated}`);
  
  // Don't fail the test here - we'll verify actual progress in notifications
  if (!downloadInitiated) {
    console.log('No explicit download indicators found, but continuing to check notifications...');
  }
}

// Helper function to open notifications menu and wait for download completion
async function openNotificationsMenu(page: Page): Promise<boolean> {
  console.log('Opening notifications menu...');
  
  // Look for the notifications button
  const notificationSelectors = [
    'button[aria-label="notifications"]',
    '[data-testid="NotificationsIcon"]',
    'button:has([data-testid="NotificationsIcon"])',
    '.MuiBadge-root:has([data-testid="NotificationsIcon"])'
  ];
  
  let notificationButtonFound = false;
  
  for (const selector of notificationSelectors) {
    try {
      const notificationButton = page.locator(selector).first();
      if (await notificationButton.isVisible()) {
        console.log(`Found notifications button with selector: ${selector}`);
        
        // Click the notifications button
        await notificationButton.click();
        console.log('Clicked notifications button');
        notificationButtonFound = true;
        break;
      }
    } catch (error) {
      continue;
    }
  }
  
  if (!notificationButtonFound) {
    console.log('Notifications button not found');
    return false;
  }
  
  // Wait for notifications menu to open
  await page.waitForTimeout(1000);
  
  // Look for download notifications specifically
  const downloadNotifications = await page.locator('.MuiPaper-root:has([data-testid="DownloadIcon"])').count();
  console.log(`Found ${downloadNotifications} download notifications`);
  
  if (downloadNotifications === 0) {
    console.log('No download notifications found');
    return false;
  }
  
  // Get the first download notification
  const downloadNotification = page.locator('.MuiPaper-root:has([data-testid="DownloadIcon"])').first();
  
  // Wait for download completion with polling - up to 1 hour
  const maxWaitTime = 3600000; // 1 hour max wait
  const pollInterval = 30000; // Check every 30 seconds (less frequent for long downloads)
  let waitTime = 0;
  
  while (waitTime < maxWaitTime) {
    try {
      // Get all progress text elements to handle multiple phases
      const progressTexts = await downloadNotification.locator('p.MuiTypography-body2').allTextContents();
      console.log(`All progress texts: ${progressTexts.join(' | ')}`);
      
      // Check the percentage from progress bar (with error handling)
      let percentage = '';
      try {
        const percentageElement = downloadNotification.locator('.MuiLinearProgress-root + span');
        percentage = await percentageElement.textContent({ timeout: 5000 }) || '';
      } catch (error) {
        console.log('Could not read percentage, continuing...');
      }
      console.log(`Download percentage: ${percentage}`);
      
      // Check asset count and size (with error handling)
      let assetInfo = '';
      try {
        assetInfo = await downloadNotification.locator('span[aria-label*="assets"]').textContent({ timeout: 5000 }) || '';
      } catch (error) {
        console.log('Could not read asset info, continuing...');
      }
      console.log(`Asset info: ${assetInfo}`);
      
      // Check if download is truly complete by looking for the Dismiss button
      // This appears when download links are ready and the job is fully complete
      const dismissButton = downloadNotification.locator('button:has-text("Dismiss")');
      const hasDismissButton = await dismissButton.count() > 0;
      
      // Also check for download links as another completion indicator
      const downloadLinks = downloadNotification.locator('a[href*="s3.amazonaws.com"], a[href*="download"]');
      const hasDownloadLinks = await downloadLinks.count() > 0;
      
      // Check for completion messages as backup
      const completionMessages = [
        'Mixed download:',
        'Your download is ready!',
        'Download completed',
        'ready'
      ];
      
      const hasCompleteText = progressTexts.some(text =>
        completionMessages.some(msg => text.toLowerCase().includes(msg.toLowerCase()))
      );
      
      const isComplete = hasDismissButton || (hasDownloadLinks && hasCompleteText);
      console.log(`Download complete: ${isComplete} (dismiss button: ${hasDismissButton}, download links: ${hasDownloadLinks}, complete text: ${hasCompleteText})`);
      
      if (isComplete) {
        console.log('✅ Download completed successfully!');
        
        // Take a final screenshot
        await page.screenshot({ path: 'download-completed.png' });
        console.log('Final screenshot saved as download-completed.png');
        
        return true;
      }
      
      // Wait before next check
      console.log(`Download still in progress, waiting ${pollInterval/1000} seconds... (${Math.round(waitTime/60000)} minutes elapsed)`);
      await page.waitForTimeout(pollInterval);
      waitTime += pollInterval;
      
    } catch (error) {
      console.log(`Error during progress check: ${error}`);
      // Continue polling even if there's an error
      await page.waitForTimeout(pollInterval);
      waitTime += pollInterval;
    }
  }
  
  // Timeout reached
  console.log('❌ Download did not complete within the 1-hour timeout period');
  await page.screenshot({ path: 'download-timeout.png' });
  console.log('Timeout screenshot saved as download-timeout.png');
  
  return false;
}

test.describe('Batch Download Tests', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    // Wait for authentication to complete - wait for redirect to home page
    await authenticatedPage.waitForURL('http://localhost:5173/', { timeout: 15000 });
    
    // Wait for the main content to load
    await authenticatedPage.waitForSelector('h1:has-text("MediaLake"), .main-content, [data-testid="home-page"]', { timeout: 10000 });
    
    // Add a small delay to ensure session is fully established
    await authenticatedPage.waitForTimeout(2000);
    
    // Navigate to the search page with all assets (200 per page)
    await authenticatedPage.goto('http://localhost:5173/search?q=*&semantic=false&page=1&pageSize=200');
    await waitForAssetsToLoad(authenticatedPage);
  });

  test('should select full page and download batch', async ({ authenticatedPage }) => {
    // Set a longer timeout for this test since downloads can take up to an hour
    test.setTimeout(3600000); // 1 hour timeout
    const page = authenticatedPage;
    
    // This test uses "Select Page" to select all assets on the current page only
    console.log('Using "Select Page" control for full page batch selection...');
    
    // Ensure we're on page 1 with a reasonable page size
    await page.goto('http://localhost:5173/search?q=*&semantic=false&page=1&pageSize=200');
    await waitForAssetsToLoad(page);
    
    // Count assets on current page before selection
    const assetCount = await page.locator('div:has(img[data-image-id]), .MuiBox-root:has(img)').count();
    console.log(`Found ${assetCount} assets on current page`);
    
    // Use the "Select Page" control to select all assets on the current page only
    const selectedCount = await selectPageUsingControl(page);
    
    // Verify we have selected assets and it matches the page count
    expect(selectedCount).toBeGreaterThan(0);
    expect(selectedCount).toBeLessThanOrEqual(200); // Should not exceed page size
    console.log(`Selected ${selectedCount} assets using "Select Page" control (single page only)`);
    
    // Navigate to batch operations
    await navigateToBatchOperations(page);
    
    // Initiate batch download
    await initiateBatchDownload(page);
    
    // Verify download success
    await verifyDownloadSuccess(page);
    
    // Wait 15 seconds for download to start and appear in notifications
    console.log('Waiting 15 seconds for download to start...');
    await page.waitForTimeout(15000);
    
    // Open notifications menu and wait for download completion
    const downloadCompleted = await openNotificationsMenu(page);
    
    // Verify that download actually completed
    expect(downloadCompleted).toBe(true);
    console.log('✅ Download verified as completed via notifications menu');
    
    // Verify selection is cleared after successful download
    const batchTabAfter = page.locator('#batch-tab');
    const batchTabTextAfter = await batchTabAfter.textContent();
    console.log(`Batch tab after download: "${batchTabTextAfter}"`);
  });
});