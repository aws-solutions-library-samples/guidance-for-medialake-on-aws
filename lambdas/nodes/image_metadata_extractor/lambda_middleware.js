// lambda_middleware.js
const AWS = require("aws-sdk");
const { v4: uuidv4 } = require("uuid");
const { cloneDeep } = require("lodash");

/* eslint camelcase:0 */
class LambdaMiddleware {
  constructor(opts = {}) {
    Object.assign(this, { maxResponseSize: 240 * 1024, maxRetries: 3 }, opts);

    // ─── config / env ──────────────────────────────────────────────────
    this.eventBusName = opts.eventBusName || process.env.EVENT_BUS_NAME;
    this.externalPayloadBucket =
      opts.externalPayloadBucket || process.env.EXTERNAL_PAYLOAD_BUCKET;
    if (!this.eventBusName) throw new Error("EVENT_BUS_NAME env-var required");
    if (!this.externalPayloadBucket)
      throw new Error("EXTERNAL_PAYLOAD_BUCKET env-var required");

    this.assetsTableName =
      opts.assetsTableName || process.env.MEDIALAKE_ASSET_TABLE || "";

    // ─── AWS clients ──────────────────────────────────────────────────
    this.s3 = new AWS.S3();
    this.eb = new AWS.EventBridge();
    this.dynamo = this.assetsTableName
      ? new AWS.DynamoDB.DocumentClient()
      : null;

    // ─── service metadata ─────────────────────────────────────────────
    this.service = process.env.SERVICE || "undefined_service";
    this.stepName = process.env.STEP_NAME || "undefined_step";
    this.pipeName = process.env.PIPELINE_NAME || "undefined_pipeline";
    this.isFirst = (process.env.IS_FIRST || "false").toLowerCase() === "true";
    this.isLast = (process.env.IS_LAST || "false").toLowerCase() === "true";
  }

  // ────────────────────────────────────────────────────────────────────────
  // Helpers
  // ────────────────────────────────────────────────────────────────────────
  _trueOriginal(ev) {
    let cur = ev.originalEvent || ev;
    while (
      cur &&
      cur.payload &&
      typeof cur.payload === "object" &&
      cur.payload.event
    ) {
      cur = cur.payload.event;
    }
    return cur;
  }

  _pickPipelineIds(ev) {
    return {
      execId: ev.pipelineExecutionId || ev.executionName || "",
      pipeId: ev.pipelineId || ev.stateMachineArn || "",
    };
  }

  async _fetchAssetRecord(asset_id) {
    if (!this.dynamo) return null;
    try {
      const { Item } = await this.dynamo
        .get({
          TableName: this.assetsTableName,
          Key: { InventoryID: asset_id },
        })
        .promise();
      return Item || null;
    } catch (e) {
      console.error(`DDB lookup failed for ${asset_id}:`, e);
      return null;
    }
  }

