/**
 * Cognito Service Adapter for tag-based user pool discovery
 * Implements the ServiceAdapter interface for AWS Cognito Identity Provider
 *
 * Note: This implementation requires the following AWS SDK packages to be installed:
 * - @aws-sdk/client-cognito-identity-provider
 * - @aws-sdk/client-resource-groups-tagging-api
 */

import {
  ServiceAdapter,
  DiscoveredResource,
  AWSResourceType,
  ResourceDiscoveryConfig,
} from "./aws-resource-finder.js";
import { TagFilter } from "./tag-matcher.js";

export interface CognitoUserPool extends DiscoveredResource {
  resourceType: "cognito-user-pool";
  clients: CognitoUserPoolClient[];
  passwordPolicy?: any;
  status: string;
}

export interface CognitoUserPoolClient {
  id: string;
  name: string;
  userPoolId: string;
}

/**
 * AWS Cognito service adapter implementing tag-based discovery
 * This is a placeholder implementation that will be completed when AWS SDK packages are installed
 */
export class CognitoServiceAdapter implements ServiceAdapter {
  private config: ResourceDiscoveryConfig;

  constructor(config: ResourceDiscoveryConfig) {
    this.config = config;
    console.log(`[CognitoAdapter] Initialized for region: ${config.region}`);
  }

  /**
   * Get the resource type this adapter handles
   */
  getResourceType(): AWSResourceType {
    return "cognito-user-pool";
  }

  /**
   * Discover Cognito user pools using tag-based filtering
   * TODO: Implement with actual AWS SDK when packages are installed
   */
  async discoverResources(filters: TagFilter[]): Promise<CognitoUserPool[]> {
    console.log(
      `[CognitoAdapter] Discovering user pools with filters:`,
      filters,
    );

    // Since AWS SDK packages are not installed, use fallback discovery immediately
    console.log(
      `[CognitoAdapter] Using fallback discovery - AWS SDK packages not installed`,
    );

    return await this.fallbackDiscovery(filters);
  }

  /**
   * Validate that a discovered resource is accessible and valid
   */
  async validateResource(resource: DiscoveredResource): Promise<boolean> {
    if (resource.resourceType !== "cognito-user-pool") {
      return false;
    }

    console.log(`[CognitoAdapter] Validating user pool: ${resource.id}`);

    // Placeholder validation - will be replaced with actual AWS SDK calls
    return (
      resource.id.startsWith("us-east-1_") ||
      resource.id.startsWith("us-west-2_")
    );
  }

  /**
   * Create a test user in the specified user pool and add to superAdministrators group
   */
  async createTestUser(
    userPoolId: string,
    username: string,
    password: string,
    email: string,
  ): Promise<void> {
    console.log(
      `[CognitoAdapter] Creating test user: ${username} in pool ${userPoolId}`,
    );

    try {
      // Use AWS CLI to create user
      const { execSync } = await import("child_process");

      // Build AWS CLI command for user creation - only add profile if it's not 'default'
      let createUserCommand = `aws cognito-idp admin-create-user --user-pool-id ${userPoolId} --username '${username}' --user-attributes Name=email,Value='${email}' Name=email_verified,Value=true --message-action SUPPRESS --region ${this.config.region}`;
      if (process.env.AWS_PROFILE && process.env.AWS_PROFILE !== "default") {
        createUserCommand = `aws cognito-idp admin-create-user --user-pool-id ${userPoolId} --username '${username}' --user-attributes Name=email,Value='${email}' Name=email_verified,Value=true --message-action SUPPRESS --profile ${process.env.AWS_PROFILE} --region ${this.config.region}`;
      }

      console.log(
        `[CognitoAdapter] Creating user with command: ${createUserCommand}`,
      );
      execSync(createUserCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 60000, // 60 second timeout
      });

      // Set permanent password - use proper shell escaping
      const escapeShellArg = (arg: string): string => {
        // Escape single quotes by ending the quoted string, adding an escaped quote, and starting a new quoted string
        return `'${arg.replace(/'/g, "'\"'\"'")}'`;
      };

      let setPasswordCommand = `aws cognito-idp admin-set-user-password --user-pool-id ${escapeShellArg(userPoolId)} --username ${escapeShellArg(username)} --password ${escapeShellArg(password)} --permanent --region ${this.config.region}`; // pragma: allowlist secret
      if (process.env.AWS_PROFILE && process.env.AWS_PROFILE !== "default") {
        setPasswordCommand = `aws cognito-idp admin-set-user-password --user-pool-id ${escapeShellArg(userPoolId)} --username ${escapeShellArg(username)} --password ${escapeShellArg(password)} --permanent --profile ${process.env.AWS_PROFILE} --region ${this.config.region}`; // pragma: allowlist secret
      }

      console.log(
        `[CognitoAdapter] Setting permanent password for user: ${username}`,
      );
      execSync(setPasswordCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 60000, // 60 second timeout
      });

