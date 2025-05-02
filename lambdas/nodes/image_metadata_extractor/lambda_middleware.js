// lambda_middleware.js
const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const { cloneDeep } = require('lodash');

class LambdaMiddleware {
  /**
   * • Builds the exact output schema
   * • Publishes to EventBridge (bus = EVENT_BUS_NAME)
   * • Standardizes incoming events into {metadata, payload:{data, assets}}
   *   - skips if already in that shape
   *   - if looks like EventBridge (has top-level detail), normalises it
   *   - otherwise wraps full event in data and carries any existing assets
   * • Honors handler-returned `updatedAsset` to override assets
   */
  constructor(opts = {}) {
    Object.assign(this, { maxResponseSize: 240 * 1024, maxRetries: 3 }, opts);

    this.eventBusName = this.eventBusName || process.env.EVENT_BUS_NAME;
    if (!this.eventBusName) {
      throw new Error('EVENT_BUS_NAME env-var required');
    }

    this.externalPayloadBucket =
      this.externalPayloadBucket || process.env.EXTERNAL_PAYLOAD_BUCKET;
    if (!this.externalPayloadBucket) {
      throw new Error('EXTERNAL_PAYLOAD_BUCKET env-var required');
    }

    this.s3 = new AWS.S3();
    this.eb = new AWS.EventBridge();

    this.service  = process.env.SERVICE        || 'undefined_service';
    this.stepName = process.env.STEP_NAME      || 'undefined_step';
    this.pipeName = process.env.PIPELINE_NAME  || 'undefined_pipeline';
    this.isFirst  = (process.env.IS_FIRST || 'false').toLowerCase() === 'true';
    this.isLast   = (process.env.IS_LAST  || 'false').toLowerCase() === 'true';
  }

  // ───────────── unwrap helper ─────────────
  _trueOriginal(ev) {
    let cur = ev.originalEvent || ev;
    while (
      cur &&
      cur.payload &&
      typeof cur.payload === 'object' &&
      cur.payload.event
    ) {
      cur = cur.payload.event;
    }
    return cur;
  }

  // ─────────── standardize input helper ───────────
  _standardizeInput(ev) {
    // 1) Already standardised
    if (
      ev &&
      typeof ev === 'object' &&
      ev.metadata &&
      typeof ev.metadata === 'object' &&
      ev.payload &&
      typeof ev.payload === 'object' &&
      Object.prototype.hasOwnProperty.call(ev.payload, 'data') &&
      Object.prototype.hasOwnProperty.call(ev.payload, 'assets')
    ) {
      return ev;
    }

    // 1b) EventBridge envelope *whose detail is already standardised*
    if (ev.detail && typeof ev.detail === 'object') {
      const detail = ev.detail;
      if (
        detail.metadata &&
        typeof detail.metadata === 'object' &&
        detail.payload &&
        typeof detail.payload === 'object' &&
        Object.prototype.hasOwnProperty.call(detail.payload, 'data') &&
        Object.prototype.hasOwnProperty.call(detail.payload, 'assets')
      ) {
        // Bubble up execution / pipeline IDs if present on the outer envelope
        detail.pipelineExecutionId =
          detail.pipelineExecutionId || ev.pipelineExecutionId || '';
        detail.pipelineId = detail.pipelineId || ev.pipelineId || '';
        return detail;
      }
    }

    // 2) Plain EventBridge envelope (detail *not* standardised)
    if (ev.detail && typeof ev.detail === 'object' && !ev.payload && !ev.assets) {
      const meta = {
        service: this.service,
        stepName: this.stepName,
        pipelineName: this.pipeName,
        pipelineTraceId: uuidv4(),
        pipelineExecutionId: ev.pipelineExecutionId || '',
        pipelineId: ev.pipelineId || '',
      };
      return {
        metadata: meta,
        payload: {
          data: {},
          assets: [cloneDeep(ev.detail)],
        },
      };
    }

    // 3) Fallback: wrap full event in data, carry any existing assets
    const meta = {
      service: this.service,
      stepName: this.stepName,
      pipelineName: this.pipeName,
      pipelineTraceId:
        (ev.metadata && ev.metadata.pipelineTraceId) || uuidv4(),
      pipelineExecutionId: ev.pipelineExecutionId || '',
      pipelineId: ev.pipelineId || '',
    };
    const payload = { data: ev, assets: [] };
    if (ev.payload && Array.isArray(ev.payload.assets)) {
      payload.assets = cloneDeep(ev.payload.assets);
    } else if (Array.isArray(ev.assets)) {
      payload.assets = cloneDeep(ev.assets);
    }

    return { metadata: meta, payload };
  }

