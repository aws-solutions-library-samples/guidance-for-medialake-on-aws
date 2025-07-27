---
title: Architecture Decision Record - Tag-Based AWS Resource Discovery Strategy
task_id: 1.1
date: 2025-07-27
last_updated: 2025-07-27
status: DRAFT
owner: Architect
---

# ADR-001: Tag-Based AWS Resource Discovery Strategy

## Status

**PROPOSED** - Awaiting review and approval

## Context

The MediaLake Playwright testing infrastructure currently uses name-based pattern matching to discover AWS resources, specifically Cognito User Pools. This approach has several limitations:

### Current Implementation Analysis

- **Name-Based Discovery**: [`findUserPoolId()`](medialake_user_interface/tests/fixtures/cognito.fixtures.ts:104-129) searches for pools containing "medialake" in the name
- **Brittle Pattern Matching**: Relies on naming conventions that may change over time
- **Limited Scalability**: Difficult to extend to multiple AWS services with consistent discovery logic
- **Environment Isolation Issues**: No clear mechanism to distinguish between dev/staging/prod resources
- **Manual Resource Management**: Requires manual coordination of resource names across environments

### Business Requirements

1. **Multi-Service Support**: Extend testing to CloudFront distributions, additional Cognito pools, and future AWS services
2. **Environment Isolation**: Clearly separate resources by environment (dev, staging, production)
3. **Automated Discovery**: Reduce manual configuration and naming convention dependencies
4. **Scalable Architecture**: Support future AWS service integrations with minimal code changes
5. **Backward Compatibility**: Maintain existing test functionality during migration

## Decision

We will **adopt a tag-based AWS resource discovery strategy** that replaces name-based pattern matching with standardized AWS resource tagging.

### Core Decision Points

#### 1. Primary Discovery Method: AWS Resource Tags

- **Standard Tag Pattern**: `Application: medialake`
- **Environment Filtering**: `Environment: dev|staging|prod`
- **Testing Enablement**: `Testing: enabled`
- **Service Classification**: `Service: cognito-user-pool|cloudfront-distribution|s3-bucket`

#### 2. Fallback Strategy: Graceful Degradation

- Maintain existing name-based discovery as fallback mechanism
- Log fallback activation for monitoring and migration tracking
- Gradual migration path without breaking existing tests

#### 3. Caching Strategy: Worker-Scoped Resource Cache

- 5-minute TTL for discovered resources
- Worker-isolated cache to prevent cross-test contamination
- Intelligent cache invalidation on AWS API errors

#### 4. API Integration: AWS SDK over CLI

- Replace AWS CLI calls with AWS SDK for JavaScript
- Improved error handling and type safety
- Better performance and reduced subprocess overhead

## Rationale

### Why Tag-Based Discovery?

#### **Advantages**

1. **Standardization**: AWS-native approach using built-in tagging capabilities
2. **Flexibility**: Easy to add new filter criteria without code changes
3. **Environment Safety**: Clear resource isolation through environment tags
4. **Scalability**: Consistent discovery pattern across all AWS services
5. **Governance**: Aligns with AWS best practices for resource management
6. **Automation**: Enables infrastructure-as-code resource discovery

#### **Addressing Current Pain Points**

- **Naming Convention Dependency**: Tags are more flexible than rigid naming patterns
- **Multi-Environment Support**: Environment tags provide clear resource separation
- **Service Expansion**: Tag-based queries work consistently across AWS services
- **Resource Lifecycle**: Tags persist through resource updates and migrations

### Why AWS SDK over CLI?

#### **Technical Benefits**

1. **Performance**: Direct API calls eliminate subprocess overhead
2. **Type Safety**: TypeScript interfaces provide compile-time validation
3. **Error Handling**: Structured error responses with detailed context
4. **Pagination**: Built-in support for large result sets
5. **Authentication**: Seamless integration with AWS credential chains

#### **Operational Benefits**

