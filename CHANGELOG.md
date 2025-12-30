# Changelog

## [1.3.0] - 2025-12-30

### Features

- feat: Favorites implementation

### Bug Fixes

- fix: resolve infinite loop in pipeline creation for cyclic graphs
- fix: use configured Max Concurrent Executions parameter instead of hardcoded value

## [1.2.2] - 2025-12-22

### Bug Fixes

- fix: Workflow Completed trigger to match actual event structure

### Other Changes

- ci: update to push main-v2 to github

## [1.2.1] - 2025-12-20

### Bug Fixes

- fix: Workflow Completed trigger to match actual event structure

### Other Changes

- ci: update to push main-v2 to github
- ci: disable eslint temporarily
- ci: fix regex issue and removed test steps
- ci: add deduplication to changelog

## [1.2.0] - 2025-12-19

### Features

- feat: adds optional custom domain support for cloudfront distribution
- feat: add intelligent tiering and lifecycle policies to s3
- feat: add TwelveLabs Marengo Embed 3.0 provider with 512D embeddings
- feat: implement MediaConvert throttling mitigation with module-level caching
- feat: add mts video extension support
- feat: migrate hardcoded strings to translation system
- feat: add ApiStatusModal for search provider API key save with masked input
- feat: add ApiStatusModal for asset delete operations
- feat: Add backward-compatible asset_embeddings support with dual-query search

### Bug Fixes

- fix: missing support for vbr/cbr audio/video
- fix: Collections itemCount bugs
- fix: resolve S3 notification removal error for connectors
- fix: resolve S3 notification removal error for connectors
- fix: pipeline map itemspath parameter
- fix: restore pipeline delete dialog to show pipeline name confirmation
- fix: add retry configuration for s3 vectors service unavailable errors
- fix: correct model_id parameter to model_id_text in transcription pipelines
- fix: filter pipeline executions to show only MediaLake pipelines
- fix: resolve embedding store retry failures and flatten payload structure
- fix: filter map child executions from database
- fix: update to OS version

## [1.1.0] - 2025-11-25

### Features

- feat: enhance DLQ with detailed OpenSearch error information
- feat: implement bulk delete with centralized deletion service
- feat: eventbridge trigger node
- feat: add custom prompts with user-friendly labels to bedrock content processor

### Bug Fixes

- fix: prevent label duplication in node configuration
- fix: improve list view UI consistency and functionality
- fix: trim whitespace from subnet IDs to prevent null AZ error
- fix: resolve case-sensitive pattern matching in TriggerTypeChips
- fix: shorten password confirmation placeholder text
- fix: change twelvelabs-api isExternal flag to false
- fix: resolve lambda_handler not found error in asset deletion
- fix: improve pipeline button responsiveness
- fix: remove debug logs
- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video

## [6.0.0] - 2025-11-22

### ⚠ BREAKING CHANGES

- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release

### ✨ Features

- feat: add custom prompts with user-friendly labels to bedrock content processor
- feat: video thumbnail in stamp player
- feat: video thumbnail in stamp player
- feat: User upload through the UI initial implementation
- feat: User upload through the UI initial implementation
- feat: add loader when editing pipeline
- feat: add loader when editing pipeline
- feat: Add i18n mode for internationalization tasks
- feat: Add i18n mode for internationalization tasks
- feat: provider metadata display
- feat: provider metadata display
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: disable update button no changes
- feat: disable update button no changes
- feat: initial Semantic release v1.0
- feat: initial Semantic release v1.0
- feat: initial release v1 test
- feat: initial release v1 test
- feat: initial Semantic Version 1.0.0
- feat: initial Semantic Version 1.0.0

### 🐛 Bug Fixes

- fix: remove debug logs
- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video
- fix: update image formats to production-verified list
- fix: consolidate extension list
- fix: Update to API parameter options for deployment of new s3 bucket that was blocking creation of new S3 buckets in connectors
- fix: profile-page-api-response-parsing
- fix: profile-page-api-response-parsing
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: correct pipeline delete navigation path
- fix: correct pipeline delete navigation path
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: executions sorting complete
- fix: executions sorting complete
- fix: executions sorting load more
- fix: executions sorting load more
- fix: clean up SQS resources when updating pipelines
- fix: clean up SQS resources when updating pipelines
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: import button small screen
- fix: import button small screen
- fix: bumped omakase to 0.22.1
- fix: bumped omakase to 0.22.1
- fix: StoragePath using filename instead of full path in rename operation
- fix: StoragePath using filename instead of full path in rename operation
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: ci test
- fix: ci test
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline

