---
title: AWS SDK Integration Specification for Tag-Based Resource Discovery
task_id: 1.1
date: 2025-07-27
last_updated: 2025-07-27
status: DRAFT
owner: Architect
---

# AWS SDK Integration Specification for Tag-Based Resource Discovery

## Objective

Define a comprehensive specification for migrating from AWS CLI-based resource discovery to AWS SDK for JavaScript v3, establishing patterns for tag-based resource queries, error handling, authentication, and performance optimization within the MediaLake Playwright testing infrastructure.

## Current State Analysis

### Existing AWS CLI Integration

The current implementation uses [`executeAwsCommand()`](medialake_user_interface/tests/fixtures/cognito.fixtures.ts:21-36) with several characteristics:

```typescript
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
```

**Limitations:**

- Subprocess overhead for each AWS operation
- String-based command construction prone to injection
- Limited error context and type safety
- No built-in retry or pagination support
- Dependency on external AWS CLI installation

## AWS SDK v3 Integration Architecture

### 1. Client Management Strategy

#### Singleton Client Factory

```typescript
import {
  CognitoIdentityProviderClient,
  CloudFrontClient,
  S3Client,
  ResourceGroupsTaggingAPIClient,
} from "@aws-sdk/client-cognito-identity-provider";

interface AWSClientConfig {
  region: string;
  profile?: string;
  credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  };
  maxAttempts?: number;
  requestTimeout?: number;
}

class AWSClientFactory {
  private static clients: Map<string, any> = new Map();
  private static config: AWSClientConfig;

  static initialize(config: AWSClientConfig): void {
    this.config = config;
  }

  static getCognitoClient(): CognitoIdentityProviderClient {
    if (!this.clients.has("cognito")) {
      this.clients.set(
        "cognito",
        new CognitoIdentityProviderClient({
          region: this.config.region,
          credentials: this.config.credentials,
          maxAttempts: this.config.maxAttempts || 3,
          requestHandler: {
            requestTimeout: this.config.requestTimeout || 30000,
          },
        }),
      );
    }
    return this.clients.get("cognito");
  }

  static getCloudFrontClient(): CloudFrontClient {
    if (!this.clients.has("cloudfront")) {
      this.clients.set(
        "cloudfront",
        new CloudFrontClient({
          region: this.config.region,
          credentials: this.config.credentials,
          maxAttempts: this.config.maxAttempts || 3,
        }),
      );
    }
    return this.clients.get("cloudfront");
  }

  static getResourceGroupsClient(): ResourceGroupsTaggingAPIClient {
    if (!this.clients.has("resourcegroups")) {
      this.clients.set(
        "resourcegroups",
        new ResourceGroupsTaggingAPIClient({
          region: this.config.region,
          credentials: this.config.credentials,
          maxAttempts: this.config.maxAttempts || 3,
        }),
      );
    }
    return this.clients.get("resourcegroups");
  }

  static destroyClients(): void {
    for (const [key, client] of this.clients.entries()) {
      if (client.destroy) {
        client.destroy();
      }
    }
    this.clients.clear();
  }
}
```

#### Configuration Management

```typescript
interface AWSEnvironmentConfig {
  region: string;
  profile?: string;
  roleArn?: string;
  externalId?: string;
}

class AWSConfigurationManager {
  private static instance: AWSConfigurationManager;
  private config: AWSEnvironmentConfig;

  private constructor() {
    this.config = this.loadConfiguration();
  }

  static getInstance(): AWSConfigurationManager {
    if (!this.instance) {
      this.instance = new AWSConfigurationManager();
    }
    return this.instance;
  }

  private loadConfiguration(): AWSEnvironmentConfig {
    return {
      region: process.env.AWS_REGION || "us-east-1",
      profile: process.env.AWS_PROFILE || "medialake-dev4",
      roleArn: process.env.AWS_ROLE_ARN,
      externalId: process.env.AWS_EXTERNAL_ID,
    };
  }

  async getCredentials(): Promise<AWSClientConfig> {
    if (this.config.roleArn) {
      // Use STS assume role for cross-account access
      return await this.assumeRole();
    }

    // Use profile-based credentials
    return {
      region: this.config.region,
      profile: this.config.profile,
    };
  }

  private async assumeRole(): Promise<AWSClientConfig> {
    const stsClient = new STSClient({ region: this.config.region });

    const assumeRoleCommand = new AssumeRoleCommand({
      RoleArn: this.config.roleArn,
      RoleSessionName: `medialake-testing-${Date.now()}`,
      ExternalId: this.config.externalId,
      DurationSeconds: 3600, // 1 hour
    });

    const response = await stsClient.send(assumeRoleCommand);

    return {
      region: this.config.region,
      credentials: {
        accessKeyId: response.Credentials!.AccessKeyId!,
        secretAccessKey: response.Credentials!.SecretAccessKey!,
        sessionToken: response.Credentials!.SessionToken!,
      },
    };
  }
}
```

