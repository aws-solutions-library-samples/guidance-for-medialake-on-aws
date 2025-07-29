import React from "react";
import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Integration } from "../components/IntegrationList/types";
import { StatusCell } from "../components/IntegrationList/cells/StatusCell";
import { ActionsCell } from "../components/IntegrationList/cells/ActionsCell";
import { DateCell } from "../components/IntegrationList/cells/DateCell";

interface UseColumnsProps {
  onEditIntegration: (id: string, integration: Integration) => void;
  onDeleteIntegration: (id: string) => void;
}

const columnHelper = createColumnHelper<Integration>();

export const useColumns = ({
  onEditIntegration,
  onDeleteIntegration,
}: UseColumnsProps) => {
  return useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Name",
        size: 200,
        enableSorting: true,
      }),
      columnHelper.accessor("status", {
        header: "Status",
        size: 120,
        cell: (info) => <StatusCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.accessor("createdAt", {
        header: "Created",
        size: 150,
        cell: (info) => <DateCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.accessor("updatedAt", {
        header: "Updated",
        size: 150,
        cell: (info) => <DateCell value={info.getValue()} />,
        enableSorting: true,
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        size: 100,
        cell: (info) => (
          <ActionsCell
            row={info.row}
            onEdit={onEditIntegration}
            onDelete={onDeleteIntegration}
          />
        ),
      }),
    ],
    [onEditIntegration, onDeleteIntegration],
  );
};