1. **Dependency Reduction**: No external CLI tool dependency
2. **Version Control**: Explicit SDK version management
3. **Testing**: Easier to mock and unit test SDK calls
4. **Monitoring**: Better observability into API call patterns

### Why Caching Strategy?

#### **Performance Optimization**

- Reduce AWS API calls during test execution
- Improve test startup time for parallel workers
- Minimize AWS service throttling risk

#### **Cost Optimization**

- Reduce AWS API request costs
- Efficient resource utilization during CI/CD runs

#### **Reliability Enhancement**

- Resilience against temporary AWS API issues
- Consistent resource state within test worker scope

## Implementation Strategy

### Phase 1: Foundation (Weeks 1-2)

```typescript
// Core interfaces and discovery engine
interface ResourceDiscoveryEngine {
  discoverByTags(
    resourceType: AWSResourceType,
    tags: TagFilter[],
  ): Promise<DiscoveredResource[]>;
  getCachedResources(
    resourceType: AWSResourceType,
  ): DiscoveredResource[] | null;
}

// Standard tag patterns
const StandardTagPatterns = {
  APPLICATION_TAG: {
    key: "Application",
    values: ["medialake"],
    operator: "equals",
  },
  ENVIRONMENT_TAG: {
    key: "Environment",
    values: ["dev", "staging", "prod"],
    operator: "equals",
  },
  TESTING_TAG: { key: "Testing", values: ["enabled"], operator: "equals" },
};
```

### Phase 2: Service Integration (Weeks 3-4)

```typescript
// Cognito service adapter with tag-based discovery
class CognitoServiceAdapter {
  async discoverUserPools(tags: TagFilter[]): Promise<CognitoUserPool[]> {
    // Use ResourceGroupsTaggingAPI for cross-service tag queries
    const taggedResources = await this.resourceGroupsClient.getResources({
      ResourceTypeFilters: ["cognito-idp:userpool"],
      TagFilters: this.convertToAWSTagFilters(tags),
    });

    return this.enrichWithCognitoDetails(taggedResources);
  }
}
```

### Phase 3: Migration and Optimization (Weeks 5-6)

```typescript
// Backward-compatible fixture extension
export const test = base.extend<EnhancedCognitoFixtures>({
  cognitoTestUser: [
    async ({}, use, testInfo) => {
      const discoveryEngine = new ResourceDiscoveryEngine();

      // Primary: Tag-based discovery
      let userPools = await discoveryEngine.discoverByTags(
        "cognito-user-pool",
        [StandardTagPatterns.APPLICATION_TAG, StandardTagPatterns.TESTING_TAG],
      );

      // Fallback: Name-based discovery
      if (userPools.length === 0) {
        console.warn("[Migration] Falling back to name-based discovery");
        userPools = await this.legacyNameBasedDiscovery();
      }

      // Continue with existing user creation logic...
    },
    { scope: "test" },
  ],
});
```

## Consequences

### Positive Consequences

#### **Immediate Benefits**

1. **Reduced Maintenance**: Less brittle than name-based patterns
2. **Environment Safety**: Clear resource isolation prevents cross-environment issues
3. **Extensibility**: Easy to add new AWS services with consistent patterns
4. **Performance**: Caching reduces API calls and improves test speed

#### **Long-term Benefits**

1. **Governance Alignment**: Follows AWS tagging best practices
2. **Cost Optimization**: Reduced API calls and better resource utilization
3. **Operational Excellence**: Improved monitoring and resource management
4. **Developer Experience**: More predictable and reliable test infrastructure

### Negative Consequences

#### **Migration Complexity**

1. **Resource Tagging**: Requires tagging existing AWS resources
2. **Coordination**: Need to coordinate with infrastructure teams
3. **Testing**: Extensive testing required during migration period
4. **Documentation**: Update team knowledge and runbooks

#### **Operational Overhead**

1. **Tag Management**: Need processes to maintain consistent tagging
2. **Monitoring**: Additional monitoring for tag compliance
3. **Permissions**: Updated IAM policies for tag-based queries