### 2. Service Adapter Implementation

#### Base Service Adapter

```typescript
import { TagFilter } from "@aws-sdk/client-resource-groups-tagging-api";

abstract class BaseServiceAdapter {
  protected resourceGroupsClient: ResourceGroupsTaggingAPIClient;
  protected region: string;

  constructor(region: string) {
    this.region = region;
    this.resourceGroupsClient = AWSClientFactory.getResourceGroupsClient();
  }

  protected convertTagFilters(filters: TagFilter[]): TagFilter[] {
    return filters.map((filter) => ({
      Key: filter.key,
      Values: filter.values,
    }));
  }

  protected async discoverResourcesByTags(
    resourceTypeFilters: string[],
    tagFilters: TagFilter[],
  ): Promise<ResourceTagMapping[]> {
    const command = new GetResourcesCommand({
      ResourceTypeFilters: resourceTypeFilters,
      TagFilters: this.convertTagFilters(tagFilters),
      ResourcesPerPage: 100,
    });

    const resources: ResourceTagMapping[] = [];
    let nextToken: string | undefined;

    do {
      if (nextToken) {
        command.input.PaginationToken = nextToken;
      }

      const response = await this.resourceGroupsClient.send(command);

      if (response.ResourceTagMappingList) {
        resources.push(...response.ResourceTagMappingList);
      }

      nextToken = response.PaginationToken;
    } while (nextToken);

    return resources;
  }

  protected extractResourceId(arn: string): string {
    // Extract resource ID from ARN
    const parts = arn.split(":");
    const resourcePart = parts[parts.length - 1];
    return resourcePart.split("/").pop() || resourcePart;
  }

  protected async withRetry<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    backoffMs: number = 1000,
  ): Promise<T> {
    let lastError: Error;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;

        if (attempt === maxRetries) {
          throw lastError;
        }

        // Exponential backoff
        const delay = backoffMs * Math.pow(2, attempt - 1);
        await new Promise((resolve) => setTimeout(resolve, delay));

        console.warn(
          `Attempt ${attempt} failed, retrying in ${delay}ms:`,
          error.message,
        );
      }
    }

    throw lastError!;
  }
}
```

#### Cognito Service Adapter

