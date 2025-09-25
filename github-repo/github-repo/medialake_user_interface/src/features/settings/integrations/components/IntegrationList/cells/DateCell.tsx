import React from "react";
import { TableCellContent } from "@/components/common/table";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";

interface DateCellProps {
  value: string;
}

export const DateCell: React.FC<DateCellProps> = ({ value }) => {
  return (
    <TableCellContent variant="secondary">
      {formatLocalDateTime(value)}
    </TableCellContent>
  );
};