## [5.0.0] - 2025-11-22

### ⚠ BREAKING CHANGES

- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release

### ✨ Features

- feat: add custom prompts with user-friendly labels to bedrock content processor
- feat: video thumbnail in stamp player
- feat: video thumbnail in stamp player
- feat: User upload through the UI initial implementation
- feat: User upload through the UI initial implementation
- feat: add loader when editing pipeline
- feat: add loader when editing pipeline
- feat: Add i18n mode for internationalization tasks
- feat: Add i18n mode for internationalization tasks
- feat: provider metadata display
- feat: provider metadata display
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: disable update button no changes
- feat: disable update button no changes
- feat: initial Semantic release v1.0
- feat: initial Semantic release v1.0
- feat: initial release v1 test
- feat: initial release v1 test
- feat: initial Semantic Version 1.0.0
- feat: initial Semantic Version 1.0.0

### 🐛 Bug Fixes

- fix: remove debug logs
- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video
- fix: update image formats to production-verified list
- fix: consolidate extension list
- fix: Update to API parameter options for deployment of new s3 bucket that was blocking creation of new S3 buckets in connectors
- fix: profile-page-api-response-parsing
- fix: profile-page-api-response-parsing
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: correct pipeline delete navigation path
- fix: correct pipeline delete navigation path
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: executions sorting complete
- fix: executions sorting complete
- fix: executions sorting load more
- fix: executions sorting load more
- fix: clean up SQS resources when updating pipelines
- fix: clean up SQS resources when updating pipelines
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: import button small screen
- fix: import button small screen
- fix: bumped omakase to 0.22.1
- fix: bumped omakase to 0.22.1
- fix: StoragePath using filename instead of full path in rename operation
- fix: StoragePath using filename instead of full path in rename operation
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: ci test
- fix: ci test
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline

## [4.0.0] - 2025-11-22

### ⚠ BREAKING CHANGES

- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release

### ✨ Features

- feat: add custom prompts with user-friendly labels to bedrock content processor
- feat: video thumbnail in stamp player
- feat: video thumbnail in stamp player
- feat: User upload through the UI initial implementation
- feat: User upload through the UI initial implementation
- feat: add loader when editing pipeline
- feat: add loader when editing pipeline
- feat: Add i18n mode for internationalization tasks
- feat: Add i18n mode for internationalization tasks
- feat: provider metadata display
- feat: provider metadata display
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: disable update button no changes
- feat: disable update button no changes
- feat: initial Semantic release v1.0
- feat: initial Semantic release v1.0
- feat: initial release v1 test
- feat: initial release v1 test
- feat: initial Semantic Version 1.0.0
- feat: initial Semantic Version 1.0.0

### 🐛 Bug Fixes

- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video
- fix: update image formats to production-verified list
- fix: consolidate extension list
- fix: Update to API parameter options for deployment of new s3 bucket that was blocking creation of new S3 buckets in connectors
- fix: profile-page-api-response-parsing
- fix: profile-page-api-response-parsing
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: correct pipeline delete navigation path
- fix: correct pipeline delete navigation path
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: executions sorting complete
- fix: executions sorting complete
- fix: executions sorting load more
- fix: executions sorting load more
- fix: clean up SQS resources when updating pipelines
- fix: clean up SQS resources when updating pipelines
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: import button small screen
- fix: import button small screen
- fix: bumped omakase to 0.22.1
- fix: bumped omakase to 0.22.1
- fix: StoragePath using filename instead of full path in rename operation
- fix: StoragePath using filename instead of full path in rename operation
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: ci test
- fix: ci test
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline

## [3.0.0] - 2025-11-22

### ⚠ BREAKING CHANGES

- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release

### ✨ Features