```typescript
import {
  CognitoIdentityProviderClient,
  ListUserPoolsCommand,
  ListUserPoolClientsCommand,
  DescribeUserPoolCommand,
  AdminCreateUserCommand,
  AdminSetUserPasswordCommand,
  AdminDeleteUserCommand,
  ListTagsForResourceCommand as CognitoListTagsCommand,
} from "@aws-sdk/client-cognito-identity-provider";

interface CognitoUserPool {
  id: string;
  name: string;
  arn: string;
  tags: Record<string, string>;
  clients: CognitoUserPoolClient[];
}

interface CognitoUserPoolClient {
  id: string;
  name: string;
  userPoolId: string;
}

class CognitoServiceAdapter extends BaseServiceAdapter {
  private cognitoClient: CognitoIdentityProviderClient;

  constructor(region: string) {
    super(region);
    this.cognitoClient = AWSClientFactory.getCognitoClient();
  }

  async discoverUserPools(tagFilters: TagFilter[]): Promise<CognitoUserPool[]> {
    // Use Resource Groups API for tag-based discovery
    const taggedResources = await this.discoverResourcesByTags(
      ["cognito-idp:userpool"],
      tagFilters,
    );

    // Enrich with Cognito-specific details
    const userPools = await Promise.all(
      taggedResources.map((resource) => this.enrichUserPoolDetails(resource)),
    );

    return userPools.filter((pool) => pool !== null) as CognitoUserPool[];
  }

  private async enrichUserPoolDetails(
    resource: ResourceTagMapping,
  ): Promise<CognitoUserPool | null> {
    try {
      const userPoolId = this.extractResourceId(resource.ResourceARN!);

      // Get user pool details
      const describeCommand = new DescribeUserPoolCommand({
        UserPoolId: userPoolId,
      });
      const userPoolDetails = await this.cognitoClient.send(describeCommand);

      // Get user pool clients
      const clients = await this.getUserPoolClients(userPoolId);

      // Convert tags to record
      const tags =
        resource.Tags?.reduce(
          (acc, tag) => {
            acc[tag.Key!] = tag.Value!;
            return acc;
          },
          {} as Record<string, string>,
        ) || {};

      return {
        id: userPoolId,
        name: userPoolDetails.UserPool!.Name!,
        arn: resource.ResourceARN!,
        tags,
        clients,
      };
    } catch (error) {
      console.warn(
        `Failed to enrich user pool details for ${resource.ResourceARN}:`,
        error.message,
      );
      return null;
    }
  }

  private async getUserPoolClients(
    userPoolId: string,
  ): Promise<CognitoUserPoolClient[]> {
    const command = new ListUserPoolClientsCommand({
      UserPoolId: userPoolId,
      MaxResults: 60,
    });

    const response = await this.cognitoClient.send(command);

    return (
      response.UserPoolClients?.map((client) => ({
        id: client.ClientId!,
        name: client.ClientName!,
        userPoolId,
      })) || []
    );
  }

  async createTestUser(
    userPoolId: string,
    username: string,
    password: string,
    email: string,
  ): Promise<void> {
    return this.withRetry(async () => {
      try {
        // Create user
        const createCommand = new AdminCreateUserCommand({
          UserPoolId: userPoolId,
          Username: username,
          UserAttributes: [
            { Name: "email", Value: email },
            { Name: "email_verified", Value: "true" },
          ],
          TemporaryPassword: password,
          MessageAction: "SUPPRESS",
        });

        await this.cognitoClient.send(createCommand);

        // Set permanent password
        const setPasswordCommand = new AdminSetUserPasswordCommand({
          UserPoolId: userPoolId,
          Username: username,
          Password: password,
          Permanent: true,
        });

        await this.cognitoClient.send(setPasswordCommand);

        console.log(
          `[Cognito SDK] Test user created successfully: ${username}`,
        );
      } catch (error: any) {
        if (error.name === "UsernameExistsException") {
          console.log(
            `[Cognito SDK] User ${username} already exists, updating password...`,
          );

          const setPasswordCommand = new AdminSetUserPasswordCommand({
            UserPoolId: userPoolId,
            Username: username,
            Password: password,
            Permanent: true,
          });

          await this.cognitoClient.send(setPasswordCommand);
          console.log(
            `[Cognito SDK] Updated password for existing user: ${username}`,
          );
        } else {
          throw error;
        }
      }
    });
  }

  async deleteTestUser(userPoolId: string, username: string): Promise<void> {
    return this.withRetry(async () => {
      try {
        const deleteCommand = new AdminDeleteUserCommand({
          UserPoolId: userPoolId,
          Username: username,
        });

        await this.cognitoClient.send(deleteCommand);
        console.log(
          `[Cognito SDK] Test user deleted successfully: ${username}`,
        );
      } catch (error: any) {
        if (error.name === "UserNotFoundException") {
          console.log(
            `[Cognito SDK] User ${username} not found, already deleted or never existed`,
          );
        } else {
          console.error(`[Cognito SDK] Error deleting test user:`, error);
          // Don't throw to avoid failing test cleanup
        }
      }
    });
  }

  async getUserPoolPasswordPolicy(userPoolId: string): Promise<any> {
    const command = new DescribeUserPoolCommand({
      UserPoolId: userPoolId,
    });

    const response = await this.cognitoClient.send(command);
    return response.UserPool?.Policies?.PasswordPolicy;
  }
}
```

#### CloudFront Service Adapter