      // Add user to superAdministrators group
      await this.addUserToGroup(userPoolId, username, "superAdministrators");

      console.log(
        `[CognitoAdapter] Successfully created user ${username} and added to superAdministrators group`,
      );
    } catch (error: any) {
      console.error(
        `[CognitoAdapter] Failed to create user ${username}:`,
        error.message,
      );
      throw error;
    }
  }

  /**
   * Add a user to a Cognito group
   */
  async addUserToGroup(
    userPoolId: string,
    username: string,
    groupName: string,
  ): Promise<void> {
    console.log(
      `[CognitoAdapter] Adding user ${username} to group ${groupName} in pool ${userPoolId}`,
    );

    try {
      const { execSync } = await import("child_process");

      // Build AWS CLI command for adding user to group - only add profile if it's not 'default'
      let addToGroupCommand = `aws cognito-idp admin-add-user-to-group --user-pool-id ${userPoolId} --username '${username}' --group-name ${groupName} --region ${this.config.region}`;
      if (process.env.AWS_PROFILE && process.env.AWS_PROFILE !== "default") {
        addToGroupCommand = `aws cognito-idp admin-add-user-to-group --user-pool-id ${userPoolId} --username '${username}' --group-name ${groupName} --profile ${process.env.AWS_PROFILE} --region ${this.config.region}`;
      }

      console.log(
        `[CognitoAdapter] Adding user to group with command: ${addToGroupCommand}`,
      );
      execSync(addToGroupCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 60000, // 60 second timeout
      });

      console.log(
        `[CognitoAdapter] Successfully added user ${username} to group ${groupName}`,
      );
    } catch (error: any) {
      console.error(
        `[CognitoAdapter] Failed to add user ${username} to group ${groupName}:`,
        error.message,
      );
      throw error;
    }
  }

  /**
   * Delete a test user from the specified user pool
   * TODO: Implement with actual AWS SDK when packages are installed
   */
  async deleteTestUser(userPoolId: string, username: string): Promise<void> {
    console.log(
      `[CognitoAdapter] Deleting test user: ${username} from pool ${userPoolId}`,
    );
    console.warn(
      `[CognitoAdapter] Placeholder implementation - would delete user with AWS SDK`,
    );

    // Placeholder - actual implementation would use AdminDeleteUserCommand
  }

  /**
   * Get user pool password policy
   * TODO: Implement with actual AWS SDK when packages are installed
   */
  async getUserPoolPasswordPolicy(userPoolId: string): Promise<any> {
    console.log(
      `[CognitoAdapter] Getting password policy for pool: ${userPoolId}`,
    );
    console.warn(
      `[CognitoAdapter] Placeholder implementation - would fetch policy with AWS SDK`,
    );

    // Return mock password policy
    return {
      PasswordPolicy: {
        MinimumLength: 8,
        RequireUppercase: true,
        RequireLowercase: true,
        RequireNumbers: true,
        RequireSymbols: true,
      },
    };
  }

  /**
   * Fallback discovery using AWS CLI to find real user pools
   * This method provides backward compatibility with existing patterns
   */
  async fallbackDiscovery(filters: TagFilter[]): Promise<CognitoUserPool[]> {
    console.log(`[CognitoAdapter] Using fallback discovery method`);

    // Look for Application filter to determine name pattern
    const applicationFilter = filters.find((f) => f.key === "Application");
    const searchPattern = applicationFilter?.values[0] || "medialake";

    console.log(
      `[CognitoAdapter] Searching for user pools containing: ${searchPattern}`,
    );

    try {
      // Use AWS CLI to discover real user pools
      const { execSync } = await import("child_process");

      // Build AWS CLI command - only add profile if it's not 'default'
      let awsCommand = `aws cognito-idp list-user-pools --max-results 50 --region ${this.config.region}`;
      if (process.env.AWS_PROFILE && process.env.AWS_PROFILE !== "default") {
        awsCommand = `aws cognito-idp list-user-pools --max-results 50 --profile ${process.env.AWS_PROFILE} --region ${this.config.region}`;
      }

      const result = execSync(awsCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 60000, // 60 second timeout
      });

      const userPools = JSON.parse(result);
      const mediaLakePool = userPools.UserPools?.find((pool: any) =>
        pool.Name?.toLowerCase().includes(searchPattern.toLowerCase()),
      );

      if (!mediaLakePool) {
        console.warn(
          `[CognitoAdapter] No user pool found containing: ${searchPattern}`,
        );
        return [];
      }

      console.log(
        `[CognitoAdapter] Found user pool: ${mediaLakePool.Name} (${mediaLakePool.Id})`,
      );

      // Get user pool clients
      let clientsCommand = `aws cognito-idp list-user-pool-clients --user-pool-id ${mediaLakePool.Id} --region ${this.config.region}`;
      if (process.env.AWS_PROFILE && process.env.AWS_PROFILE !== "default") {
        clientsCommand = `aws cognito-idp list-user-pool-clients --user-pool-id ${mediaLakePool.Id} --profile ${process.env.AWS_PROFILE} --region ${this.config.region}`;
      }

      const clientsResult = execSync(clientsCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 15000, // 15 second timeout
      });

      const clients = JSON.parse(clientsResult);
      const client = clients.UserPoolClients?.[0];

      if (!client) {
        console.warn(
          `[CognitoAdapter] No client found for user pool: ${mediaLakePool.Id}`,
        );
        return [];
      }

      // Create CognitoUserPool object with real data
      const discoveredPool: CognitoUserPool = {
        id: mediaLakePool.Id,
        name: mediaLakePool.Name,
        arn: `arn:aws:cognito-idp:${this.config.region}:123456789:userpool/${mediaLakePool.Id}`,
        tags: {
          Application: searchPattern,
          Environment: "dev",
          DiscoveryMethod: "fallback",
        },
        resourceType: "cognito-user-pool",
        region: this.config.region,
        discoveredAt: new Date(),
        clients: [
          {
            id: client.ClientId,
            name: client.ClientName || "medialake-web-client",
            userPoolId: mediaLakePool.Id,
          },
        ],
        status: "ACTIVE",
      };

      return [discoveredPool];
    } catch (error: any) {
      console.error(
        `[CognitoAdapter] Fallback discovery failed:`,
        error.message,
      );
      return [];
    }
  }

  /**
   * Cleanup resources and connections
   */
  async cleanup(): Promise<void> {
    console.log(`[CognitoAdapter] Cleaning up Cognito service adapter...`);
    // AWS SDK clients don't require explicit cleanup in v3
  }
}

/**
 * Factory function to create CognitoServiceAdapter
 */
export function createCognitoServiceAdapter(
  config: ResourceDiscoveryConfig,
): CognitoServiceAdapter {
  return new CognitoServiceAdapter(config);
}