  // ─────────── formatter ───────────
  async _format(result, orig, stepStart) {
    const data =
      result && typeof result === 'object' ? { ...result } : { value: result };

    // ── strip external-job fields ──────────────────────────────────────
    let extId = data.externalJobId     || '';
    let extSt = data.externalJobStatus || '';
    let extRs = data.externalJobResult || '';
    delete data.externalJobId;
    delete data.externalJobStatus;
    delete data.externalJobResult;

    const now      = Date.now() / 1000;
    const prevMeta = orig.metadata || {};

    const meta = {
      service:                this.service,
      stepName:               this.stepName,
      stepStatus:             'Completed',
      stepResult:             'Success',
      pipelineTraceId:        prevMeta.pipelineTraceId || uuidv4(),
      stepExecutionStartTime: prevMeta.stepExecutionStartTime || stepStart,
      stepExecutionEndTime:   now,
      stepExecutionDuration:  +(now - stepStart).toFixed(3),
      pipelineExecutionStartTime: orig.pipelineExecutionStartTime || '',
      pipelineExecutionEndTime:   this.isLast ? now : '',
      pipelineName:           this.pipeName,
      pipelineStatus:         this.isFirst ? 'Started'
                          : this.isLast  ? 'Completed'
                          : 'InProgress',
      pipelineId:             orig.pipelineId          || '',
      pipelineExecutionId:    orig.pipelineExecutionId || '',
      externalJobResult:      extRs,
      externalJobId:          extId || prevMeta.externalJobId || '',
      externalJobStatus:      extSt,
      stepExternalPayload:    'False',
      stepExternalPayloadLocation: {},
    };

    // ── helper: flatten a standardised object to its inner assets ─────
    const innerAssets = (obj) => {
      if (
        obj && typeof obj === 'object' &&
        obj.metadata && typeof obj.metadata === 'object' &&
        obj.payload && typeof obj.payload === 'object' &&
        Array.isArray(obj.payload.assets)
      ) {
        return cloneDeep(obj.payload.assets);
      }
      return [cloneDeep(obj)];
    };

    // ── assemble `assets` ──────────────────────────────────────────────
    let assets;
    if (result && typeof result === 'object' && result.updatedAsset) {
      assets = [cloneDeep(result.updatedAsset)];
      delete data.updatedAsset;            // don’t leak this into `data`
    } else {
      const assetFromDetail =
        (orig.input && orig.input.detail) ||
        orig.detail ||
        orig;

      let prevAssets = [];
      if (orig.payload && Array.isArray(orig.payload.assets)) {
        prevAssets = cloneDeep(orig.payload.assets);
      } else if (Array.isArray(orig.assets)) {
        prevAssets = cloneDeep(orig.assets);
      }

      assets = [
        ...prevAssets,
        ...(assetFromDetail ? innerAssets(assetFromDetail) : []),
      ];
    }

    let payload = { data, assets };

    // ── off-load oversized payloads to S3 ──────────────────────────────
    const raw = Buffer.from(JSON.stringify(payload));
    if (raw.length > this.maxResponseSize) {
      const key = `${
        meta.pipelineExecutionId || 'unknown'
      }/${uuidv4()}-payload.json`;

      await this.s3
        .putObject({
          Bucket: this.externalPayloadBucket,
          Key:    key,
          Body:   raw,
        })
        .promise();

      meta.stepExternalPayload = 'True';
      meta.stepExternalPayloadLocation = { bucket: this.externalPayloadBucket, key };
      payload.data = {};
    }

    return { metadata: meta, payload };
  }


  // ─────────── publisher ───────────
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
      console.error('EventBridge publish failed:', e);
    }
  }

  // ─────────── wrapper ───────────
  middleware(handler) {
    return async (event, ctx) => {
      const raw = this._trueOriginal(event);
      const orig = cloneDeep(raw);

      const standardEvent = this._standardizeInput(orig);

      const start = Date.now() / 1000;
      let retries = 0,
        result;
      while (true) {
        try {
          result = await handler(standardEvent, ctx);
          break;
        } catch (err) {
          if (retries++ < this.maxRetries) {
            const backoff = Math.min(2 ** retries * 1000, 30000);
            await new Promise((r) => setTimeout(r, backoff));
            continue;
          }
          throw err;
        }
      }

      const out = await this._format(result, orig, start);
      await this._publish(out);
      return out;
    };
  }
}

// factory + exports
function lambdaMiddleware(options = {}) {
  const mw = new LambdaMiddleware(options);
  return (handler) => mw.middleware(handler);
}

module.exports = { lambdaMiddleware, LambdaMiddleware };