### Risk Mitigation Strategies

#### **Migration Risks**

- **Gradual Rollout**: Phase-based implementation with fallback mechanisms
- **Comprehensive Testing**: Extensive testing in dev environment before production
- **Rollback Plan**: Ability to revert to name-based discovery if issues arise

#### **Operational Risks**

- **Tag Validation**: Automated checks for required tags during resource creation
- **Documentation**: Clear tagging standards and team training
- **Monitoring**: Alerts for resources missing required tags

## Alternatives Considered

### Alternative 1: Enhanced Name-Based Discovery

**Description**: Improve existing name-based patterns with regex and environment prefixes

**Pros**:

- Minimal infrastructure changes required
- Familiar to current team
- Quick to implement

**Cons**:

- Still brittle and dependent on naming conventions
- Doesn't scale to multiple services well
- Limited environment isolation capabilities

**Decision**: Rejected - doesn't address fundamental scalability issues

### Alternative 2: Configuration-Based Discovery

**Description**: Use external configuration files to map environments to specific resource IDs

**Pros**:

- Explicit resource mapping
- Version controlled configuration
- Clear environment separation

**Cons**:

- Manual maintenance overhead
- Doesn't scale with dynamic infrastructure
- Configuration drift risk

**Decision**: Rejected - increases operational complexity without solving discovery scalability

### Alternative 3: Service Discovery Integration

**Description**: Integrate with AWS Service Discovery or external service registry

**Pros**:

- Centralized resource registry
- Advanced query capabilities
- Integration with service mesh patterns

**Cons**:

- Additional infrastructure complexity
- Overkill for current testing needs
- Vendor lock-in to specific service discovery solution

**Decision**: Rejected - unnecessary complexity for current requirements

## Implementation Notes

### Required AWS Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "resourcegroupstaggingapi:GetResources",
        "cognito-idp:ListUserPools",
        "cognito-idp:ListTagsForResource",
        "cloudfront:ListDistributions",
        "cloudfront:ListTagsForResource"
      ],
      "Resource": "*"
    }
  ]
}
```

### Standard Tag Schema

```yaml
required_tags:
  Application:
    description: "Primary application identifier"
    values: ["medialake"]
    required: true

  Environment:
    description: "Deployment environment"
    values: ["dev", "staging", "prod"]
    required: true

  Testing:
    description: "Testing enablement flag"
    values: ["enabled", "disabled"]
    required: false
    default: "disabled"

optional_tags:
  Owner:
    description: "Team or individual responsible for resource"
    pattern: "^[a-zA-Z0-9-]+$"

  CostCenter:
    description: "Cost allocation identifier"
    pattern: "^CC-[0-9]{4}$"
```

### Migration Checklist

- [ ] Tag existing Cognito User Pools with standard tags
- [ ] Tag existing CloudFront distributions with standard tags
- [ ] Update IAM policies for tag-based resource queries
- [ ] Implement ResourceDiscoveryEngine with caching
- [ ] Create service adapters for Cognito and CloudFront
- [ ] Update fixture implementations with fallback logic
- [ ] Add monitoring for tag compliance and fallback usage
- [ ] Update team documentation and runbooks
- [ ] Conduct thorough testing in dev environment
- [ ] Plan production rollout with rollback procedures

## References

- [AWS Resource Groups Tagging API Documentation](https://docs.aws.amazon.com/resourcegroupstaggingapi/)
- [AWS Tagging Best Practices](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)
- [Existing Cognito Fixture Implementation](medialake_user_interface/tests/fixtures/cognito.fixtures.ts)
- [AWS SDK for JavaScript v3](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/)

## Approval

**Architect**: [Pending]
**Lead Developer**: [Pending]
**DevOps Lead**: [Pending]
**Product Owner**: [Pending]

---

_This ADR will be updated as implementation progresses and feedback is incorporated._
