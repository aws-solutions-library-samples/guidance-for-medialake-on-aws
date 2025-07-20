import { Integration as BaseIntegration } from "../../types/integrations.types";
import {
  ColumnSort as TanStackColumnSort,
  ColumnFilter as TanStackColumnFilter,
} from "@tanstack/react-table";

export interface Integration extends BaseIntegration {
  id: string;
  name: string;
  type: string;
  status: string;
  description: string;
  createdAt: string;
  updatedAt: string;
}

export interface ColumnSort {
  columnId: string;
  desc: boolean;
}

export interface ColumnFilter {
  columnId: string;
  value: string;
}

export interface IntegrationListProps {
  integrations: Integration[];
  onEditIntegration: (id: string, integration: Integration) => void;
  onDeleteIntegration: (id: string) => void;
  activeFilters: TanStackColumnFilter[];
  activeSorting: TanStackColumnSort[];
  onFilterChange: (columnId: string, value: string) => void;
  onSortChange: (columnId: string, desc: boolean) => void;
  onRemoveFilter: (columnId: string) => void;
  onRemoveSort: (columnId: string) => void;
  isLoading?: boolean;
}
