// lambda_middleware.js
const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const { cloneDeep } = require('lodash');

class LambdaMiddleware {
  constructor(opts = {}) {
    Object.assign(this, { maxResponseSize: 240 * 1024, maxRetries: 3 }, opts);

    this.eventBusName = this.eventBusName || process.env.EVENT_BUS_NAME;
    if (!this.eventBusName) throw new Error('EVENT_BUS_NAME env-var required');

    this.externalPayloadBucket =
      this.externalPayloadBucket || process.env.EXTERNAL_PAYLOAD_BUCKET;
    if (!this.externalPayloadBucket)
      throw new Error('EXTERNAL_PAYLOAD_BUCKET env-var required');

    this.s3 = new AWS.S3();
    this.eb = new AWS.EventBridge();

    this.service   = process.env.SERVICE        || 'undefined_service';
    this.stepName  = process.env.STEP_NAME      || 'undefined_step';
    this.pipeName  = process.env.PIPELINE_NAME  || 'undefined_pipeline';
    this.isFirst   = (process.env.IS_FIRST || 'false').toLowerCase() === 'true';
    this.isLast    = (process.env.IS_LAST  || 'false').toLowerCase() === 'true';
  }

  /* ───────────── helpers ───────────── */
  _trueOriginal(ev) {
    let cur = ev.originalEvent || ev;
    while (cur && cur.payload && cur.payload.event) cur = cur.payload.event;
    return cur;
  }

  /* ───────────── formatter ───────────── */
  async _format(result, orig, stepStart) {
    /* ── business data (strip external-job fields) ─────────────────── */
    const data =
      result && typeof result === 'object' ? { ...result } : { value: result };

    const extId = data.externalJobId     || '';
    const extSt = data.externalJobStatus || '';
    const extRs = data.externalJobResult || '';
    delete data.externalJobId;
    delete data.externalJobStatus;
    delete data.externalJobResult;

    /* ── metadata block ─────────────────────────────────────────────── */
    const now = Date.now() / 1000;
    const meta = {
      service: this.service,
      stepName: this.stepName,
      stepStatus: 'Completed',
      stepResult: 'Success',

      pipelineTraceId:
        orig.metadata?.pipelineTraceId || uuidv4(),
      stepExecutionStartTime:
        orig.metadata?.stepExecutionStartTime || stepStart,
      stepExecutionEndTime: now,
      stepExecutionDuration: +(now - stepStart).toFixed(3),

      pipelineExecutionStartTime: orig.pipelineExecutionStartTime || '',
      pipelineExecutionEndTime:   this.isLast ? now : '',

      pipelineName: this.pipeName,
      pipelineStatus: this.isFirst
        ? 'Started'
        : this.isLast
        ? 'Completed'
        : 'InProgress',

      pipelineId:         orig.pipelineId         || '',
      pipelineExecutionId: orig.pipelineExecutionId || '',

      externalJobResult:  extRs,
      externalJobId:      extId,
      externalJobStatus:  extSt,

      stepExternalPayload: 'False',
      stepExternalPayloadLocation: {},
    };

    /* ── isolate the current asset detail ───────────────────────────── */
    const asset =
      orig?.input?.detail   // events wrapped by Step Functions
        ?? orig?.detail     // already-flattened events
        ?? orig;            // fallback – leave untouched

    /* ── carry over previous assets, then append the current one ────── */
    let prevAssets = [];

    if (orig && typeof orig === 'object') {
      if (Array.isArray(orig.payload?.assets)) {
        prevAssets = cloneDeep(orig.payload.assets);
      } else if (Array.isArray(orig.assets)) {
        prevAssets = cloneDeep(orig.assets);
      }
    }

    const assets = [
      ...prevAssets,
      ...(asset ? [cloneDeep(asset)] : []),
    ];

    let payload = { data, assets };

    /* ── off-load oversized payloads to S3 ──────────────────────────── */
    const raw = Buffer.from(JSON.stringify(payload));
    if (raw.length > this.maxResponseSize) {
      const key = `${
        meta.pipelineExecutionId || 'unknown'
      }/${uuidv4()}-payload.json`;

      await this.s3
        .putObject({
          Bucket: this.externalPayloadBucket,
          Key: key,
          Body: raw,
        })
        .promise();

      meta.stepExternalPayload = 'True';
      meta.stepExternalPayloadLocation = {
        bucket: this.externalPayloadBucket,
        key,
      };
      payload.data = {}; // shrink inline payload
    }

    return { metadata: meta, payload };
  }

  /* ───────────── publisher ───────────── */
  async _publish(out) {
    try {
      await this.eb
        .putEvents({
          Entries: [
            {
              Source: this.service,
              DetailType: `${this.stepName}Output`,
              Detail: JSON.stringify(out),
              EventBusName: this.eventBusName,
            },
          ],
        })
        .promise();
    } catch (e) {
      console.error('EventBridge publish failed', e);
    }
  }

  /* ───────────── wrapper ───────────── */
  middleware(handler) {
    return async (event, ctx) => {
      const orig  = cloneDeep(this._trueOriginal(event));
      const start = Date.now() / 1000;

      let retries = 0,
          res;

      /* retry-with-backoff loop */
      while (true) {
        try {
          res = await handler(event, ctx);
          break;
        } catch (e) {
          if (retries++ < this.maxRetries) {
            await new Promise((r) =>
              setTimeout(r, Math.min(2 ** retries * 1000, 30000))
            );
            continue;
          }
          throw e;
        }
      }

      const out = await this._format(res, orig, start);
      await this._publish(out);
      return out;
    };
  }
}

/* ─────────── factory + exports ─────────── */
function lambdaMiddleware(options = {}) {
  const mw = new LambdaMiddleware(options);
  return (handler) => mw.middleware(handler);
}

module.exports = { lambdaMiddleware, LambdaMiddleware };
