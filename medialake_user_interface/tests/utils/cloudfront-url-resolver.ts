/**
 * CloudFront URL auto-resolver for performance benchmarks.
 *
 * Resolution order:
 *   1. PLAYWRIGHT_BASE_URL env var (explicit override — always wins)
 *   2. SSM Parameter: /medialake/{env}/cloudfront-distribution-domain
 *   3. CloudFront tag-based discovery (Application=medialake)
 *   4. CloudFront listing fallback (comment/alias matching)
 *
 * Supports AWS_PROFILE for multi-account setups.
 *
 * Usage:
 *   import { resolveCloudFrontUrl } from './cloudfront-url-resolver';
 *   const url = await resolveCloudFrontUrl({ environment: 'dev', profile: 'my-profile' });
 */

import { execSync } from "child_process";

export interface ResolverOptions {
  /** MediaLake environment: dev, staging, prod. Defaults to MEDIALAKE_ENV or 'dev'. */
  environment?: string;
  /** AWS CLI profile name. Defaults to AWS_PROFILE env var. */
  profile?: string;
  /** AWS region for SSM lookups. Defaults to AWS_REGION or 'us-east-1'. */
  region?: string;
  /** Application tag value to match. Defaults to 'medialake'. */
  applicationTag?: string;
  /** Command timeout in ms. Defaults to 15000. */
  timeout?: number;
}

export interface ResolverResult {
  url: string;
  method: "env-var" | "ssm-parameter" | "tag-discovery" | "fallback-listing";
  distributionId?: string;
  domainName?: string;
}

/**
 * Builds the base AWS CLI flags for profile and region.
 */
function awsFlags(profile?: string, region?: string): string {
  const parts: string[] = [];
  if (profile && profile !== "default") {
    parts.push(`--profile ${profile}`);
  }
  if (region) {
    parts.push(`--region ${region}`);
  }
  return parts.join(" ");
}

/**
 * Runs an AWS CLI command and returns parsed JSON, or null on failure.
 */
function awsCli<T = any>(command: string, timeout: number): T | null {
  try {
    const output = execSync(command, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
      timeout,
    });
    return JSON.parse(output) as T;
  } catch (err: any) {
    console.warn(`[url-resolver] CLI command failed: ${err.message}`);
    return null;
  }
}

/**
 * Strategy 1: Read the CloudFront domain from SSM Parameter Store.
 * The CDK stack writes it to /medialake/{env}/cloudfront-distribution-domain.
 */
function resolveFromSsm(env: string, flags: string, timeout: number): ResolverResult | null {
  const paramName = `/medialake/${env}/cloudfront-distribution-domain`;
  console.log(`[url-resolver] Trying SSM parameter: ${paramName}`);

  const data = awsCli<{ Parameter: { Value: string } }>(
    `aws ssm get-parameter --name "${paramName}" ${flags} --output json`,
    timeout
  );

  if (data?.Parameter?.Value) {
    const domain = data.Parameter.Value;
    console.log(`[url-resolver] Found domain via SSM: ${domain}`);
    return {
      url: `https://${domain}`,
      method: "ssm-parameter",
      domainName: domain,
    };
  }

  console.warn(`[url-resolver] SSM parameter not found or empty`);
  return null;
}

/**
 * Strategy 2: Use Resource Groups Tagging API to find CloudFront distributions
 * tagged with Application=medialake + Environment={env}.
 */
function resolveFromTags(
  env: string,
  applicationTag: string,
  flags: string,
  timeout: number
): ResolverResult | null {
  console.log(
    `[url-resolver] Trying tag-based discovery: Application=${applicationTag}, Environment=${env}`
  );

  const tagFilters = JSON.stringify([
    { Key: "Application", Values: [applicationTag] },
    { Key: "Environment", Values: [env] },
  ]);

  const data = awsCli<{
    ResourceTagMappingList: Array<{ ResourceARN: string }>;
  }>(
    `aws resourcegroupstaggingapi get-resources --tag-filters '${tagFilters}' --resource-type-filters cloudfront:distribution ${flags} --output json`,
    timeout
  );

  const resources = data?.ResourceTagMappingList || [];
  if (resources.length === 0) {
    console.warn(`[url-resolver] No tagged CloudFront distributions found`);
    return null;
  }

  // ARN format: arn:aws:cloudfront::123456789012:distribution/E1234567890
  const arn = resources[0].ResourceARN;
  const distId = arn.split("/").pop()!;
  console.log(`[url-resolver] Found distribution via tags: ${distId}`);

  // Get the domain name for this distribution
  const distData = awsCli<{
    Distribution: { DomainName: string };
  }>(`aws cloudfront get-distribution --id ${distId} ${flags} --output json`, timeout);

  if (distData?.Distribution?.DomainName) {
    const domain = distData.Distribution.DomainName;
    console.log(`[url-resolver] Resolved domain: ${domain}`);
    return {
      url: `https://${domain}`,
      method: "tag-discovery",
      distributionId: distId,
      domainName: domain,
    };
  }

  return null;
}

/**
 * Strategy 3: List all CloudFront distributions and match by comment/alias
 * containing the application name. Last resort.
 */
