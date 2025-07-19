import React, { createContext, useContext, ReactNode } from "react";

interface TableFilter {
  columnId: string;
  value: string;
}

interface TableSort {
  columnId: string;
  desc: boolean;
}

interface TableFiltersContextType {
  activeFilters: TableFilter[];
  activeSorting: TableSort[];
  onRemoveFilter: (columnId: string) => void;
  onRemoveSort: (columnId: string) => void;
  onFilterChange?: (columnId: string, value: string) => void;
  onSortChange?: (columnId: string, desc: boolean) => void;
}

const TableFiltersContext = createContext<TableFiltersContextType | undefined>(
  undefined,
);

interface TableFiltersProviderProps extends TableFiltersContextType {
  children: ReactNode;
}

export const TableFiltersProvider: React.FC<TableFiltersProviderProps> = ({
  children,
  ...value
}) => {
  return (
    <TableFiltersContext.Provider value={value}>
      {children}
    </TableFiltersContext.Provider>
  );
};

export const useTableFilters = () => {
  const context = useContext(TableFiltersContext);
  if (!context) {
    throw new Error(
      "useTableFilters must be used within a TableFiltersProvider",
    );
  }
  return context;
};

export type { TableFilter, TableSort, TableFiltersContextType };
