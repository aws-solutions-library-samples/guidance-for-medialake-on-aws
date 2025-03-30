import { formatDateTime } from '../../../shared/utils/dateTime';

interface Execution {
  execution_id: string;
  start_time: string;
  end_time?: string;
}

const ExecutionsList: React.FC<{ executions: Execution[] }> = ({ executions }) => {
  return (
    <div>
      {executions.map(execution => (
        <div key={execution.execution_id}>
          <span>Started: {formatDateTime(execution.start_time)}</span>
          {execution.end_time && (
            <span>Ended: {formatDateTime(execution.end_time)}</span>
          )}
        </div>
      ))}
    </div>
  );
};

export default ExecutionsList; 