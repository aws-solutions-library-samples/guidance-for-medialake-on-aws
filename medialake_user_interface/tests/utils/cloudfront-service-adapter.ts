/**
 * CloudFront Service Adapter for tag-based distribution discovery
 * Implements the ServiceAdapter interface for AWS CloudFront
 *
 * Note: This implementation requires the following AWS SDK packages to be installed:
 * - @aws-sdk/client-cloudfront
 * - @aws-sdk/client-resource-groups-tagging-api
 */

import {
  ServiceAdapter,
  DiscoveredResource,
  AWSResourceType,
  ResourceDiscoveryConfig,
} from "./aws-resource-finder.js";
import { TagFilter } from "./tag-matcher.js";

export interface CloudFrontDistribution extends DiscoveredResource {
  resourceType: "cloudfront-distribution";
  domainName: string;
  aliases: string[];
  status: string;
  origins: DistributionOrigin[];
  enabled: boolean;
  priceClass: string;
}

export interface DistributionOrigin {
  id: string;
  domainName: string;
  originPath?: string;
  customOriginConfig?: any;
  s3OriginConfig?: any;
}

/**
 * AWS CloudFront service adapter implementing tag-based discovery
 * This is a placeholder implementation that will be completed when AWS SDK packages are installed
 */
export class CloudFrontServiceAdapter implements ServiceAdapter {
  private config: ResourceDiscoveryConfig;

  constructor(config: ResourceDiscoveryConfig) {
    this.config = config;
    console.log(`[CloudFrontAdapter] Initialized for region: ${config.region}`);
  }

  /**
   * Get the resource type this adapter handles
   */
  getResourceType(): AWSResourceType {
    return "cloudfront-distribution";
  }

  /**
   * Discover CloudFront distributions using tag-based filtering
   * TODO: Implement with actual AWS SDK when packages are installed
   */
  async discoverResources(
    filters: TagFilter[],
  ): Promise<CloudFrontDistribution[]> {
    console.log(
      `[CloudFrontAdapter] Discovering distributions with filters:`,
      filters,
    );

    // Use fallback discovery method to find real CloudFront distributions
    console.log(
      `[CloudFrontAdapter] Using fallback discovery - AWS SDK packages not installed`,
    );

    return await this.fallbackDiscovery(filters);
  }

  /**
   * Validate that a discovered resource is accessible and valid
   */
  async validateResource(resource: DiscoveredResource): Promise<boolean> {
    if (resource.resourceType !== "cloudfront-distribution") {
      return false;
    }

    console.log(`[CloudFrontAdapter] Validating distribution: ${resource.id}`);

    // Placeholder validation - will be replaced with actual AWS SDK calls
    return resource.id.startsWith("E") && resource.id.length === 14;
  }

  /**
   * Get distribution configuration details
   * TODO: Implement with actual AWS SDK when packages are installed
   */
  async getDistributionConfiguration(distributionId: string): Promise<any> {
    console.log(
      `[CloudFrontAdapter] Getting configuration for distribution: ${distributionId}`,
    );
    console.warn(
      `[CloudFrontAdapter] Placeholder implementation - would fetch config with AWS SDK`,
    );

    // Return mock configuration
    return {
      Id: distributionId,
      CallerReference: `medialake-${Date.now()}`,
      Aliases: {
        Quantity: 1,
        Items: ["cdn.medialake.example.com"],
      },
      DefaultRootObject: "index.html",
      Origins: {
        Quantity: 1,
        Items: [
          {
            Id: "S3-medialake-assets",
            DomainName: "medialake-assets.s3.amazonaws.com",
            OriginPath: "/media",
            S3OriginConfig: {
              OriginAccessIdentity:
                "origin-access-identity/cloudfront/E1234567890ABC", // pragma: allowlist secret
            },
          },
        ],
      },
      DefaultCacheBehavior: {
        TargetOriginId: "S3-medialake-assets",
        ViewerProtocolPolicy: "redirect-to-https",
        MinTTL: 0,
        ForwardedValues: {
          QueryString: false,
          Cookies: { Forward: "none" },
        },
      },
      Comment: "MediaLake CDN Distribution",
      Enabled: true,
      PriceClass: "PriceClass_All",
    };
  }

  /**
   * Create cache invalidation for testing purposes
   */
  async createInvalidation(
    distributionId: string,
    paths: string[],
  ): Promise<string> {
    console.log(
      `[CloudFrontAdapter] Creating invalidation for distribution ${distributionId}, paths:`,
      paths,
    );
    console.warn(
      `[CloudFrontAdapter] Placeholder implementation - would create invalidation with AWS SDK`,
    );

    // Return mock invalidation ID
    const invalidationId = `I${Date.now()}`;
    console.log(
      `[CloudFrontAdapter] Mock invalidation created: ${invalidationId}`,
    );

    return invalidationId;
  }