```typescript
import {
  CloudFrontClient,
  ListDistributionsCommand,
  GetDistributionCommand,
  GetDistributionConfigCommand,
  CreateInvalidationCommand,
  GetInvalidationCommand,
  ListTagsForResourceCommand as CloudFrontListTagsCommand,
} from "@aws-sdk/client-cloudfront";

interface CloudFrontDistribution {
  id: string;
  domainName: string;
  aliases: string[];
  status: string;
  arn: string;
  tags: Record<string, string>;
  origins: DistributionOrigin[];
}

interface DistributionOrigin {
  id: string;
  domainName: string;
  originPath?: string;
}

class CloudFrontServiceAdapter extends BaseServiceAdapter {
  private cloudFrontClient: CloudFrontClient;

  constructor(region: string) {
    super(region);
    this.cloudFrontClient = AWSClientFactory.getCloudFrontClient();
  }

  async discoverDistributions(
    tagFilters: TagFilter[],
  ): Promise<CloudFrontDistribution[]> {
    // Use Resource Groups API for tag-based discovery
    const taggedResources = await this.discoverResourcesByTags(
      ["cloudfront:distribution"],
      tagFilters,
    );

    // Enrich with CloudFront-specific details
    const distributions = await Promise.all(
      taggedResources.map((resource) =>
        this.enrichDistributionDetails(resource),
      ),
    );

    return distributions.filter(
      (dist) => dist !== null,
    ) as CloudFrontDistribution[];
  }

  private async enrichDistributionDetails(
    resource: ResourceTagMapping,
  ): Promise<CloudFrontDistribution | null> {
    try {
      const distributionId = this.extractResourceId(resource.ResourceARN!);

      // Get distribution details
      const getCommand = new GetDistributionCommand({
        Id: distributionId,
      });
      const distributionDetails = await this.cloudFrontClient.send(getCommand);

      const distribution = distributionDetails.Distribution!;
      const config = distribution.DistributionConfig!;

      // Convert tags to record
      const tags =
        resource.Tags?.reduce(
          (acc, tag) => {
            acc[tag.Key!] = tag.Value!;
            return acc;
          },
          {} as Record<string, string>,
        ) || {};

      return {
        id: distributionId,
        domainName: distribution.DomainName!,
        aliases: config.Aliases?.Items || [],
        status: distribution.Status!,
        arn: resource.ResourceARN!,
        tags,
        origins: config.Origins!.Items!.map((origin) => ({
          id: origin.Id!,
          domainName: origin.DomainName!,
          originPath: origin.OriginPath,
        })),
      };
    } catch (error) {
      console.warn(
        `Failed to enrich distribution details for ${resource.ResourceARN}:`,
        error.message,
      );
      return null;
    }
  }

  async getDistributionConfiguration(distributionId: string): Promise<any> {
    const command = new GetDistributionConfigCommand({
      Id: distributionId,
    });

    const response = await this.cloudFrontClient.send(command);
    return response.DistributionConfig;
  }

  async createInvalidation(
    distributionId: string,
    paths: string[],
  ): Promise<string> {
    const command = new CreateInvalidationCommand({
      DistributionId: distributionId,
      InvalidationBatch: {
        Paths: {
          Quantity: paths.length,
          Items: paths,
        },
        CallerReference: `medialake-test-${Date.now()}`,
      },
    });

    const response = await this.cloudFrontClient.send(command);
    return response.Invalidation!.Id!;
  }

  async waitForInvalidation(
    distributionId: string,
    invalidationId: string,
  ): Promise<void> {
    const maxWaitTime = 300000; // 5 minutes
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitTime) {
      const command = new GetInvalidationCommand({
        DistributionId: distributionId,
        Id: invalidationId,
      });

      const response = await this.cloudFrontClient.send(command);
      const status = response.Invalidation!.Status!;

      if (status === "Completed") {
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, 10000)); // Wait 10 seconds
    }

    throw new Error(
      `Invalidation ${invalidationId} did not complete within timeout`,
    );
  }
}
```

### 3. Error Handling and Resilience

#### AWS SDK Error Classification

