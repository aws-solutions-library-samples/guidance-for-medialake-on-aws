const { DynamoDB } = require("aws-sdk");
const dynamodb = new DynamoDB.DocumentClient();

class WarmerExtension {
  constructor() {
    this.extensionId = process.env._HANDLER;
    this.tableName = process.env.WARMER_TABLE;
    this.ttl = parseInt(process.env.EXTENSION_TTL || "300");
    this.enabled = process.env.WARMER_ENABLED === "true";
    this.maxRetries = 3;
    this.retryDelay = 1000;
  }

  async register() {
    const res = await fetch(
      `http://${process.env.AWS_LAMBDA_RUNTIME_API}/2020-01-01/extension/register`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Lambda-Extension-Name": "warmer",
        },
        body: JSON.stringify({
          events: ["INVOKE", "SHUTDOWN"],
        }),
      },
    );

    if (!res.ok) {
      throw new Error(`Failed to register extension: ${await res.text()}`);
    }

    const { extensionId } = await res.json();
    return extensionId;
  }

  async processEvents() {
    while (true) {
      const res = await fetch(
        `http://${process.env.AWS_LAMBDA_RUNTIME_API}/2020-01-01/extension/event/next`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "Lambda-Extension-Identifier": this.extensionId,
          },
        },
      );

      if (!res.ok) {
        console.error("Failed to get next event:", await res.text());
        continue;
      }

      const event = await res.json();

      switch (event.eventType) {
        case "INVOKE":
          await this.handleInvoke();
          break;
        case "SHUTDOWN":
          await this.handleShutdown();
          return;
      }
    }
  }

  async handleInvoke() {
    if (!this.enabled) return;

    try {
      await this.updateState();
    } catch (error) {
      console.error("Failed to handle invoke:", error);
    }
  }

  async handleShutdown() {
    if (!this.enabled) return;

    try {
      await this.cleanupState();
    } catch (error) {
      console.error("Failed to handle shutdown:", error);
    }
  }

  async updateState() {
    const now = Math.floor(Date.now() / 1000);
    const item = {
      extensionId: this.extensionId,
      ttl: now + this.ttl,
      lastUpdated: now,
    };

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        await dynamodb
          .put({
            TableName: this.tableName,
            Item: item,
          })
          .promise();
        return;
      } catch (error) {
        if (attempt === this.maxRetries - 1) throw error;
        await new Promise((resolve) =>
          setTimeout(resolve, this.retryDelay * Math.pow(2, attempt)),
        );
      }
    }
  }

  async cleanupState() {
    try {
      await dynamodb
        .delete({
          TableName: this.tableName,
          Key: { extensionId: this.extensionId },
        })
        .promise();
    } catch (error) {
      console.error("Failed to cleanup state:", error);
    }
  }
}

module.exports = { WarmerExtension };
