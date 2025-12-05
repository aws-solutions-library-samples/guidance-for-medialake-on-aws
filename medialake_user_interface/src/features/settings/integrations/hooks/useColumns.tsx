import React from "react";
import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { useTranslation } from "react-i18next";
import { Integration } from "../components/IntegrationList/types";
import { StatusCell } from "../components/IntegrationList/cells/StatusCell";
import { ActionsCell } from "../components/IntegrationList/cells/ActionsCell";
import { DateCell } from "../components/IntegrationList/cells/DateCell";

interface UseColumnsProps {
  onEditIntegration: (id: string, integration: Integration) => void;
  onDeleteIntegration: (id: string) => void;
}

const columnHelper = createColumnHelper<Integration>();

export const useColumns = ({ onEditIntegration, onDeleteIntegration }: UseColumnsProps) => {
  const { t } = useTranslation();

  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: t("common.columns.name"),
        size: 200,
        enableSorting: true,
      }),
      columnHelper.accessor("status", {
        header: t("common.columns.status"),
        size: 120,
        cell: (info) => <StatusCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.accessor("createdAt", {
        header: t("common.columns.created"),
        size: 150,
        cell: (info) => <DateCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.accessor("updatedAt", {
        header: t("common.columns.modified"),
        size: 150,
        cell: (info) => <DateCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.display({
        id: "actions",
        header: t("common.columns.actions"),
        size: 100,
        cell: (info) => (
          <ActionsCell row={info.row} onEdit={onEditIntegration} onDelete={onDeleteIntegration} />
        ),
      }),
    ],
    [onEditIntegration, onDeleteIntegration, t]
  );
};
