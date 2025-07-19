import React from "react";
import { format } from "date-fns";

interface DateCellProps {
  value: string;
}

export const DateCell = React.memo(({ value }: DateCellProps) =>
  format(new Date(value), "MMM dd, yyyy HH:mm"),
);

DateCell.displayName = "DateCell";

interface TextCellProps {
  value: string;
}

export const TextCell = React.memo(({ value }: TextCellProps) => value);

TextCell.displayName = "TextCell";
