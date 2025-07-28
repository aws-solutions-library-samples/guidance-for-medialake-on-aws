/**
 * Enhanced Cognito Fixtures with Tag-Based Discovery and No-Password-Reset User Creation
 * Extends existing Cognito fixtures to support AWS resource discovery while maintaining backward compatibility
 * Implements permanent password creation without requiring password reset on first login
 */

import { test as base } from "@playwright/test";
import { execSync } from "child_process";
import * as crypto from "crypto";
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "../utils/aws-resource-finder.js";
import {
  CognitoServiceAdapter,
  createCognitoServiceAdapter,
  CognitoUserPool,
} from "../utils/cognito-service-adapter.js";
import { TagFilter, STANDARD_TAG_PATTERNS } from "../utils/tag-matcher.js";

const AWS_REGION =
  process.env.DEPLOY_REGION || process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Enhanced types for Cognito fixtures with discovery capabilities
export interface EnhancedCognitoTestUser {
  username: string;
  password: string;
  email: string;
  userPoolId: string;
  userPoolClientId: string;
  userPool?: CognitoUserPool;
  discoveryMethod: "tag-based" | "name-based" | "fallback";
}

export interface EnhancedCognitoFixtures {
  enhancedCognitoTestUser: EnhancedCognitoTestUser;
  cognitoDiscoveryEngine: ResourceDiscoveryEngine;
  cognitoServiceAdapter: CognitoServiceAdapter;
}

/**
 * Create discovery configuration from environment
 */
function createDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 300000, // 5 minutes
    maxCacheSize: 100,
    enableFallback: true,
  };
}

/**
 * Get standard tag filters for Cognito user pool discovery
 */
function getCognitoTagFilters(): TagFilter[] {
  return [
    STANDARD_TAG_PATTERNS.APPLICATION_TAG,
    {
      key: "Environment",
      values: [ENVIRONMENT],
      operator: "equals",
    },
    STANDARD_TAG_PATTERNS.TESTING_TAG,
  ];
}

/**
 * Helper function to execute AWS CLI commands with enhanced error handling
 */
function executeAwsCommand(command: string): string {
  // Build AWS CLI command - only add profile if it's not 'default'
  let awsCommand = `aws ${command} --region ${AWS_REGION}`;
  if (AWS_PROFILE && AWS_PROFILE !== "default") {
    awsCommand = `aws ${command} --profile ${AWS_PROFILE} --region ${AWS_REGION}`;
  }

  try {
    const result = execSync(awsCommand, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 30000, // 30 second timeout
    });
    return result.trim();
  } catch (error: any) {
    console.error(`[EnhancedCognito] AWS CLI command failed: ${awsCommand}`);
    console.error(`[EnhancedCognito] Error: ${error.message}`);
    throw error;
  }
}

/**
 * Generate secure password based on policy requirements
 */
function generateSecurePassword(passwordPolicy?: any): string {
  // Always use a minimum of 20 characters to avoid AWS policy discrepancies
  // AWS sometimes has stricter requirements than reported
  const policyMinLength = passwordPolicy?.MinimumLength || 20;
  const minLength = Math.max(policyMinLength, 20);
  const requireUppercase = passwordPolicy?.RequireUppercase !== false;
  const requireLowercase = passwordPolicy?.RequireLowercase !== false;
  const requireNumbers = passwordPolicy?.RequireNumbers !== false;
  const requireSymbols = passwordPolicy?.RequireSymbols !== false;

  const uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowercase = "abcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  // Use shell-safe symbols to avoid command parsing issues
  const symbols = "!@#%^&*()_+-=.";

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

/**
 * Enhanced error types for better error handling
 */
class CognitoDiscoveryError extends Error {
  constructor(
    message: string,
    public readonly method: string,
    public readonly originalError?: Error,
  ) {
    super(message);
    this.name = "CognitoDiscoveryError";
  }
}

/**
 * Retry mechanism with exponential backoff
 */
async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000,
  context: string = "operation",
): Promise<T> {
  let lastError: Error;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error: any) {
      lastError = error;

      if (attempt === maxRetries) {
        console.error(
          `[EnhancedCognito] ${context} failed after ${maxRetries} attempts:`,
          error,
        );
        throw error;
      }

      const delay = baseDelay * Math.pow(2, attempt - 1);
      console.warn(
        `[EnhancedCognito] ${context} attempt ${attempt} failed, retrying in ${delay}ms:`,
        error.message,
      );
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError!;
}

/**
 * Discover user pool using tag-based approach with comprehensive fallback mechanisms
 */
