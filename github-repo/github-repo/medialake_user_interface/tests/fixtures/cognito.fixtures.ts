import { test as base } from "@playwright/test";
import { execSync } from "child_process";
import * as crypto from "crypto";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const E2E_TEST_EMAIL = "mne-medialake+e2etest@amazon.com";

// Types for our Cognito fixtures
type CognitoFixtures = {
  cognitoTestUser: {
    username: string;
    password: string;
    email: string;
    userPoolId: string;
    userPoolClientId: string;
  };
};

// Helper function to execute AWS CLI commands
function executeAwsCommand(command: string): string {
  try {
    const result = execSync(
      `aws ${command} --profile ${AWS_PROFILE} --region ${AWS_REGION}`,
      {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    return result.trim();
  } catch (error: any) {
    console.error(`AWS CLI command failed: aws ${command}`);
    console.error(`Error: ${error.message}`);
    throw error;
  }
}

// Helper function to generate a secure random password
function generateSecurePassword(passwordPolicy?: any): string {
  // Default to conservative requirements if policy is not available
  const minLength = passwordPolicy?.MinimumLength || 20; // Use 20 as a safe default
  const requireUppercase = passwordPolicy?.RequireUppercase !== false;
  const requireLowercase = passwordPolicy?.RequireLowercase !== false;
  const requireNumbers = passwordPolicy?.RequireNumbers !== false;
  const requireSymbols = passwordPolicy?.RequireSymbols !== false;

  const uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowercase = "abcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  const symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?";

  let password = "";
  let availableChars = "";

  // Add required character types
  if (requireUppercase) {
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    availableChars += uppercase;
  }

  if (requireLowercase) {
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    availableChars += lowercase;
  }

  if (requireNumbers) {
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    availableChars += numbers;
  }

  if (requireSymbols) {
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    availableChars += symbols;
  }

  // If no specific requirements, use all character types
  if (!availableChars) {
    availableChars = uppercase + lowercase + numbers + symbols;
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
  }

  // Fill to minimum length
  while (password.length < minLength) {
    password += availableChars.charAt(
      Math.floor(Math.random() * availableChars.length),
    );
  }

  // Shuffle the password to randomize character positions
  return password
    .split("")
    .sort(() => Math.random() - 0.5)
    .join("");
}

// Helper function to find the user pool ID
function findUserPoolId(): string {
  try {
    console.log("[Cognito Fixture] Finding user pool...");
    const userPoolsOutput = executeAwsCommand(
      "cognito-idp list-user-pools --max-results 50",
    );
    const userPools = JSON.parse(userPoolsOutput);

    // Look for a user pool with 'medialake' in the name
    const mediaLakePool = userPools.UserPools?.find((pool: any) =>
      pool.Name?.toLowerCase().includes("medialake"),
    );

    if (!mediaLakePool) {
      throw new Error("No MediaLake user pool found");
    }

    console.log(
      `[Cognito Fixture] Found user pool: ${mediaLakePool.Name} (${mediaLakePool.Id})`,
    );
    return mediaLakePool.Id;
  } catch (error) {
    console.error("[Cognito Fixture] Error finding user pool:", error);
    throw error;
  }
}

// Helper function to find the user pool client ID
function findUserPoolClientId(userPoolId: string): string {
  try {
    console.log("[Cognito Fixture] Finding user pool client...");
    const clientsOutput = executeAwsCommand(
      `cognito-idp list-user-pool-clients --user-pool-id ${userPoolId}`,
    );
    const clients = JSON.parse(clientsOutput);

    // Get the first client (there should typically be one main client)
    const client = clients.UserPoolClients?.[0];

    if (!client) {
      throw new Error("No user pool client found");
    }

    console.log(
      `[Cognito Fixture] Found user pool client: ${client.ClientName} (${client.ClientId})`,
    );
    return client.ClientId;
  } catch (error) {
    console.error("[Cognito Fixture] Error finding user pool client:", error);
    throw error;
  }
}

// Helper function to get user pool password policy
function getUserPoolPasswordPolicy(userPoolId: string): any {
  try {
    console.log(
      `[Cognito Fixture] Getting password policy for user pool: ${userPoolId}`,
    );
    const policyOutput = executeAwsCommand(
      `cognito-idp describe-user-pool --user-pool-id ${userPoolId}`,
    );
    const userPool = JSON.parse(policyOutput);
    const passwordPolicy = userPool.UserPool?.Policies?.PasswordPolicy;
    console.log(
      `[Cognito Fixture] Password policy:`,
      JSON.stringify(passwordPolicy, null, 2),
    );
    return passwordPolicy;
  } catch (error) {
    console.error("[Cognito Fixture] Error getting password policy:", error);
    return null;
  }
}

// Helper function to create a test user
function createTestUser(
  userPoolId: string,
  username: string,
  password: string,
  email: string,
): void {
  try {
    console.log(`[Cognito Fixture] Creating test user: ${username}`);
    console.log(`[Cognito Fixture] Password length: ${password.length}`);
    console.log(`[Cognito Fixture] Password: ${password}`);

    // Get password policy for debugging
    getUserPoolPasswordPolicy(userPoolId);

    // Create the user with admin privileges
    const createUserCommand = `cognito-idp admin-create-user --user-pool-id ${userPoolId} --username "${username}" --user-attributes Name=email,Value="${email}" Name=email_verified,Value=true --temporary-password "${password}" --message-action SUPPRESS`;
    executeAwsCommand(createUserCommand);

    // Set permanent password
    const setPasswordCommand = `cognito-idp admin-set-user-password --user-pool-id ${userPoolId} --username "${username}" --password "${password}" --permanent`;
    executeAwsCommand(setPasswordCommand);

    console.log(
      `[Cognito Fixture] Test user created successfully: ${username}`,
    );
  } catch (error: any) {
    if (error.message.includes("UsernameExistsException")) {
      console.log(
        `[Cognito Fixture] User ${username} already exists, updating password...`,
      );
      try {
        // Update the existing user's password
        const setPasswordCommand = `cognito-idp admin-set-user-password --user-pool-id ${userPoolId} --username "${username}" --password "${password}" --permanent`;
        executeAwsCommand(setPasswordCommand);
        console.log(
          `[Cognito Fixture] Updated password for existing user: ${username}`,
        );
      } catch (updateError) {
        console.error(
          "[Cognito Fixture] Error updating existing user password:",
          updateError,
        );
        throw updateError;
      }
    } else {
      console.error("[Cognito Fixture] Error creating test user:", error);
      throw error;
    }
  }
}

// Helper function to delete a test user
function deleteTestUser(userPoolId: string, username: string): void {
  try {
    console.log(`[Cognito Fixture] Deleting test user: ${username}`);
    const deleteUserCommand = `cognito-idp admin-delete-user --user-pool-id ${userPoolId} --username "${username}"`;
    executeAwsCommand(deleteUserCommand);
    console.log(
      `[Cognito Fixture] Test user deleted successfully: ${username}`,
    );
  } catch (error: any) {
    if (error.message.includes("UserNotFoundException")) {
      console.log(
        `[Cognito Fixture] User ${username} not found, already deleted or never existed`,
      );
    } else {
      console.error("[Cognito Fixture] Error deleting test user:", error);
      // Don't throw here to avoid failing test cleanup
    }
  }
}

// Extend the base Playwright test fixture
export const test = base.extend<CognitoFixtures>({
  cognitoTestUser: [
    async ({}, use, testInfo) => {
      // Generate unique email for this test run (using email as username)
      const randomId = crypto.randomBytes(4).toString("hex");
      const uniqueEmail = `mne-medialake+e2etest-${testInfo.workerIndex}-${randomId}@amazon.com`;

      console.log(
        `[Cognito Fixture] Setting up test user for worker ${testInfo.workerIndex}`,
      );

      let userPoolId: string | undefined;
      let userPoolClientId: string | undefined;

      try {
        // Find the user pool and client
        userPoolId = findUserPoolId();
        userPoolClientId = findUserPoolClientId(userPoolId);

        // Get password policy and generate appropriate password
        const passwordPolicy = getUserPoolPasswordPolicy(userPoolId);
        const password = generateSecurePassword(passwordPolicy);

        // Create the test user (using email as username)
        createTestUser(userPoolId, uniqueEmail, password, uniqueEmail);

        // Provide the user details to the test
        const testUser = {
          username: uniqueEmail,
          password,
          email: uniqueEmail,
          userPoolId,
          userPoolClientId,
        };

        console.log(`[Cognito Fixture] Test user ready: ${uniqueEmail}`);
        await use(testUser);
      } catch (error) {
        console.error("[Cognito Fixture] Error setting up test user:", error);
        throw error;
      } finally {
        // Cleanup: Delete the test user
        if (userPoolId && uniqueEmail) {
          try {
            deleteTestUser(userPoolId, uniqueEmail);
          } catch (cleanupError) {
            console.error(
              "[Cognito Fixture] Error during cleanup:",
              cleanupError,
            );
            // Don't throw cleanup errors to avoid masking test failures
          }
        }
      }
    },
    { scope: "test" },
  ],
});

export { expect } from "@playwright/test";