  // ────────────────────────────────────────────────────────────────────────
  // Standardise input (with external-payload rehydration)
  // ────────────────────────────────────────────────────────────────────────
  async _standardizeInput(ev) {
    // ── top-level external-payload rehydration ────────────────────────────
    if (ev.metadata?.stepExternalPayload === "True") {
      const { bucket, key } = ev.metadata.stepExternalPayloadLocation || {};
      let data = {};
      if (bucket && key) {
        const obj = await this.s3
          .getObject({ Bucket: bucket, Key: key })
          .promise();
        const parsed = JSON.parse(obj.Body.toString("utf-8"));
        if (Array.isArray(parsed)) {
          data = parsed.map((_, idx) => ({
            s3_bucket: bucket,
            s3_key: key,
            index: idx,
          }));
        } else {
          data = parsed;
        }
      }
      return {
        metadata: ev.metadata,
        payload: {
          data,
          assets: ev.payload?.assets || [],
        },
      };
    }

    // ── Step-Functions wrapper ─────────────────────────────────────────────
    if (
      typeof ev.executionName === "string" &&
      typeof ev.stateMachineArn === "string" &&
      ev.payload &&
      typeof ev.payload === "object"
    ) {
      const { execId, pipeId } = this._pickPipelineIds(ev);
      const stdInner = await this._standardizeInput(cloneDeep(ev.payload));
      stdInner.metadata = stdInner.metadata || {};
      stdInner.metadata.pipelineExecutionId = execId;
      stdInner.metadata.pipelineId = pipeId;
      return stdInner;
    }

    // ── Map/Task iterator with external-payload placeholder ────────────────
    if (ev.item && ev.item.asset_id) {
      // extract any offload flags
      const hasOffload = ev.item.stepExternalPayload === "True";
      const loc = ev.item.stepExternalPayloadLocation || {};
      const idx = ev.item.index || 0;

      if (hasOffload) {
        // rehydrate just this index
        let parsed, data;
        if (loc.bucket && loc.key) {
          const obj = await this.s3
            .getObject({ Bucket: loc.bucket, Key: loc.key })
            .promise();
          parsed = JSON.parse(obj.Body.toString("utf-8"));
        }
        if (Array.isArray(parsed)) {
          data = parsed[idx] || {};
        } else {
          data = parsed;
        }
        return {
          metadata: {
            service: this.service,
            stepName: this.stepName,
            pipelineName: this.pipeName,
            pipelineTraceId: uuidv4(),
            stepExternalPayload: "True",
            stepExternalPayloadLocation: loc,
          },
          payload: {
            data: { item: data },
            assets: ev.payload?.assets || [],
          },
        };
      }

      // ── normal Map/Task path ──────────────────────────────────────────────
      const { execId, pipeId } = this._pickPipelineIds(ev);
      const itemObj = cloneDeep(ev.item);
      const assetRec = await this._fetchAssetRecord(itemObj.asset_id);

      return {
        metadata: {
          service: this.service,
          stepName: this.stepName,
          pipelineName: this.pipeName,
          pipelineTraceId: uuidv4(),
          pipelineExecutionId: execId,
          pipelineId: pipeId,
        },
        payload: {
          data: itemObj,
          assets: assetRec ? [assetRec] : [],
          map: { item: itemObj },
        },
      };
    }

    // ── already standardised ────────────────────────────────────────────────
    if (
      ev.metadata &&
      ev.payload &&
      Object.prototype.hasOwnProperty.call(ev.payload, "data") &&
      Object.prototype.hasOwnProperty.call(ev.payload, "assets")
    ) {
      return ev;
    }

    // ── EventBridge envelopes ──────────────────────────────────────────────
    if (ev.detail?.metadata && ev.detail?.payload) {
      const detail = ev.detail;
      const { execId, pipeId } = this._pickPipelineIds(ev);
      detail.pipelineExecutionId ||= execId;
      detail.pipelineId ||= pipeId;
      return detail;
    }
    if (ev.detail && !ev.payload && !ev.assets) {
      const { execId, pipeId } = this._pickPipelineIds(ev);
      return {
        metadata: {
          service: this.service,
          stepName: this.stepName,
          pipelineName: this.pipeName,
          pipelineTraceId: uuidv4(),
          pipelineExecutionId: execId,
          pipelineId: pipeId,
        },
        payload: {
          data: {},
          assets: [cloneDeep(ev.detail)],
        },
      };
    }

    // ── fallback wrap ──────────────────────────────────────────────────────
    const { execId, pipeId } = this._pickPipelineIds(ev);
    const payload = { data: ev, assets: [] };
    if (ev.payload?.assets) payload.assets = cloneDeep(ev.payload.assets);
    if (ev.assets) payload.assets = cloneDeep(ev.assets);
    if (ev.payload?.map) payload.map = cloneDeep(ev.payload.map);
    if (ev.map) payload.map = cloneDeep(ev.map);

    return {
      metadata: {
        service: this.service,
        stepName: this.stepName,
        pipelineName: this.pipeName,
        pipelineTraceId: ev.metadata?.pipelineTraceId || uuidv4(),
        pipelineExecutionId: execId,
        pipelineId: pipeId,
      },
      payload,
    };
  }