```typescript
interface AWSErrorContext {
  operation: string;
  service: string;
  resourceId?: string;
  retryable: boolean;
  userMessage: string;
}

class AWSErrorHandler {
  static classifyError(
    error: any,
    context: Partial<AWSErrorContext>,
  ): AWSErrorContext {
    const baseContext: AWSErrorContext = {
      operation: context.operation || "unknown",
      service: context.service || "unknown",
      resourceId: context.resourceId,
      retryable: false,
      userMessage: "An AWS operation failed",
    };

    // AWS SDK v3 error classification
    if (error.name) {
      switch (error.name) {
        case "ThrottlingException":
        case "TooManyRequestsException":
          return {
            ...baseContext,
            retryable: true,
            userMessage: "AWS API rate limit exceeded, retrying...",
          };

        case "ServiceUnavailableException":
        case "InternalServerError":
          return {
            ...baseContext,
            retryable: true,
            userMessage: "AWS service temporarily unavailable, retrying...",
          };

        case "AccessDeniedException":
        case "UnauthorizedOperation":
          return {
            ...baseContext,
            retryable: false,
            userMessage: "Insufficient AWS permissions for this operation",
          };

        case "ResourceNotFoundException":
        case "NoSuchBucket":
        case "UserNotFoundException":
          return {
            ...baseContext,
            retryable: false,
            userMessage: `AWS resource not found: ${
              context.resourceId || "unknown"
            }`,
          };

        case "ValidationException":
        case "InvalidParameterException":
          return {
            ...baseContext,
            retryable: false,
            userMessage: "Invalid parameters provided to AWS operation",
          };

        default:
          return {
            ...baseContext,
            retryable: error.retryable || false,
            userMessage: `AWS operation failed: ${error.message}`,
          };
      }
    }

    return baseContext;
  }

  static async handleWithRetry<T>(
    operation: () => Promise<T>,
    context: Partial<AWSErrorContext>,
    maxRetries: number = 3,
  ): Promise<T> {
    let lastError: any;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        const errorContext = this.classifyError(error, context);

        if (!errorContext.retryable || attempt === maxRetries) {
          console.error(`[AWS Error] ${errorContext.userMessage}`, {
            operation: errorContext.operation,
            service: errorContext.service,
            resourceId: errorContext.resourceId,
            attempt,
            error: error.message,
          });
          throw error;
        }

        const delay = Math.min(1000 * Math.pow(2, attempt - 1), 10000);
        console.warn(
          `[AWS Retry] ${errorContext.userMessage} (attempt ${attempt}/${maxRetries})`,
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    throw lastError;
  }
}
```

### 4. Migration Strategy

#### Phase 1: Parallel Implementation

```typescript
class MigrationAwareCognitoFixture {
  private sdkAdapter: CognitoServiceAdapter;
  private legacyDiscovery: LegacyDiscovery;
  private useSdk: boolean;

  constructor() {
    this.sdkAdapter = new CognitoServiceAdapter(
      process.env.AWS_REGION || "us-east-1",
    );
    this.legacyDiscovery = new LegacyDiscovery();
    this.useSdk = process.env.USE_AWS_SDK === "true";
  }

  async discoverUserPool(): Promise<CognitoUserPool> {
    if (this.useSdk) {
      try {
        console.log("[Migration] Using AWS SDK for discovery");
        const pools = await this.sdkAdapter.discoverUserPools([
          { key: "Application", values: ["medialake"], operator: "equals" },
        ]);

        if (pools.length > 0) {
          return pools[0];
        }
      } catch (error) {
        console.warn(
          "[Migration] SDK discovery failed, falling back to CLI:",
          error.message,
        );
      }
    }

    console.log("[Migration] Using legacy CLI discovery");
    return this.legacyDiscovery.findUserPoolByName();
  }

  async createTestUser(
    userPoolId: string,
    username: string,
    password: string,
    email: string,
  ): Promise<void> {
    if (this.useSdk) {
      try {
        await this.sdkAdapter.createTestUser(
          userPoolId,
          username,
          password,
          email,
        );
        return;
      } catch (error) {
        console.warn(
          "[Migration] SDK user creation failed, falling back to CLI:",
          error.message,
        );
      }
    }

    // Fallback to existing CLI-based implementation
    return this.legacyDiscovery.createTestUser(
      userPoolId,
      username,
      password,
      email,
    );
  }
}
```

#### Phase 2: Performance Comparison

```typescript
class PerformanceComparator {
  async compareDiscoveryMethods(): Promise<PerformanceComparison> {
    const sdkAdapter = new CognitoServiceAdapter("us-east-1");
    const legacyDiscovery = new LegacyDiscovery();

    // SDK performance
    const sdkStart = Date.now();
    try {
      const sdkPools = await sdkAdapter.discoverUserPools([
        { key: "Application", values: ["medialake"], operator: "equals" },
      ]);
      const sdkDuration = Date.now() - sdkStart;

      // CLI performance
      const cliStart = Date.now();
      const cliPool = await legacyDiscovery.findUserPoolByName();
      const cliDuration = Date.now() - cliStart;

      return {
        sdk: {
          duration: sdkDuration,
          success: true,
          resourceCount: sdkPools.length,
        },
        cli: {
          duration: cliDuration,
          success: true,
          resourceCount: cliPool ? 1 : 0,
        },
        recommendation: sdkDuration < cliDuration ? "sdk" : "cli",
      };
    } catch (error) {
      return {
        sdk: {
          duration: Date.now() - sdkStart,
          success: false,
          error: error.message,
        },
        cli: {
          duration: 0,
          success: false,
          error: "Not tested due to SDK failure",
        },
        recommendation: "cli",
      };
    }
  }
}
```