  /**
   * Wait for invalidation to complete
   */
  async waitForInvalidation(
    distributionId: string,
    invalidationId: string,
  ): Promise<void> {
    console.log(
      `[CloudFrontAdapter] Waiting for invalidation ${invalidationId} on distribution ${distributionId}`,
    );
    console.warn(
      `[CloudFrontAdapter] Placeholder implementation - would poll invalidation status with AWS SDK`,
    );

    // Mock wait time
    await new Promise((resolve) => setTimeout(resolve, 1000));
    console.log(
      `[CloudFrontAdapter] Mock invalidation completed: ${invalidationId}`,
    );
  }

  /**
   * Check if distribution is ready for testing
   */
  async isDistributionReady(distributionId: string): Promise<boolean> {
    console.log(
      `[CloudFrontAdapter] Checking if distribution ${distributionId} is ready`,
    );

    try {
      const config = await this.getDistributionConfiguration(distributionId);
      return config.Enabled === true;
    } catch (error) {
      console.warn(
        `[CloudFrontAdapter] Error checking distribution readiness:`,
        error,
      );
      return false;
    }
  }

  /**
   * Get distribution domain name for testing
   */
  async getDistributionDomainName(distributionId: string): Promise<string> {
    console.log(
      `[CloudFrontAdapter] Getting domain name for distribution: ${distributionId}`,
    );

    // Placeholder - would get from actual distribution configuration
    return `${distributionId.toLowerCase()}.cloudfront.net`;
  }

  /**
   * Test distribution accessibility
   */
  async testDistributionAccess(
    distributionId: string,
    testPath: string = "/",
  ): Promise<boolean> {
    console.log(
      `[CloudFrontAdapter] Testing access to distribution ${distributionId} at path: ${testPath}`,
    );

    try {
      const domainName = await this.getDistributionDomainName(distributionId);
      const testUrl = `https://${domainName}${testPath}`;

      console.log(`[CloudFrontAdapter] Would test URL: ${testUrl}`);
      console.warn(
        `[CloudFrontAdapter] Placeholder implementation - would make HTTP request to test access`,
      );

      // Mock successful access test
      return true;
    } catch (error) {
      console.warn(
        `[CloudFrontAdapter] Distribution access test failed:`,
        error,
      );
      return false;
    }
  }