async function discoverUserPool(
  discoveryEngine: ResourceDiscoveryEngine,
  serviceAdapter: CognitoServiceAdapter,
): Promise<{
  userPool: CognitoUserPool | null;
  method: "tag-based" | "name-based" | "fallback";
}> {
  console.log("[EnhancedCognito] Starting user pool discovery process...");
  const tagFilters = getCognitoTagFilters();
  console.log(
    "[EnhancedCognito] Tag filters:",
    JSON.stringify(tagFilters, null, 2),
  );

  const discoveryMethods = [
    {
      name: "tag-based",
      operation: async () => {
        console.log(
          "[EnhancedCognito] Attempting tag-based user pool discovery...",
        );
        console.log(
          "[EnhancedCognito] Calling discoveryEngine.discoverByTags...",
        );

        const pools = (await Promise.race([
          discoveryEngine.discoverByTags("cognito-user-pool", tagFilters),
          new Promise((_, reject) =>
            setTimeout(
              () =>
                reject(
                  new Error("Tag-based discovery timeout after 60 seconds"),
                ),
              60000,
            ),
          ),
        ])) as any[];

        console.log(
          `[EnhancedCognito] Tag-based discovery completed. Found ${pools.length} pools`,
        );
        if (pools.length === 0) {
          throw new CognitoDiscoveryError(
            "No user pools found via tag-based discovery",
            "tag-based",
          );
        }
        return pools[0] as CognitoUserPool;
      },
    },
    {
      name: "service-fallback",
      operation: async () => {
        console.log(
          "[EnhancedCognito] Using service adapter fallback discovery...",
        );
        const pools = await serviceAdapter.fallbackDiscovery(tagFilters);
        if (pools.length === 0) {
          throw new CognitoDiscoveryError(
            "No user pools found via service fallback",
            "service-fallback",
          );
        }
        return pools[0];
      },
    },
    {
      name: "legacy-name-based",
      operation: async () => {
        console.log("[EnhancedCognito] Using legacy name-based discovery...");
        const userPoolId = await retryWithBackoff(
          () => Promise.resolve(findUserPoolIdLegacy()),
          2,
          1000,
          "legacy user pool discovery",
        );
        const userPoolClientId = await retryWithBackoff(
          () => Promise.resolve(findUserPoolClientIdLegacy(userPoolId)),
          2,
          1000,
          "legacy client discovery",
        );

        return {
          id: userPoolId,
          name: "medialake-legacy-discovered",
          arn: `arn:aws:cognito-idp:${AWS_REGION}:123456789:userpool/${userPoolId}`,
          tags: {
            Application: "medialake",
            Environment: ENVIRONMENT,
            DiscoveryMethod: "legacy",
          },
          resourceType: "cognito-user-pool" as const,
          region: AWS_REGION,
          discoveredAt: new Date(),
          clients: [
            {
              id: userPoolClientId,
              name: "medialake-web-client",
              userPoolId: userPoolId,
            },
          ],
          status: "ACTIVE",
        } as CognitoUserPool;
      },
    },
  ];

  // Try each discovery method in sequence
  for (const method of discoveryMethods) {
    try {
      const userPool = await retryWithBackoff(
        method.operation,
        2,
        1000,
        `${method.name} discovery`,
      );

      console.log(
        `[EnhancedCognito] Found user pool via ${method.name}: ${userPool.name} (${userPool.id})`,
      );

      // Validate the discovered user pool
      const isValid = await validateUserPool(userPool);
      if (!isValid) {
        console.warn(
          `[EnhancedCognito] User pool ${userPool.id} failed validation, trying next method...`,
        );
        continue;
      }

      return {
        userPool,
        method:
          method.name === "legacy-name-based"
            ? "name-based"
            : method.name === "tag-based"
              ? "tag-based"
              : "fallback",
      };
    } catch (error: any) {
      console.warn(
        `[EnhancedCognito] ${method.name} discovery failed:`,
        error.message,
      );

      // For critical errors, don't continue to next method
      if (
        error.message.includes("AccessDenied") ||
        error.message.includes("InvalidUserPoolConfiguration")
      ) {
        throw new CognitoDiscoveryError(
          `Critical error in ${method.name}: ${error.message}`,
          method.name,
          error,
        );
      }
    }
  }

  throw new CognitoDiscoveryError(
    "All discovery methods failed",
    "all-methods",
  );
}

/**
 * Validate discovered user pool
 */
async function validateUserPool(userPool: CognitoUserPool): Promise<boolean> {
  try {
    // Basic validation checks
    if (!userPool.id || !userPool.id.match(/^[a-zA-Z0-9_-]+$/)) {
      console.warn(
        `[EnhancedCognito] Invalid user pool ID format: ${userPool.id}`,
      );
      return false;
    }

    if (!userPool.clients || userPool.clients.length === 0) {
      console.warn(`[EnhancedCognito] User pool ${userPool.id} has no clients`);
      return false;
    }

    // Additional validation could include AWS API calls to verify pool exists
    // For now, we'll do basic structural validation

    return true;
  } catch (error) {
    console.warn(`[EnhancedCognito] User pool validation failed:`, error);
    return false;
  }
}

