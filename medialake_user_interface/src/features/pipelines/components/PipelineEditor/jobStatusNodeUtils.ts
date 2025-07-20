import React from "react";
import { FaRegCheckCircle } from "react-icons/fa";

// Job status node constants
export const JOB_STATUS_NODE_TYPE = "jobStatusNode";
export const JOB_STATUS_NODE_METHOD = "checkJobStatus";

/**
 * Creates the job status node data for drag and drop from sidebar
 */
export const createJobStatusNodeData = () => {
  return {
    id: `job-status-${Date.now()}`,
    type: "UTILITY",
    label: "Check Job Status",
    description:
      "Checks the status of a job and routes based on completion status",
    inputTypes: ["*"],
    outputTypes: ["completed", "in-progress", "failed"],
    selectedMethod: JOB_STATUS_NODE_METHOD,
    icon: "", //React.createElement(FaRegCheckCircle, { size: 18, color: "#4CAF50" }),
    methodConfig: {
      method: JOB_STATUS_NODE_METHOD,
      parameters: {
        jobId: {
          type: "string",
          required: true,
          defaultValue: "",
          description: "ID of the job to check",
        },
        statusPath: {
          type: "string",
          required: false,
          defaultValue: "status",
          description: "Path to the status field in the response",
        },
      },
      requestMapping: {
        jobId: "$.jobId",
      },
      responseMapping: {
        status: "$.status",
      },
    },
  };
};