  /**
   * Fallback discovery using list-based approach
   * This method provides backward compatibility if tag-based discovery fails
   */
  async fallbackDiscovery(
    filters: TagFilter[],
  ): Promise<CloudFrontDistribution[]> {
    console.log(`[CloudFrontAdapter] Using fallback discovery method`);

    // Look for Application filter to determine naming pattern
    const applicationFilter = filters.find((f) => f.key === "Application");
    const searchPattern = applicationFilter?.values[0] || "medialake";

    console.log(
      `[CloudFrontAdapter] Searching for distributions related to: ${searchPattern}`,
    );

    try {
      // Use AWS CLI to list CloudFront distributions
      const { execSync } = await import("child_process");

      // Build AWS CLI command - only add profile if it's not 'default'
      let awsCommand = `aws cloudfront list-distributions --region ${this.config.region}`;
      if (this.config.profile && this.config.profile !== "default") {
        awsCommand = `aws cloudfront list-distributions --profile ${this.config.profile} --region ${this.config.region}`;
      }

      console.log(`[CloudFrontAdapter] Executing: ${awsCommand}`);
      const distributionsOutput = execSync(awsCommand, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
        timeout: 30000, // 30 second timeout
      });

      const distributionsData = JSON.parse(distributionsOutput);
      const distributions = distributionsData.DistributionList?.Items || [];

      console.log(
        `[CloudFrontAdapter] Found ${distributions.length} total distributions`,
      );

      const matchingDistributions: CloudFrontDistribution[] = [];

      for (const dist of distributions) {
        // Log distribution details for debugging
        const comment = dist.Comment || "";
        const aliases = dist.Aliases?.Items || [];
        const domainName = dist.DomainName || "";

        console.log(`[CloudFrontAdapter] Checking distribution ${dist.Id}:`);
        console.log(`  - Comment: "${comment}"`);
        console.log(`  - Domain: "${domainName}"`);
        console.log(`  - Aliases: [${aliases.join(", ")}]`);
        console.log(`  - ARN: ${dist.ARN}`);

        // Always check tags for every distribution, regardless of name/comment matching
        console.log(
          `[CloudFrontAdapter] Checking tags for distribution: ${dist.Id}`,
        );

        // Get distribution tags to verify it matches our filters
        try {
          let getTagsCommand = `aws cloudfront list-tags-for-resource --resource ${dist.ARN} --region ${this.config.region}`;
          if (this.config.profile && this.config.profile !== "default") {
            getTagsCommand = `aws cloudfront list-tags-for-resource --resource ${dist.ARN} --profile ${this.config.profile} --region ${this.config.region}`;
          }

          console.log(`[CloudFrontAdapter] Executing: ${getTagsCommand}`);
          const tagsOutput = execSync(getTagsCommand, {
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            timeout: 15000, // 15 second timeout for tag checking
          });

          const tagsData = JSON.parse(tagsOutput);
          const tags = tagsData.Tags?.Items || [];

          console.log(
            `[CloudFrontAdapter] Found ${tags.length} tags for distribution ${dist.Id}:`,
          );
          tags.forEach((tag: any) => {
            console.log(`  - ${tag.Key}: ${tag.Value}`);
          });

          // Convert tags to our format
          const tagMap: Record<string, string> = {};
          tags.forEach((tag: any) => {
            tagMap[tag.Key] = tag.Value;
          });

          // Check if tags match our filters - check both cases
          const applicationTag = tagMap["Application"] || tagMap["application"];
          console.log(
            `[CloudFrontAdapter] Application tag value: "${applicationTag}", searching for: "${searchPattern}"`,
          );

          if (
            applicationTag &&
            applicationTag.toLowerCase() === searchPattern.toLowerCase()
          ) {
            console.log(
              `[CloudFrontAdapter] ✓ Distribution ${dist.Id} matches Application tag!`,
            );

            const cloudFrontDist: CloudFrontDistribution = {
              id: dist.Id,
              name: comment || `cloudfront-${dist.Id}`,
              arn: dist.ARN,
              tags: tagMap,
              resourceType: "cloudfront-distribution",
              region: "global", // CloudFront is global
              discoveredAt: new Date(),
              domainName: dist.DomainName,
              aliases: aliases,
              status: dist.Status,
              enabled: dist.Enabled,
              priceClass: dist.PriceClass,
              origins: (dist.Origins?.Items || []).map((origin: any) => ({
                id: origin.Id,
                domainName: origin.DomainName,
                originPath: origin.OriginPath,
                customOriginConfig: origin.CustomOriginConfig,
                s3OriginConfig: origin.S3OriginConfig,
              })),
            };

            matchingDistributions.push(cloudFrontDist);
            console.log(
              `[CloudFrontAdapter] Added distribution: ${cloudFrontDist.name} (${cloudFrontDist.domainName})`,
            );
          } else {
            console.log(
              `[CloudFrontAdapter] ✗ Distribution ${dist.Id} does not match Application tag`,
            );
          }
        } catch (tagError: any) {
          console.warn(
            `[CloudFrontAdapter] Could not get tags for distribution ${dist.Id}:`,
            tagError.message,
          );

          // Check if distribution comment or aliases contain the search pattern as fallback
          const matchesPattern =
            comment.toLowerCase().includes(searchPattern.toLowerCase()) ||
            aliases.some((alias: string) =>
              alias.toLowerCase().includes(searchPattern.toLowerCase()),
            ) ||
            domainName.toLowerCase().includes(searchPattern.toLowerCase());

          if (matchesPattern) {
            console.log(
              `[CloudFrontAdapter] Using fallback pattern matching for ${dist.Id}`,
            );
            const cloudFrontDist: CloudFrontDistribution = {
              id: dist.Id,
              name: comment || `cloudfront-${dist.Id}`,
              arn: dist.ARN,
              tags: { Application: searchPattern }, // Assume it matches
              resourceType: "cloudfront-distribution",
              region: "global",
              discoveredAt: new Date(),
              domainName: dist.DomainName,
              aliases: aliases,
              status: dist.Status,
              enabled: dist.Enabled,
              priceClass: dist.PriceClass,
              origins: (dist.Origins?.Items || []).map((origin: any) => ({
                id: origin.Id,
                domainName: origin.DomainName,
                originPath: origin.OriginPath,
                customOriginConfig: origin.CustomOriginConfig,
                s3OriginConfig: origin.S3OriginConfig,
              })),
            };

            matchingDistributions.push(cloudFrontDist);
            console.log(
              `[CloudFrontAdapter] Added distribution via fallback: ${cloudFrontDist.name}`,
            );
          }
        }
      }

      console.log(
        `[CloudFrontAdapter] Found ${matchingDistributions.length} matching distributions`,
      );
      return matchingDistributions;
    } catch (error: any) {
      console.error(
        `[CloudFrontAdapter] Fallback discovery failed:`,
        error.message,
      );
      return [];
    }
  }

  /**
   * Cleanup resources and connections
   */
  async cleanup(): Promise<void> {
    console.log(
      `[CloudFrontAdapter] Cleaning up CloudFront service adapter...`,
    );
    // AWS SDK clients don't require explicit cleanup in v3
  }
}

/**
 * Factory function to create CloudFrontServiceAdapter
 */
export function createCloudFrontServiceAdapter(
  config: ResourceDiscoveryConfig,
): CloudFrontServiceAdapter {
  return new CloudFrontServiceAdapter(config);
}