/**
 * Legacy user pool discovery function (from original cognito.fixtures.ts)
 */
function findUserPoolIdLegacy(): string {
  try {
    console.log("[EnhancedCognito] Finding user pool using legacy method...");
    const userPoolsOutput = executeAwsCommand(
      "cognito-idp list-user-pools --max-results 50",
    );
    const userPools = JSON.parse(userPoolsOutput);

    const mediaLakePool = userPools.UserPools?.find((pool: any) =>
      pool.Name?.toLowerCase().includes("medialake"),
    );

    if (!mediaLakePool) {
      throw new Error("No MediaLake user pool found");
    }

    console.log(
      `[EnhancedCognito] Found user pool: ${mediaLakePool.Name} (${mediaLakePool.Id})`,
    );
    return mediaLakePool.Id;
  } catch (error) {
    console.error("[EnhancedCognito] Error finding user pool:", error);
    throw error;
  }
}

/**
 * Legacy user pool client discovery function (from original cognito.fixtures.ts)
 */
function findUserPoolClientIdLegacy(userPoolId: string): string {
  try {
    console.log(
      "[EnhancedCognito] Finding user pool client using legacy method...",
    );
    const clientsOutput = executeAwsCommand(
      `cognito-idp list-user-pool-clients --user-pool-id ${userPoolId}`,
    );
    const clients = JSON.parse(clientsOutput);

    const client = clients.UserPoolClients?.[0];

    if (!client) {
      throw new Error("No user pool client found");
    }

    console.log(
      `[EnhancedCognito] Found user pool client: ${client.ClientName} (${client.ClientId})`,
    );
    return client.ClientId;
  } catch (error) {
    console.error("[EnhancedCognito] Error finding user pool client:", error);
    throw error;
  }
}

/**
 * Get user pool password policy
 */
function getUserPoolPasswordPolicy(userPoolId: string): any {
  try {
    console.log(
      `[EnhancedCognito] Getting password policy for user pool: ${userPoolId}`,
    );
    const policyOutput = executeAwsCommand(
      `cognito-idp describe-user-pool --user-pool-id ${userPoolId}`,
    );
    const userPool = JSON.parse(policyOutput);
    const passwordPolicy = userPool.UserPool?.Policies?.PasswordPolicy;
    console.log(
      `[EnhancedCognito] Password policy:`,
      JSON.stringify(passwordPolicy, null, 2),
    );
    return passwordPolicy;
  } catch (error) {
    console.error("[EnhancedCognito] Error getting password policy:", error);
    return null;
  }
}

/**
 * Delete test user
 */
function deleteTestUser(userPoolId: string, username: string): void {
  try {
    console.log(`[EnhancedCognito] Deleting test user: ${username}`);
    const deleteUserCommand = `cognito-idp admin-delete-user --user-pool-id ${userPoolId} --username "${username}"`;
    executeAwsCommand(deleteUserCommand);
    console.log(
      `[EnhancedCognito] Test user deleted successfully: ${username}`,
    );
  } catch (error: any) {
    if (error.message.includes("UserNotFoundException")) {
      console.log(
        `[EnhancedCognito] User ${username} not found, already deleted or never existed`,
      );
    } else {
      console.error("[EnhancedCognito] Error deleting test user:", error);
      // Don't throw here to avoid failing test cleanup
    }
  }
}

