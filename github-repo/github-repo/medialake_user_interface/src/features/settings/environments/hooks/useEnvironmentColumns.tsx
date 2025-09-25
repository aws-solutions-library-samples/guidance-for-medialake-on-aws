import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Environment } from "@/types/environment";
import { Box, Tooltip } from "@mui/material";
import { TableCellContent } from "@/components/common/table";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";

const columnHelper = createColumnHelper<Environment>();

export const useEnvironmentColumns = () => {
  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Name",
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="primary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("region", {
        header: "Region",
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("status", {
        header: "Status",
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("created_at", {
        header: "Created At",
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip
              title={formatLocalDateTime(dateValue, { showSeconds: true })}
              placement="top"
            >
              <Box>
                <TableCellContent variant="secondary">
                  {formatLocalDateTime(dateValue, { showSeconds: false })}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor("updated_at", {
        header: "Updated At",
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip
              title={formatLocalDateTime(dateValue, { showSeconds: true })}
              placement="top"
            >
              <Box>
                <TableCellContent variant="secondary">
                  {formatLocalDateTime(dateValue, { showSeconds: false })}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      }),
    ],
    [],
  );
};
