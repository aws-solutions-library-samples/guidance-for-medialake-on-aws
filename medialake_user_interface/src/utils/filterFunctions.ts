import { FilterFn } from "@tanstack/react-table";

export const includesString: FilterFn<any> = (row, columnId, filterValue) => {
  const value = row.getValue(columnId);
  if (!value) return false;
  return String(value)
    .toLowerCase()
    .includes(String(filterValue).toLowerCase());
};