// Extend the base Playwright test fixture with enhanced Cognito capabilities
export const test = base.extend<EnhancedCognitoFixtures>({
  /**
   * Discovery engine fixture - test scoped for proper Playwright integration
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  cognitoDiscoveryEngine: async ({ page }, use, testInfo) => {
    const config = createDiscoveryConfig();
    const engine = createResourceDiscoveryEngine(config, testInfo.workerIndex);

    console.log(
      `[EnhancedCognito Worker ${testInfo.workerIndex}] Initializing discovery engine`,
    );

    // Register Cognito service adapter
    const cognitoAdapter = createCognitoServiceAdapter(config);
    engine.registerAdapter(cognitoAdapter);

    // Prefetch Cognito resources
    try {
      const cognitoFilters = getCognitoTagFilters();
      await engine.prefetchResources(cognitoFilters);
    } catch (error) {
      console.warn(
        `[EnhancedCognito Worker ${testInfo.workerIndex}] Prefetch failed:`,
        error,
      );
    }

    await use(engine);

    // Cleanup
    await engine.cleanup();
  },

  /**
   * Cognito service adapter fixture
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  cognitoServiceAdapter: async ({ page }, use) => {
    const config = createDiscoveryConfig();
    const adapter = createCognitoServiceAdapter(config);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * Enhanced Cognito test user with tag-based discovery and permanent password
   */
  enhancedCognitoTestUser: [
    async (
      { cognitoDiscoveryEngine, cognitoServiceAdapter },
      use,
      testInfo,
    ) => {
      // Generate unique email for this test run (using email as username)
      const randomId = crypto.randomBytes(4).toString("hex");
      const uniqueEmail = `mne-medialake+e2etest-${testInfo.workerIndex}-${randomId}@amazon.com`;

      console.log(
        `[EnhancedCognito] Setting up enhanced test user for worker ${testInfo.workerIndex}`,
      );
      console.log(`[EnhancedCognito] Generated unique email: ${uniqueEmail}`);

      let userPool: CognitoUserPool | null = null;
      let discoveryMethod: "tag-based" | "name-based" | "fallback" = "fallback";

      try {
        // Discover user pool using enhanced discovery methods
        console.log(`[EnhancedCognito] Starting user pool discovery...`);
        const discoveryResult = (await Promise.race([
          discoverUserPool(cognitoDiscoveryEngine, cognitoServiceAdapter),
          new Promise((_, reject) =>
            setTimeout(
              () =>
                reject(
                  new Error("User pool discovery timeout after 120 seconds"),
                ),
              120000,
            ),
          ),
        ])) as {
          userPool: CognitoUserPool | null;
          method: "tag-based" | "name-based" | "fallback";
        };

        userPool = discoveryResult.userPool;
        discoveryMethod = discoveryResult.method;
        console.log(
          `[EnhancedCognito] User pool discovery completed: ${userPool?.id} (method: ${discoveryMethod})`,
        );

        if (!userPool) {
          throw new Error("No user pool could be discovered using any method");
        }

        // Get password policy and generate appropriate password
        console.log(
          `[EnhancedCognito] Getting password policy for user pool: ${userPool.id}`,
        );
        const passwordPolicy = getUserPoolPasswordPolicy(userPool.id);
        const password = generateSecurePassword(passwordPolicy);
        console.log(
          `[EnhancedCognito] Generated password with length: ${password.length}`,
        );

        // Create the test user with permanent password and add to superAdministrators group
        console.log(`[EnhancedCognito] Creating test user: ${uniqueEmail}`);
        await Promise.race([
          cognitoServiceAdapter.createTestUser(
            userPool.id,
            uniqueEmail,
            password,
            uniqueEmail,
          ),
          new Promise((_, reject) =>
            setTimeout(
              () => reject(new Error("User creation timeout after 60 seconds")),
              60000,
            ),
          ),
        ]);
        console.log(
          `[EnhancedCognito] Test user created successfully: ${uniqueEmail}`,
        );

        // Get client ID from discovered user pool or fallback to legacy discovery
        let userPoolClientId = userPool.clients[0]?.id;
        if (!userPoolClientId) {
          console.warn(
            "[EnhancedCognito] No client found in discovered pool, using legacy discovery...",
          );
          userPoolClientId = findUserPoolClientIdLegacy(userPool.id);
        }

        // Provide the enhanced user details to the test
        const testUser: EnhancedCognitoTestUser = {
          username: uniqueEmail,
          password,
          email: uniqueEmail,
          userPoolId: userPool.id,
          userPoolClientId,
          userPool,
          discoveryMethod,
        };

        console.log(
          `[EnhancedCognito] Enhanced test user ready: ${uniqueEmail} (discovery: ${discoveryMethod})`,
        );
        await use(testUser);
      } catch (error) {
        console.error(
          "[EnhancedCognito] Error setting up enhanced test user:",
          error,
        );
        throw error;
      } finally {
        // Cleanup: Delete the test user
        if (userPool && uniqueEmail) {
          try {
            deleteTestUser(userPool.id, uniqueEmail);
          } catch (cleanupError) {
            console.error(
              "[EnhancedCognito] Error during cleanup:",
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

// Re-export expect from the base playwright test module
export { expect } from "@playwright/test";

/**
 * Utility functions for enhanced Cognito testing
 */
export const EnhancedCognitoUtils = {
  /**
   * Create custom tag filters for specific test scenarios
   */
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[] {
    return Object.entries(customTags).map(([key, value]) => ({
      key,
      values: [value],
      operator: "equals" as const,
    }));
  },

  /**
   * Validate user pool discovery method
   */
  validateDiscoveryMethod(
    user: EnhancedCognitoTestUser,
    expectedMethod: "tag-based" | "name-based" | "fallback",
  ): boolean {
    return user.discoveryMethod === expectedMethod;
  },

  /**
   * Get user pool information for debugging
   */
  getUserPoolInfo(user: EnhancedCognitoTestUser): any {
    return {
      id: user.userPoolId,
      clientId: user.userPoolClientId,
      discoveryMethod: user.discoveryMethod,
      userPoolName: user.userPool?.name,
      userPoolTags: user.userPool?.tags,
    };
  },
};
