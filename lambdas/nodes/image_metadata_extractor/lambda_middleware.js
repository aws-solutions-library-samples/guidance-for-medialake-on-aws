const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const { Logger } = require('@aws-lambda-powertools/logger');
const { Metrics, MetricUnit } = require('@aws-lambda-powertools/metrics');
const { Tracer } = require('@aws-lambda-powertools/tracer');

// Helper sleep function (using Promise)
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class LambdaMiddleware {
  /**
   * @param {Object} params
   * @param {string} params.eventBusName
   * @param {string} [params.metricsNamespace='MediaLake']
   * @param {number} [params.maxEventSize=256000]
   * @param {boolean} [params.cleanupS3=true]
   * @param {string} [params.largePayloadBucket]
   * @param {number} [params.maxRetries=3]
   * @param {boolean} [params.standardizePayloads=true]
   * @param {string} [params.externalPayloadBucket]
   * @param {number} [params.maxResponseSize=245760] // 240KB in bytes
   */
  constructor({
    eventBusName,
    metricsNamespace = 'MediaLake',
    maxEventSize = 256000,
    cleanupS3 = true,
    largePayloadBucket,
    maxRetries = 3,
    standardizePayloads = true,
    externalPayloadBucket,
    maxResponseSize = 240 * 1024,
  }) {
    // Initialize clients and instance properties
    this.eventBusName = eventBusName;
    this.maxEventSize = maxEventSize;
    this.cleanupS3 = cleanupS3;
    this.maxRetries = maxRetries;
    this.maxResponseSize = maxResponseSize;

    this.s3 = new AWS.S3();
    this.eventBridge = new AWS.EventBridge();

    // The large and external payload buckets are either passed or obtained from env variables.
    this.largePayloadBucket =
      largePayloadBucket || process.env.EXTERNAL_PAYLOAD_BUCKET;
    if (!this.largePayloadBucket) {
      throw new Error(
        "largePayloadBucket must be provided or EXTERNAL_PAYLOAD_BUCKET environment variable must be set"
      );
    }
    this.externalPayloadBucket =
      externalPayloadBucket || process.env.EXTERNAL_PAYLOAD_BUCKET;
    if (!this.externalPayloadBucket) {
      throw new Error(
        "externalPayloadBucket must be provided or EXTERNAL_PAYLOAD_BUCKET environment variable must be set"
      );
    }

    this.serviceName = process.env.SERVICE_NAME || 'undefined_service';
    this.logger = new Logger({ serviceName: this.serviceName });
    this.metrics = new Metrics({ namespace: metricsNamespace, serviceName: this.serviceName });
    this.tracer = new Tracer({ serviceName: this.serviceName });

    this.tempS3Objects = [];
    this.standardizePayloads = standardizePayloads;

    this.retryCount = 0;
    this.retryErrors = new Set();
  }

  shouldRetry(error) {
    const RETRYABLE_ERRORS = [
      'RequestTimeout',
      'InternalServerError',
      'ServiceUnavailable',
      'ConnectionError',
      'ThrottlingException',
      'TooManyRequestsException',
      'ProvisionedThroughputExceededException',
    ];
    const errorType = error.name;
    this.retryErrors.add(errorType);
    return (
      this.retryCount < this.maxRetries &&
      RETRYABLE_ERRORS.some(err => errorType.includes(err))
    );
  }

  async emitProgress(context, progress, status, detail) {
    const progressDetails = {
      function_name: context.functionName,
      request_id: context.awsRequestId,
      progress,
      status,
      timestamp: Math.floor(Date.now() / 1000),
    };
    if (detail) {
      Object.assign(progressDetails, detail);
    }
    await this.emitEvent(
      "FunctionExecutionProgress",
      progressDetails,
      [context.invokedFunctionArn]
    );
  }

  async standardizeInput(event) {
    let newEvent = { ...event };

    if (!this.standardizePayloads) return newEvent;

    // If the event contains an S3 reference
    if (newEvent.s3_bucket && newEvent.s3_key) {
      try {
        const response = await this.s3
          .getObject({
            Bucket: newEvent.s3_bucket,
            Key: newEvent.s3_key,
          })
          .promise();
        newEvent = JSON.parse(response.Body.toString('utf-8'));
      } catch (e) {
        this.logger.error(`Failed to fetch payload from S3: ${e.message}`);
        throw e;
      }
    }

    // Processing items that reference S3 and specify an iteration.
    if (
      newEvent.item &&
      typeof newEvent.item === 'object' &&
      newEvent.item.item &&
      newEvent.item.iteration !== undefined
    ) {
      try {
        this.logger.info("Detected item with S3 reference and iteration");
        const { bucket, key } = newEvent.item.item;
        const iteration = newEvent.item.iteration;
        this.logger.info(`Retrieving payload from S3: bucket=${bucket}, key=${key}, iteration=${iteration}`);
        const response = await this.s3
          .getObject({ Bucket: bucket, Key: key })
          .promise();
        const payloadJson = JSON.parse(response.Body.toString('utf-8'));
        if (
          payloadJson.externalTaskResults &&
          Array.isArray(payloadJson.externalTaskResults)
        ) {
          const arrayData = payloadJson.externalTaskResults;
          this.logger.info(`Found array with ${arrayData.length} items in payload`);
          if (iteration >= 0 && iteration < arrayData.length) {
            this.logger.info(`Using item at index ${iteration} from array`);
            newEvent.item = arrayData[iteration];
          } else {
            this.logger.warn(`Iteration ${iteration} is out of bounds for array of length ${arrayData.length}`);
          }
        } else {
          this.logger.info("No array found in payload, using the entire payload as the item");
          newEvent.item = payloadJson;
        }
        this.logger.info("Successfully processed item with S3 reference and iteration");
      } catch (e) {
        this.logger.error(`Failed to process item with S3 reference: ${e.message}`);
        throw e;
      }
    }

    // Handle external payload flag by retrieving the payload from S3.
    if (newEvent.metadata && newEvent.metadata.externalPayload) {
      try {
        this.logger.info("Detected external payload flag, retrieving payload from S3");
        let bucket, key;
        if (
          newEvent.payload &&
          newEvent.payload.externalTaskResults &&
          Array.isArray(newEvent.payload.externalTaskResults) &&
          newEvent.payload.externalTaskResults.length > 0
        ) {
          if (newEvent.payload.externalTaskResults[0].item) {
            ({ bucket, key } = newEvent.payload.externalTaskResults[0].item);
          } else {
            bucket = newEvent.payload.externalTaskResults[0].bucket;
            key = newEvent.payload.externalTaskResults[0].key;
          }
          this.logger.info(`Retrieving external payload from externalTaskResults: bucket=${bucket}, key=${key}`);
        } else if (newEvent.payload && newEvent.payload.externalPayloadLocation) {
          if (Array.isArray(newEvent.payload.externalPayloadLocation) && newEvent.payload.externalPayloadLocation.length > 0) {
            ({ bucket, key } = newEvent.payload.externalPayloadLocation[0]);
          } else {
            ({ bucket, key } = newEvent.payload.externalPayloadLocation);
          }
          this.logger.info(`Retrieving external payload from externalPayloadLocation: bucket=${bucket}, key=${key}`);
        } else {
          this.logger.error("External payload flag is set but payload location is missing");
          throw new Error("External payload flag is set but payload location is missing");
        }
        const response = await this.s3.getObject({ Bucket: bucket, Key: key }).promise();
        newEvent.payload = JSON.parse(response.Body.toString('utf-8'));
        newEvent.metadata.externalPayload = false;
        this.logger.info("Successfully retrieved external payload from S3");
      } catch (e) {
        this.logger.error(`Failed to retrieve external payload from S3: ${e.message}`);
        throw e;
      }
    }

    // Ensure metadata exists and add timestamp and service info.
    if (!newEvent.metadata) {
      newEvent.metadata = {};
    }
    newEvent.metadata.timestamp = Math.floor(Date.now() / 1000);
    newEvent.metadata.service = this.serviceName;

    // If payload key does not exist, promote item to payload.
    if (!newEvent.payload && newEvent.item) {
      newEvent.payload = newEvent.item;
      delete newEvent.item;
    }

    return newEvent;
  }

  async standardizeOutput(result, originalEvent = {}) {
    const payloadContent = typeof result === 'object' ? result : { data: result };

    const incomingStatus =
      originalEvent.metadata && originalEvent.metadata.stepStatus
        ? originalEvent.metadata.stepStatus
        : "InProgress";
    const updatedStatus = incomingStatus === "InProgress" ? "Completed" : incomingStatus;

    const metadata = {
      service: this.serviceName,
      stepName: (originalEvent.metadata && originalEvent.metadata.stepName) || "assetRegistration",
      stepStatus: updatedStatus,
      stepId: uuidv4(),
      externalTaskId: "",
      externalTaskStatus: "",
      externalPayload: false,
      externalPayloadLocation: null,
      stepCost: "",
      stepResult: "",
      stepDuration: "",
      pipelineAssets: [],
    };

    let existingPipelineAssets = [];
    if (payloadContent.pipelineAssets) {
      existingPipelineAssets = payloadContent.pipelineAssets;
      this.logger.info("Found pipelineAssets at top level of payloadContent");
      delete payloadContent.pipelineAssets;
    } else if (payloadContent.metadata && payloadContent.metadata.pipelineAssets) {
      existingPipelineAssets = payloadContent.metadata.pipelineAssets;
      this.logger.info("Found pipelineAssets inside payloadContent.metadata");
      delete payloadContent.metadata.pipelineAssets;
    } else if (originalEvent.metadata && originalEvent.metadata.pipelineAssets) {
      existingPipelineAssets = originalEvent.metadata.pipelineAssets;
      this.logger.info("Found pipelineAssets in originalEvent.metadata");
    } else if (originalEvent.payload && originalEvent.payload.pipelineAssets) {
      existingPipelineAssets = originalEvent.payload.pipelineAssets;
      this.logger.info("Found pipelineAssets in originalEvent.payload");
      delete originalEvent.payload.pipelineAssets;
    }
    if (Array.isArray(existingPipelineAssets)) {
      metadata.pipelineAssets = metadata.pipelineAssets.concat(existingPipelineAssets);
    } else {
      this.logger.warn("pipelineAssets found but not an array; ignoring.");
    }

    let existingAssets = [];
    if (payloadContent.assets) {
      existingAssets = payloadContent.assets;
      this.logger.info(`Found existing assets in result: ${JSON.stringify(existingAssets)}`);
    } else if (originalEvent.payload && originalEvent.payload.assets) {
      existingAssets = originalEvent.payload.assets;
      this.logger.info(`Found existing assets in original event: ${JSON.stringify(existingAssets)}`);
    }
    if (!Array.isArray(existingAssets)) {
      existingAssets = [];
    }

    const flattenedPayload = {
      metadata: payloadContent.metadata || {},
      originalEvent: originalEvent || payloadContent,
    };

    const output = { metadata, payload: flattenedPayload };
    const outputSize = Buffer.byteLength(JSON.stringify(output), 'utf-8');
    this.logger.info(`Output size: ${outputSize} bytes`);
    if (outputSize > this.maxResponseSize) {
      this.logger.info(`Output size ${outputSize} exceeds limit ${this.maxResponseSize}, storing payload in S3`);
      const workflowId = (originalEvent.metadata && originalEvent.metadata.workflowId) || "unknown";
      const executionId = (originalEvent.metadata && originalEvent.metadata.executionId) || "unknown";
      const stepId = metadata.stepId;
      const s3Key = `${workflowId}/${executionId}/${stepId}-payload.json`;
      try {
        await this.s3.putObject({
          Bucket: this.externalPayloadBucket,
          Key: s3Key,
          Body: JSON.stringify(output.payload)
        }).promise();
        this.logger.info(`Large payload written to S3: ${s3Key}`);
        output.metadata.externalPayload = true;

        let itemCount = 1;
        if (output.payload.externalTaskResults && Array.isArray(output.payload.externalTaskResults)) {
          itemCount = output.payload.externalTaskResults.length;
          this.logger.info(`Found ${itemCount} items in externalTaskResults array`);
        } else {
          this.logger.info("Could not determine item count, defaulting to 1");
        }

        const references = [];
        for (let i = 0; i < itemCount; i++) {
          references.push({
            item: { bucket: this.externalPayloadBucket, key: s3Key },
            iteration: i,
          });
        }
        if (output.payload.key) {
          output.payload = { externalTaskResults: references };
        }
        this.logger.info(`Created ${references.length} references to S3 object`);
      } catch (e) {
        this.logger.error(`Failed to write payload to S3: ${e.message}`);
        throw e;
      }
    }

    if (payloadContent.externalTaskId) {
      metadata.externalTaskId = payloadContent.externalTaskId;
      delete payloadContent.externalTaskId;
      this.logger.info(`Carried over externalTaskId: ${metadata.externalTaskId}`);
    }
    if (payloadContent.externalTaskStatus) {
      metadata.externalTaskStatus = payloadContent.externalTaskStatus;
      delete payloadContent.externalTaskStatus;
      this.logger.info(`Carried over externalTaskStatus: ${metadata.externalTaskStatus}`);
    }

    const originalItem = originalEvent ? (originalEvent.item || originalEvent.payload) : null;
    if (originalItem && originalItem.mediaType === "Audio") {
      ["start_time", "end_time"].forEach(key => {
        if (originalItem[key] !== undefined) {
          output.payload[key] = originalItem[key];
          this.logger.info(`Carried over ${key} from original event`);
        }
      });
    }

    return output;
  }

  async emitEvent(detailType, detail, resources = []) {
    try {
      const event = {
        Source: this.serviceName,
        DetailType: detailType,
        Detail: JSON.stringify(detail),
        EventBusName: this.eventBusName,
        Resources: resources,
      };
      const eventSize = Buffer.byteLength(JSON.stringify(event), 'utf-8');
      if (eventSize > this.maxEventSize) {
        this.logger.info(`Event size ${eventSize} exceeds limit ${this.maxEventSize}, using S3`);
        const key = `events/${Math.floor(Date.now() / 1000)}-${detailType}.json`;
        await this.s3.putObject({
          Bucket: this.largePayloadBucket,
          Key: key,
          Body: JSON.stringify(detail)
        }).promise();
        this.tempS3Objects.push(key);
        event.Detail = JSON.stringify({
          s3_bucket: this.largePayloadBucket,
          s3_key: key,
          original_size: eventSize,
        });
      }
      await this.eventBridge.putEvents({ Entries: [event] }).promise();
    } catch (e) {
      this.logger.error(`Failed to emit event: ${e.message}`);
      this.metrics.addMetric('FailedEvents', MetricUnit.Count, 1);
    }
  }

  async cleanupTempS3Objects() {
    if (!this.cleanupS3 || this.tempS3Objects.length === 0) return;
    try {
      const objectsToDelete = this.tempS3Objects.map(key => ({ Key: key }));
      await this.s3
        .deleteObjects({
          Bucket: this.largePayloadBucket,
          Delete: { Objects: objectsToDelete },
        })
        .promise();
      this.tempS3Objects = [];
    } catch (e) {
      this.logger.error(`Failed to cleanup S3 objects: ${e.message}`);
    }
  }

  async handleFailure(error, context) {
    const errorType = error.name;
    const errorDetails = {
      error_type: errorType,
      error_message: error.message,
      function_name: context.functionName,
      request_id: context.awsRequestId,
      function_version: context.functionVersion,
    };
    this.logger.error("Function execution failed", error);
    await this.emitEvent("FunctionExecutionFailure", errorDetails, [context.invokedFunctionArn]);
    this.metrics.addMetric("Errors", MetricUnit.Count, 1);
    this.metrics.addMetric(`Errors_${errorType}`, MetricUnit.Count, 1);
  }

  /**
   * Wraps a given handler function with the middleware logic.
   * @param {Function} handler - The original Lambda handler.
   * @returns {Function} A new handler function with middleware applied.
   */
  middleware(handler) {
    const self = this;
    return async function(event, context) {
      const startTime = Date.now();
      try {
        await self.emitEvent("FunctionExecutionStart", {
          function_name: context.functionName,
          request_id: context.awsRequestId,
          remaining_time: context.getRemainingTimeInMillis(),
        }, [context.invokedFunctionArn]);

        self.metrics.addDimension("FunctionName", context.functionName);
        self.metrics.addDimension("Environment", process.env.ENVIRONMENT || "undefined");

        const processedEvent = await self.standardizeInput(event);
        if (!processedEvent.metadata) {
          processedEvent.metadata = {};
        }
        processedEvent.metadata.stepName = context.functionName;
        if (!processedEvent.metadata.stepStatus) {
          processedEvent.metadata.stepStatus = "InProgress";
        }

        // Attach progress helper
        context.emitProgress = (progress, status, detail) => self.emitProgress(context, progress, status, detail);

        self.retryCount = 0;
        self.retryErrors.clear();

        self.logger.info(`Middleware before handler execution - function: ${context.functionName}, request_id: ${context.awsRequestId}`);

        let result;
        while (true) {
          try {
            result = await handler(processedEvent, context);
            break;
          } catch (e) {
            if (self.shouldRetry(e)) {
              self.retryCount += 1;
              const retryDelay = Math.min(2 ** self.retryCount * 1000, 30000);
              self.logger.warn(`Retrying after error (attempt ${self.retryCount}/${self.maxRetries})`, {
                error: e.message,
                error_type: e.name,
                retry_delay: retryDelay,
              });
              await self.emitEvent("FunctionExecutionRetry", {
                function_name: context.functionName,
                request_id: context.awsRequestId,
                error: e.message,
                error_type: e.name,
                retry_count: self.retryCount,
                retry_delay: retryDelay,
              }, [context.invokedFunctionArn]);
              await sleep(retryDelay);
              continue;
            }
            throw e;
          }
        }

        if (self.retryCount > 0) {
          self.metrics.addMetric("RetryAttempts", MetricUnit.Count, self.retryCount);
          self.retryErrors.forEach(errorType => {
            self.metrics.addMetric(`RetryErrors_${errorType}`, MetricUnit.Count, 1);
          });
        }

        self.logger.info(`Middleware after handler execution - function: ${context.functionName}, request_id: ${context.awsRequestId}`);

        const processedResult = await self.standardizeOutput(result, event);
        const executionTime = Date.now() - startTime;

        self.metrics.addMetric("Invocations", MetricUnit.Count, 1);
        self.metrics.addMetric("ExecutionTime", MetricUnit.Milliseconds, executionTime);
        self.metrics.addMetric("MemoryUsed", MetricUnit.Megabytes, parseFloat(context.memoryLimitInMB));

        if (!LambdaMiddleware._coldStartRecorded) {
          self.metrics.addMetric("ColdStart", MetricUnit.Count, 1);
          LambdaMiddleware._coldStartRecorded = true;
        }

        await self.emitEvent("FunctionExecutionComplete", {
          function_name: context.functionName,
          request_id: context.awsRequestId,
          execution_time_ms: executionTime,
          memory_used: context.memoryLimitInMB,
        }, [context.invokedFunctionArn]);

        return processedResult;
      } catch (e) {
        await self.handleFailure(e, context);
        throw e;
      } finally {
        await self.cleanupTempS3Objects();
      }
    };
  }
}

/**
 * A higher-order function to apply the middleware on a Lambda handler.
 * @param {Object} options - Middleware options.
 * @param {Function} handler - The original Lambda handler.
 * @returns {Function} A new handler function wrapped with middleware logic.
 */
function lambdaMiddleware(options) {
  const middlewareInstance = new LambdaMiddleware(options);
  return (handler) => middlewareInstance.middleware(handler);
}

module.exports = { lambdaMiddleware, LambdaMiddleware };
