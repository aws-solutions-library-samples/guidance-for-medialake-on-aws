import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { useTranslation } from "react-i18next";
import { Environment } from "@/types/environment";
import { Box, Tooltip } from "@mui/material";
import { TableCellContent } from "@/components/common/table";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";

const columnHelper = createColumnHelper<Environment>();

export const useEnvironmentColumns = () => {
  const { t } = useTranslation();

  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: t("common.columns.name"),
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => <TableCellContent variant="primary">{getValue()}</TableCellContent>,
      }),
      columnHelper.accessor("region", {
        header: t("common.labels.region"),
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("status", {
        header: t("common.columns.status"),
        size: 150,
        enableSorting: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">{getValue()}</TableCellContent>
        ),
      }),
      columnHelper.accessor("created_at", {
        header: t("common.columns.created"),
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip title={formatLocalDateTime(dateValue, { showSeconds: true })} placement="top">
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
        header: t("common.columns.modified"),
        size: 200,
        enableSorting: true,
        cell: ({ getValue }) => {
          const dateValue = getValue();
          return (
            <Tooltip title={formatLocalDateTime(dateValue, { showSeconds: true })} placement="top">
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
    []
  );
};
