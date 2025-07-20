export interface TableState {
  globalFilter: string;
  columnFilters: any[];
  columnVisibility: Record<string, boolean>;
  columnMenuAnchor: HTMLElement | null;
  filterMenuAnchor: HTMLElement | null;
  activeFilterColumn: string | null;
  pagination: {
    pageIndex: number;
    pageSize: number;
  };
  deleteDialog: {
    open: boolean;
    pipelineName: string;
    pipelineId: string;
    userInput: string;
  };
  snackbar: {
    open: boolean;
    severity: "success" | "error" | "info" | "warning";
    message: string;
  };
}

export interface TableActions {
  setPagination: (pagination: TableState["pagination"]) => void;
  setGlobalFilter: (filter: string) => void;
  setColumnFilters: (filters: any[]) => void;
  setColumnVisibility: (visibility: Record<string, boolean>) => void;
  handleCloseSnackbar: () => void;
  handleEdit: (id: string) => void;
  openDeleteDialog: (id: string, name: string) => void;
  closeDeleteDialog: () => void;
  handleDirectDelete?: (id: string, name: string) => void;
  handleDeleteConfirm?: () => void;
  handleColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
  handleColumnMenuClose: () => void;
  handleFilterMenuOpen: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
  handleFilterMenuClose: () => void;
  setDeleteDialogInput: (input: string) => void;
}