### 5. Testing and Validation

#### Unit Testing for SDK Integration

```typescript
describe("CognitoServiceAdapter", () => {
  let mockCognitoClient: jest.Mocked<CognitoIdentityProviderClient>;
  let mockResourceGroupsClient: jest.Mocked<ResourceGroupsTaggingAPIClient>;
  let adapter: CognitoServiceAdapter;

  beforeEach(() => {
    mockCognitoClient = {
      send: jest.fn(),
    } as any;

    mockResourceGroupsClient = {
      send: jest.fn(),
    } as any;

    // Mock the client factory
    jest
      .spyOn(AWSClientFactory, "getCognitoClient")
      .mockReturnValue(mockCognitoClient);
    jest
      .spyOn(AWSClientFactory, "getResourceGroupsClient")
      .mockReturnValue(mockResourceGroupsClient);

    adapter = new CognitoServiceAdapter("us-east-1");
  });

  test("should discover user pools by tags", async () => {
    // Mock Resource Groups API response
    mockResourceGroupsClient.send.mockResolvedValueOnce({
      ResourceTagMappingList: [
        {
          ResourceARN:
            "arn:aws:cognito-idp:us-east-1:123456789:userpool/us-east-1_ABC123",
          Tags: [
            { Key: "Application", Value: "medialake" },
            { Key: "Environment", Value: "dev" },
          ],
        },
      ],
    });

    // Mock Cognito API response
    mockCognitoClient.send
      .mockResolvedValueOnce({
        UserPool: {
          Id: "us-east-1_ABC123",
          Name: "medialake-dev-user-pool",
        },
      })
      .mockResolvedValueOnce({
        UserPoolClients: [
          {
            ClientId: "abc123def456", // pragma: allowlist secret
            ClientName: "medialake-web-client",
          },
        ],
      });

    const pools = await adapter.discoverUserPools([
      { key: "Application", values: ["medialake"], operator: "equals" },
    ]);

    expect(pools).toHaveLength(1);
    expect(pools[0].id).toBe("us-east-1_ABC123");
    expect(pools[0].name).toBe("medialake-dev-user-pool");
    expect(pools[0].tags.Application).toBe("medialake");
    expect(pools[0].clients).toHaveLength(1);
  });

  test("should handle user creation with existing user", async () => {
    // Mock user already exists error
    mockCognitoClient.send
      .mockRejectedValueOnce({
        name: "UsernameExistsException",
        message: "User already exists",
      })
      .mockResolvedValueOnce({}); // Successful password update

    await expect(
      adapter.createTestUser(
        "us-east-1_ABC123",
        "test@example.com",
        "password123",
        "test@example.com",
      ),
    ).resolves.not.toThrow();

    expect(mockCognitoClient.send).toHaveBeenCalledTimes(2);
  });
});
```

#### Integration Testing

```typescript
describe("AWS SDK Integration", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = process.env;
    process.env = {
      ...originalEnv,
      USE_AWS_SDK: "true",
      AWS_REGION: "us-east-1",
    };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  test("should initialize AWS clients correctly", async () => {
    const config = await AWSConfigurationManager.getInstance().getCredentials();
    AWSClientFactory.initialize(config);

    const cognitoClient = AWSClientFactory.getCognitoClient();
    const cloudFrontClient = AWSClientFactory.getCloudFrontClient();

    expect(cognitoClient).toBeInstanceOf(CognitoIdentityProviderClient);
    expect(cloudFrontClient).toBeInstanceOf(CloudFrontClient);
  });

  test("should handle credential configuration", async () => {
    process.env.AWS_ROLE_ARN = "arn:aws:iam::123456789:role/TestRole";

    const configManager = AWSConfigurationManager.getInstance();
    const config = await configManager.getCredentials();

    expect(config.credentials).toBeDefined();
    expect(config.credentials?.accessKeyId).toBeDefined();
  });
});
```

### 6. Deployment and Configuration

#### Package Dependencies

```json
{
  "dependencies": {
    "@aws-sdk/client-cognito-identity-provider": "^3.450.0",
    "@aws-sdk/client-cloudfront": "^3.450.0",
    "@aws-sdk/client-s3": "^3.450.0",
    "@aws-sdk/client-resource-groups-tagging-api": "^3.450.0",
    "@aws-sdk/client
```
