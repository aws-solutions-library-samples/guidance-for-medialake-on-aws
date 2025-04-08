import { FullConfig } from '@playwright/test';
import { execSync } from 'child_process';

// Global teardown to shut down the development server
async function globalTeardown(config: FullConfig) {
  // Get the server PID from the environment
  const serverPID = process.env.SERVER_PID;
  
  if (serverPID) {
    try {
      console.log(`Shutting down development server with PID ${serverPID}`);
      
      // Use different kill commands based on platform
      if (process.platform === 'win32') {
        // Windows
        execSync(`taskkill /F /PID ${serverPID} /T`);
      } else {
        // Unix/macOS
        execSync(`kill -15 ${serverPID}`);
      }
      
      console.log('Development server has been stopped');
    } catch (error) {
      console.error('Failed to stop development server', error);
    }
  }
}

export default globalTeardown; 