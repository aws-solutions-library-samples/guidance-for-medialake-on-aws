import {
  formatLocalDateTime,
  formatRelativeTime,
} from "@/shared/utils/dateUtils";
import type { PipelineExecution } from "../types/pipelineExecutions.types";

interface ExecutionsListProps {
  executions: PipelineExecution[];
}

const ExecutionsList: React.FC<ExecutionsListProps> = ({ executions }) => {
  return (
    <div className="space-y-4">
      {executions.map((execution) => (
        <div key={execution.execution_id} className="p-4 border rounded-lg">
          <div className="flex flex-col space-y-2">
            <div className="flex items-center space-x-2">
              <span className="font-semibold">Started:</span>
              <span>{formatLocalDateTime(execution.start_time)}</span>
              <span className="text-gray-500">
                ({formatRelativeTime(execution.start_time)})
              </span>
            </div>
            {execution.end_time && (
              <div className="flex items-center space-x-2">
                <span className="font-semibold">Ended:</span>
                <span>{formatLocalDateTime(execution.end_time)}</span>
                <span className="text-gray-500">
                  ({formatRelativeTime(execution.end_time)})
                </span>
              </div>
            )}
            <div className="flex items-center space-x-2">
              <span className="font-semibold">Status:</span>
              <span
                className={`px-2 py-1 rounded ${
                  execution.status === "SUCCEEDED"
                    ? "bg-green-100 text-green-800"
                    : execution.status === "FAILED"
                      ? "bg-red-100 text-red-800"
                      : execution.status === "RUNNING"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-gray-100 text-gray-800"
                }`}
              >
                {execution.status}
              </span>
            </div>
            <div className="text-sm text-gray-600">
              Pipeline: {execution.pipeline_name}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ExecutionsList;