  // ────────────────────────────────────────────────────────────────────────
  // Outbound formatter (with large-payload offload)
  // ────────────────────────────────────────────────────────────────────────
  async _format(result, orig, stepStart) {
    // prepare data & strip externalJob fields
    const data =
      result && typeof result === "object" ? { ...result } : { value: result };
    const extId = data.externalJobId || "";
    const extSt = data.externalJobStatus || "";
    const extRs = data.externalJobResult || "";
    delete data.externalJobId;
    delete data.externalJobStatus;
    delete data.externalJobResult;

    const now = Date.now() / 1000;
    const prevMeta = orig.metadata || {};
    const completed =
      this.isLast && (!extSt || extSt.toLowerCase() === "completed");

    const meta = {
      service: this.service,
      stepName: this.stepName,
      stepStatus: "Completed",
      stepResult: "Success",
      pipelineTraceId: prevMeta.pipelineTraceId || uuidv4(),
      stepExecutionStartTime: prevMeta.stepExecutionStartTime || stepStart,
      stepExecutionEndTime: now,
      stepExecutionDuration: +(now - stepStart).toFixed(3),
      pipelineExecutionStartTime: orig.pipelineExecutionStartTime || "",
      pipelineExecutionEndTime: this.isLast ? now : "",
      pipelineName: this.pipeName,
      pipelineStatus: this.isFirst
        ? "Started"
        : completed
          ? "Completed"
          : "InProgress",
      pipelineId: prevMeta.pipelineId || "",
      pipelineExecutionId: prevMeta.pipelineExecutionId || "",
      externalJobResult: extRs,
      externalJobId: extId,
      externalJobStatus: extSt,
      stepExternalPayload: "False",
      stepExternalPayloadLocation: {},
    };

    // assemble assets
    let assets = [];
    if (result && typeof result === "object" && result.updatedAsset) {
      assets = [cloneDeep(result.updatedAsset)];
      delete data.updatedAsset;
    } else {
      const prev = orig.payload?.assets || orig.assets || [];
      const fromDetail = orig.input?.detail || orig.detail || orig;
      const inner = (obj) =>
        obj?.metadata && obj.payload?.assets
          ? cloneDeep(obj.payload.assets)
          : [cloneDeep(obj)];
      assets = prev.concat(inner(fromDetail));
    }

    // payload
    const payload = { data, assets };
    if (orig.payload?.map) payload.map = cloneDeep(orig.payload.map);

    // large-payload offload
    const raw = Buffer.from(JSON.stringify(payload.data));
    if (raw.length > this.maxResponseSize) {
      const key = `${meta.pipelineExecutionId}/${uuidv4()}-payload.json`;
      await this.s3
        .putObject({
          Bucket: this.externalPayloadBucket,
          Key: key,
          Body: raw,
        })
        .promise();

      meta.stepExternalPayload = "True";
      meta.stepExternalPayloadLocation = {
        bucket: this.externalPayloadBucket,
        key,
      };

      // build Map‐state references
      const parsed = JSON.parse(raw.toString());
      const listLen = Array.isArray(parsed) ? parsed.length : 0;
      payload.data = Array.from({ length: listLen }).map((_, idx) => ({
        asset_id: assets[0]?.InventoryID || null,
        stepExternalPayload: "True",
        stepExternalPayloadLocation: meta.stepExternalPayloadLocation,
        index: idx,
      }));
    }

    return { metadata: meta, payload };
  }

  // ────────────────────────────────────────────────────────────────────────
  // Publish to EventBridge
  // ────────────────────────────────────────────────────────────────────────
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
      console.error("EventBridge publish failed:", e);
    }
  }

  // ────────────────────────────────────────────────────────────────────────
  // Middleware wrapper
  // ────────────────────────────────────────────────────────────────────────
  middleware(handler) {
    return async (event, ctx) => {
      const raw = this._trueOriginal(event);
      const standardEvent = await this._standardizeInput(cloneDeep(raw));
      const start = Date.now() / 1000;

      let retries = 0,
        result;
      while (true) {
        try {
          result = await handler(standardEvent, ctx);
          break;
        } catch (err) {
          if (retries++ < this.maxRetries) {
            await new Promise((r) =>
              setTimeout(r, Math.min(2 ** retries * 1000, 30000)),
            );
            continue;
          }
          throw err;
        }
      }

      const out = await this._format(result, standardEvent, start);
      await this._publish(out);
      return out;
    };
  }
}

// factory
function lambdaMiddleware(opts = {}) {
  const mw = new LambdaMiddleware(opts);
  return (handler) => mw.middleware(handler);
}

module.exports = { lambdaMiddleware, LambdaMiddleware };