- feat: add custom prompts with user-friendly labels to bedrock content processor
- feat: video thumbnail in stamp player
- feat: video thumbnail in stamp player
- feat: User upload through the UI initial implementation
- feat: User upload through the UI initial implementation
- feat: add loader when editing pipeline
- feat: add loader when editing pipeline
- feat: Add i18n mode for internationalization tasks
- feat: Add i18n mode for internationalization tasks
- feat: provider metadata display
- feat: provider metadata display
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: disable update button no changes
- feat: disable update button no changes
- feat: initial Semantic release v1.0
- feat: initial Semantic release v1.0
- feat: initial release v1 test
- feat: initial release v1 test
- feat: initial Semantic Version 1.0.0
- feat: initial Semantic Version 1.0.0

### 🐛 Bug Fixes

- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video
- fix: update image formats to production-verified list
- fix: consolidate extension list
- fix: Update to API parameter options for deployment of new s3 bucket that was blocking creation of new S3 buckets in connectors
- fix: profile-page-api-response-parsing
- fix: profile-page-api-response-parsing
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: correct pipeline delete navigation path
- fix: correct pipeline delete navigation path
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: executions sorting complete
- fix: executions sorting complete
- fix: executions sorting load more
- fix: executions sorting load more
- fix: clean up SQS resources when updating pipelines
- fix: clean up SQS resources when updating pipelines
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: import button small screen
- fix: import button small screen
- fix: bumped omakase to 0.22.1
- fix: bumped omakase to 0.22.1
- fix: StoragePath using filename instead of full path in rename operation
- fix: StoragePath using filename instead of full path in rename operation
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: ci test
- fix: ci test
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline

## [2.0.0] - 2025-11-21

### ⚠ BREAKING CHANGES

- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release

### ✨ Features

- feat: video thumbnail in stamp player
- feat: video thumbnail in stamp player
- feat: User upload through the UI initial implementation
- feat: User upload through the UI initial implementation
- feat: add loader when editing pipeline
- feat: add loader when editing pipeline
- feat: Add i18n mode for internationalization tasks
- feat: Add i18n mode for internationalization tasks
- feat: provider metadata display
- feat: provider metadata display
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: add model-dependent embedding type filtering for twelvelabs search clips to...
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: Add glassy effect to pipeline toolbar and auto-refresh on save
- feat: disable update button no changes
- feat: disable update button no changes
- feat: initial Semantic release v1.0
- feat: initial Semantic release v1.0
- feat: initial release v1 test
- feat: initial release v1 test
- feat: initial Semantic Version 1.0.0
- feat: initial Semantic Version 1.0.0

### 🐛 Bug Fixes

- fix: remove sensitive data from log statements
- fix: missing support for vbr/cbr audio/video
- fix: update image formats to production-verified list
- fix: consolidate extension list
- fix: Update to API parameter options for deployment of new s3 bucket that was blocking creation of new S3 buckets in connectors
- fix: profile-page-api-response-parsing
- fix: profile-page-api-response-parsing
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: use Distributed Map for embedding pipelines to support better scale
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: correct pipeline delete navigation path
- fix: correct pipeline delete navigation path
- fix: prevent canvas reset during spacebar drag in ImageViewer
- fix: executions sorting complete
- fix: executions sorting complete
- fix: executions sorting load more
- fix: executions sorting load more
- fix: clean up SQS resources when updating pipelines
- fix: clean up SQS resources when updating pipelines
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: api key management: ui label cutoff, partition key mismatch, optional...
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: Update to IAM roles that manage infrastructure for media lake
- fix: import button small screen
- fix: import button small screen
- fix: bumped omakase to 0.22.1
- fix: bumped omakase to 0.22.1
- fix: StoragePath using filename instead of full path in rename operation
- fix: StoragePath using filename instead of full path in rename operation
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: Add on_delete handlers to pipeline custom resources for graceful rollback
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: update stack permissions and S3 Vector bucket naming schema
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: implement CloudWatch log group cleanup for Step Functions
- fix: ci test
- fix: ci test
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline
- fix: resolve Bedrock token limit exceeded error in video transcription pipeline

## [1.0.1] - 2025-11-21

### Bug Fixes

- fix: update image formats to production-verified list
- fix: consolidate extension list

## [1.0.0] - 2025-11-21

### Bug Fixes

- fix: update image formats to production-verified list
- fix: consolidate extension list

### Features

- feat: Initial Semantic Versioning release 1.0.0
- feat: User uploads initial release
