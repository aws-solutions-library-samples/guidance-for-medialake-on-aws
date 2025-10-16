# Requirements Document

## Introduction

The MediaLake Auto-Upgrade System enables users to automatically upgrade their MediaLake deployment to newer versions by selecting from available GitHub releases, tags, or branches. This feature provides a seamless way to keep MediaLake installations current with the latest features, security updates, and bug fixes without manual intervention in the deployment pipeline.

The system integrates with the existing CodePipeline infrastructure deployed via the medialake.template CloudFormation script and provides a user-friendly interface in the system settings to manage upgrades. It fetches available versions from the public GitHub repository, allows users to select a target version, and orchestrates the upgrade process through the existing CI/CD pipeline.

## Requirements

### Requirement 1

**User Story:** As a MediaLake super administrator, I want to view available versions (branches and tags) from the GitHub repository, so that I can choose which version to upgrade to.

#### Acceptance Criteria

1. WHEN the system settings page loads THEN the system SHALL display the current version as "main branch latest" for initial deployments
2. WHEN a user navigates to the upgrade section in system settings THEN the system SHALL fetch and display available branches and tags from https://github.com/aws-solutions-library-samples/guidance-for-medialake-on-aws
3. WHEN the API call to /updates/versions is made THEN the system SHALL return a list of available branches and tags with their metadata (name, commit SHA, date)
4. IF the GitHub API is unavailable THEN the system SHALL display an appropriate error message and allow retry
5. WHEN displaying versions THEN the system SHALL clearly distinguish between branches and tags in the UI

### Requirement 2

**User Story:** As a MediaLake super administrator, I want to trigger an upgrade to a selected version, so that my MediaLake deployment stays current with the latest features and fixes.

#### Acceptance Criteria

1. WHEN a super administrator selects a version and clicks the upgrade button THEN the system SHALL trigger the CodePipeline execution with the selected version
2. WHEN the upgrade is initiated THEN the system SHALL modify the CodePipeline source configuration to download the specified tag or branch
3. WHEN the pipeline starts THEN the system SHALL update the system settings to indicate an upgrade is in progress
4. IF the user tries to initiate another upgrade while one is in progress THEN the system SHALL prevent the action and display an appropriate message
5. WHEN the upgrade button is clicked THEN the system SHALL require user confirmation before proceeding
6. WHEN selecting versions THEN the system SHALL support both tagged releases and any available branch

### Requirement 3

**User Story:** As a MediaLake super administrator, I want to track the upgrade progress and status, so that I know when the upgrade is complete and whether it was successful.

#### Acceptance Criteria

1. WHEN an upgrade is in progress THEN the system SHALL display the current pipeline execution status
2. WHEN the pipeline completes successfully THEN the system SHALL update the system settings table with the new version information
3. WHEN the pipeline fails THEN the system SHALL display the failure reason and maintain the previous version information
4. WHEN viewing the upgrade status THEN the system SHALL show the current version, target version (if upgrading), and last upgrade timestamp
5. WHEN the upgrade completes THEN the system SHALL provide a link to view the pipeline execution details in AWS Console

### Requirement 4

**User Story:** As a MediaLake super administrator, I want the system to maintain version history and rollback capabilities, so that I can revert to a previous version if needed.

#### Acceptance Criteria

1. WHEN an upgrade completes THEN the system SHALL store the previous version information for potential rollback
2. WHEN viewing upgrade history THEN the system SHALL display the last 10 upgrade attempts with their status and timestamps
3. WHEN a rollback is requested THEN the system SHALL allow upgrading to any previously successful version
4. IF a rollback is initiated THEN the system SHALL follow the same upgrade process but to the previous version
5. WHEN storing version history THEN the system SHALL include upgrade duration and any relevant metadata

### Requirement 5

**User Story:** As a MediaLake super administrator, I want to control who can trigger upgrades, so that only authorized personnel can modify the system deployment.

#### Acceptance Criteria

1. WHEN a user attempts to access the upgrade functionality THEN the system SHALL verify the user belongs to the superAdministrators group
2. WHEN a non-super administrator tries to access upgrade features THEN the system SHALL display an access denied message
3. WHEN the upgrade UI loads THEN the system SHALL only display upgrade controls to users in the superAdministrators group
4. WHEN API calls are made to upgrade endpoints THEN the system SHALL validate superAdministrators group membership
5. WHEN checking permissions THEN the system SHALL use the superAdministrators group defined in the auth seeder custom resource

### Requirement 6

**User Story:** As a MediaLake super administrator, I want to schedule upgrades during maintenance windows, so that I can minimize disruption to users.

#### Acceptance Criteria

1. WHEN scheduling an upgrade THEN the system SHALL allow setting a future date and time for execution
2. WHEN a scheduled upgrade time arrives THEN the system SHALL automatically trigger the upgrade process
3. IF a scheduled upgrade conflicts with system usage THEN the system SHALL provide options to proceed or reschedule
4. WHEN viewing scheduled upgrades THEN the system SHALL display upcoming scheduled upgrades with the ability to cancel or modify
5. WHEN scheduling upgrades THEN the system SHALL validate that the selected time is in the future and within reasonable bounds
