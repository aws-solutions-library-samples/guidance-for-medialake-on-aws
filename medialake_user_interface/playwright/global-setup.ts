import { FullConfig } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Global setup to start the development server
async function globalSetup(config: FullConfig) {
  // Get the base URL from the configuration
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:3000';
  
  // Extract port from baseURL
  const port = baseURL.match(/:(\d+)/)?.[1] || '3000';
  
  // Log the startup message
  console.log(`Starting development server on port ${port}...`);
  
  // Start the dev server as a child process
  const server = exec(`npm run dev -- --port ${port}`);
  
  // Store the server process in the global context for teardown
  process.env.SERVER_PID = String(server.pid);
  
  // Wait for the server to be available
  const serverCheckCommand = `npx wait-on ${baseURL} -t 60000`;
  try {
    await execAsync(serverCheckCommand);
    console.log(`Development server is ready on ${baseURL}`);
  } catch (error) {
    console.error('Failed to start development server', error);
    process.exit(1);
  }
}

export default globalSetup; 