function resolveFromListing(
  applicationTag: string,
  flags: string,
  timeout: number
): ResolverResult | null {
  console.log(`[url-resolver] Trying CloudFront listing fallback`);

  const data = awsCli<{
    DistributionList: {
      Items: Array<{
        Id: string;
        DomainName: string;
        Comment: string;
        Aliases: { Items: string[] };
        Enabled: boolean;
        Status: string;
      }>;
    };
  }>(`aws cloudfront list-distributions ${flags} --output json`, timeout);

  const distributions = data?.DistributionList?.Items || [];
  console.log(`[url-resolver] Found ${distributions.length} total distributions`);

  // Match by comment or alias containing the application name
  const pattern = applicationTag.toLowerCase();
  const match = distributions.find((d) => {
    if (!d.Enabled || d.Status !== "Deployed") return false;
    const comment = (d.Comment || "").toLowerCase();
    const aliases = (d.Aliases?.Items || []).map((a) => a.toLowerCase());
    return comment.includes(pattern) || aliases.some((a) => a.includes(pattern));
  });

  if (match) {
    // Prefer alias over CloudFront domain if available
    const domain = match.Aliases?.Items?.length > 0 ? match.Aliases.Items[0] : match.DomainName;

    console.log(`[url-resolver] Matched distribution ${match.Id} via listing: ${domain}`);
    return {
      url: `https://${domain}`,
      method: "fallback-listing",
      distributionId: match.Id,
      domainName: domain,
    };
  }

  // If no comment/alias match, try matching by tags on each distribution
  for (const dist of distributions) {
    if (!dist.Enabled || dist.Status !== "Deployed") continue;

    const tagsData = awsCli<{
      Tags: { Items: Array<{ Key: string; Value: string }> };
    }>(
      `aws cloudfront list-tags-for-resource --resource arn:aws:cloudfront::*:distribution/${dist.Id} ${flags} --output json`,
      timeout
    );

    const tags = tagsData?.Tags?.Items || [];
    const appTag = tags.find(
      (t) => t.Key.toLowerCase() === "application" && t.Value.toLowerCase() === pattern
    );

    if (appTag) {
      const domain = dist.Aliases?.Items?.length > 0 ? dist.Aliases.Items[0] : dist.DomainName;

      console.log(`[url-resolver] Matched distribution ${dist.Id} via tag scan: ${domain}`);
      return {
        url: `https://${domain}`,
        method: "fallback-listing",
        distributionId: dist.Id,
        domainName: domain,
      };
    }
  }

  console.warn(`[url-resolver] No matching distribution found in listing`);
  return null;
}

/**
 * Resolves the CloudFront URL for the MediaLake UI deployment.
 *
 * Tries strategies in order: env var → SSM → tags → listing.
 * Throws if no URL can be resolved.
 */
export async function resolveCloudFrontUrl(options: ResolverOptions = {}): Promise<ResolverResult> {
  const env = options.environment || process.env.MEDIALAKE_ENV || "dev";
  const profile = options.profile || process.env.AWS_PROFILE;
  const region = options.region || process.env.AWS_REGION || "us-east-1";
  const applicationTag = options.applicationTag || "medialake";
  const timeout = options.timeout || 15000;

  console.log(
    `[url-resolver] Resolving CloudFront URL (env=${env}, profile=${
      profile || "default"
    }, region=${region})`
  );

  // 1. Explicit env var always wins
  if (process.env.PLAYWRIGHT_BASE_URL) {
    console.log(`[url-resolver] Using PLAYWRIGHT_BASE_URL: ${process.env.PLAYWRIGHT_BASE_URL}`);
    return {
      url: process.env.PLAYWRIGHT_BASE_URL,
      method: "env-var",
    };
  }

  const flags = awsFlags(profile, region);

  // 2. SSM Parameter (fastest — single API call)
  const ssmResult = resolveFromSsm(env, flags, timeout);
  if (ssmResult) return ssmResult;

  // 3. Tag-based discovery via Resource Groups Tagging API
  const tagResult = resolveFromTags(env, applicationTag, flags, timeout);
  if (tagResult) return tagResult;

  // 4. Fallback: list all distributions and match
  const listResult = resolveFromListing(applicationTag, flags, timeout);
  if (listResult) return listResult;

  throw new Error(
    `[url-resolver] Could not resolve CloudFront URL for environment "${env}". ` +
      `Ensure the stack is deployed or set PLAYWRIGHT_BASE_URL manually.`
  );
}

/**
 * Synchronous wrapper for use in Playwright config files (which need sync baseURL).
 * Falls back to a placeholder if resolution fails, letting tests skip gracefully.
 */
export function resolveCloudFrontUrlSync(options: ResolverOptions = {}): string {
  const env = options.environment || process.env.MEDIALAKE_ENV || "dev";
  const profile = options.profile || process.env.AWS_PROFILE;
  const region = options.region || process.env.AWS_REGION || "us-east-1";
  const applicationTag = options.applicationTag || "medialake";
  const timeout = options.timeout || 15000;

  // 1. Explicit env var
  if (process.env.PLAYWRIGHT_BASE_URL) {
    return process.env.PLAYWRIGHT_BASE_URL;
  }

  const flags = awsFlags(profile, region);

  // 2. SSM
  const ssmResult = resolveFromSsm(env, flags, timeout);
  if (ssmResult) return ssmResult.url;

  // 3. Tags
  const tagResult = resolveFromTags(env, applicationTag, flags, timeout);
  if (tagResult) return tagResult.url;

  // 4. Listing
  const listResult = resolveFromListing(applicationTag, flags, timeout);
  if (listResult) return listResult.url;

  console.error(
    `[url-resolver] Could not auto-detect CloudFront URL. Set PLAYWRIGHT_BASE_URL or deploy the stack.`
  );
  return "http://localhost:5173"; // Safe fallback for local dev
}
