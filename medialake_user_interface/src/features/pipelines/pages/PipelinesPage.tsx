import React, { useState, useMemo, useRef } from "react";
import {
  Box,
  Button,
  Snackbar,
  Alert,
  ButtonGroup,
  Popper,
  Grow,
  Paper,
  ClickAwayListener,
  MenuList,
  MenuItem,
  useTheme,
  alpha,
  IconButton,
} from "@mui/material";
import {
  Add as AddIcon,
  FileUpload as FileUploadIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnFiltersState,
  SortingState,
  ColumnSizingState,
} from "@tanstack/react-table";

import { PageHeader, PageContent } from "@/components/common/layout";
import { BaseTableToolbar } from "@/components/common/table/BaseTableToolbar";
import { BaseFilterPopover } from "@/components/common/table/BaseFilterPopover";
import { ColumnVisibilityMenu } from "@/components/common/table/ColumnVisibilityMenu";
import ApiStatusModal from "@/components/ApiStatusModal";
import queryClient from "@/api/queryClient";
import { PipelinesService } from "../api/pipelinesService";
import { PipelineDeleteDialog } from "../components";
import PipelineList from "../components/PipelineList";
import { usePipelineManager } from "../hooks/usePipelineManager";
import {
  usePipelineColumns,
  defaultColumnVisibility,
} from "../hooks/usePipelineColumns";
import { TableFiltersProvider } from "../context/TableFiltersContext";

// Define query keys for prefetching
const PIPELINES_QUERY_KEYS = {
  all: ["pipelines"] as const,
  detail: (id: string) => ["pipelines", "detail", id] as const,
};

const PipelinesPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const theme = useTheme();

  // Add Pipeline Button Menu state
  const addPipelineButtonRef = useRef<HTMLDivElement>(null);
  const [addPipelineMenuOpen, setAddPipelineMenuOpen] = useState(false);

  // API Status Modal state
  const [apiStatus, setApiStatus] = useState({
    open: false,
    status: "loading" as "loading" | "success" | "error",
    action: "",
    message: "",
  });

  // Delete dialog state
  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    pipelineName: "",
    pipelineId: "",
    userInput: "",
  });

  // Table state
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState(() => {
    try {
      const saved = localStorage.getItem("pipelineTableColumns");
      return saved && saved !== "undefined"
        ? JSON.parse(saved)
        : defaultColumnVisibility;
    } catch (error) {
      console.error(
        "Error parsing column visibility from localStorage:",
        error,
      );
      return defaultColumnVisibility;
    }
  });
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );
  const [isDeletingInProgress, setIsDeletingInProgress] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [snackbar, setSnackbar] = useState({
    open: false,
    severity: "info" as "info" | "success" | "error" | "warning",
    message: "",
  });

  // Function to handle closing the ApiStatusModal
  // Handle Add Pipeline Menu Toggle
  const handleAddPipelineMenuToggle = () => {
    setAddPipelineMenuOpen((prevOpen) => !prevOpen);
  };

  // Handle Add Pipeline Menu Close
  const handleAddPipelineMenuClose = (event: Event) => {
    if (
      addPipelineButtonRef.current &&
      addPipelineButtonRef.current.contains(event.target as HTMLElement)
    ) {
      return;
    }
    setAddPipelineMenuOpen(false);
  };

  // Handle Import Pipeline
  const handleImportPipeline = () => {
    const fileInput = document.getElementById("pipeline-import-input");
    if (fileInput) fileInput.click();
    setAddPipelineMenuOpen(false);
  };

  // Handle Close API Status Modal
  const handleCloseApiStatus = () => {
    setApiStatus((prev) => ({ ...prev, open: false }));
  };

  const {
    pipelines,
    isLoading,
    error,
    deletePipeline,
    isDeleting,
    toggleActive,
    togglingPipelines,
    refetch,
  } = usePipelineManager();

  // Handle refresh
  const handleRefresh = () => {
    setIsRefreshing(true);
    refetch().finally(() => {
      setIsRefreshing(false);
    });
  };

  // Handle edit pipeline
  const handleEdit = (id: string) => {
    // Show loading modal
    setApiStatus({
      open: true,
      status: "loading",
      action: "Loading pipeline data...",
      message: "",
    });

    // Start prefetching in the background
    queryClient
      .prefetchQuery({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
        queryFn: () => PipelinesService.getPipeline(id),
        staleTime: 30000, // Consider data fresh for 30 seconds
      })
      .finally(() => {
        // Close the modal regardless of prefetch result
        setApiStatus((prev) => ({ ...prev, open: false }));
      });

    // Navigate immediately without waiting for prefetch
    navigate(`/settings/pipelines/edit/${id}`);
  };

  // Handle delete pipeline
  const handleDeletePipeline = async (id: string) => {
    // If deletion is already in progress, do nothing
    if (isDeletingInProgress) {
      return;
    }

    // Set deletion in progress
    setIsDeletingInProgress(true);

    // Close the dialog first to prevent UI freezing
    setDeleteDialog((prev) => ({ ...prev, open: false }));

    // Show ApiStatusModal in "loading" state
    setApiStatus({
      open: true,
      status: "loading",
      action: "Deleting pipeline...",
      message: "",
    });

    try {
      await deletePipeline(id);

      // Show success modal
      setApiStatus({
        open: true,
        status: "success",
        action: "Pipeline deleted successfully",
        message: "The pipeline has been deleted.",
      });

      // Auto-close the modal after a few seconds
      setTimeout(() => {
        setApiStatus((prev) => ({ ...prev, open: false }));
      }, 2000);
    } catch (error) {
      // Show error modal
      setApiStatus({
        open: true,
        status: "error",
        action: "Error deleting pipeline",
        message:
          error instanceof Error ? error.message : "An unknown error occurred",
      });
    } finally {
      // Reset deletion in progress
      setIsDeletingInProgress(false);
    }
  };

  // Open delete dialog
  const openDeleteDialog = (id: string, name: string) => {
    setDeleteDialog({
      open: true,
      pipelineId: id,
      pipelineName: name,
      userInput: "",
    });
  };

  // Close delete dialog
  const closeDeleteDialog = () => {
    setDeleteDialog((prev) => ({ ...prev, open: false }));
  };

  // Handle delete confirmation
  const handleDeleteConfirm = () => {
    const pipelineId = deleteDialog.pipelineId;
    if (!pipelineId) {
      console.error("No pipeline ID found in delete dialog state");
      return;
    }

    handleDeletePipeline(pipelineId);
  };

  // Handle filter column
  const handleFilterColumn = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    setActiveFilterColumn(columnId);
    setFilterMenuAnchor(event.currentTarget);
  };

  // Handle filter menu close
  const handleFilterMenuClose = () => {
    setFilterMenuAnchor(null);
    setActiveFilterColumn(null);
  };

  // Handle column visibility changes with persistence
  const handleColumnVisibilityChange = (
    updatedVisibility: Record<string, boolean>,
  ) => {
    if (!updatedVisibility) return;
    setColumnVisibility(updatedVisibility);
    try {
      if (Object.keys(updatedVisibility).length > 0) {
        localStorage.setItem(
          "pipelineTableColumns",
          JSON.stringify(updatedVisibility),
        );
      }
    } catch (error) {
      console.error("Error saving column visibility to localStorage:", error);
    }
  };

  // Handle snackbar close
  const handleCloseSnackbar = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  // Set delete dialog input
  const setDeleteDialogInput = (input: string) => {
    setDeleteDialog((prev) => ({ ...prev, userInput: input }));
  };

  // Create table filters context value
  const tableFiltersValue = useMemo(
    () => ({
      activeFilters: columnFilters.map((f) => ({
        columnId: f.id,
        value: f.value as string,
      })),
      activeSorting: sorting.map((s) => ({ columnId: s.id, desc: s.desc })),
      onRemoveFilter: (columnId: string) => {
        setColumnFilters((prev) => prev.filter((f) => f.id !== columnId));
      },
      onRemoveSort: (columnId: string) => {
        setSorting((prev) => prev.filter((s) => s.id !== columnId));
      },
      onFilterChange: (columnId: string, value: string) => {
        setColumnFilters((prev) => {
          const existing = prev.find((f) => f.id === columnId);
          if (existing) {
            return prev.map((f) => (f.id === columnId ? { ...f, value } : f));
          }
          return [...prev, { id: columnId, value }];
        });
      },
      onSortChange: (columnId: string, desc: boolean) => {
        setSorting((prev) => {
          const existing = prev.find((s) => s.id === columnId);
          if (existing) {
            return prev.map((s) => (s.id === columnId ? { ...s, desc } : s));
          }
          return [...prev, { id: columnId, desc }];
        });
      },
    }),
    [columnFilters, sorting],
  );

  // Create columns
  const columns = usePipelineColumns({
    onEdit: handleEdit,
    onDelete: openDeleteDialog,
    onToggleActive: toggleActive,
  });

  // Create table
  const table = useReactTable({
    data: pipelines || [],
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      columnSizing,
      globalFilter,
    },
    enableSorting: true,
    enableColumnFilters: true,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: handleColumnVisibilityChange,
    onColumnSizingChange: setColumnSizing,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    filterFns: {
      includesString: (row, columnId, filterValue) => {
        const value = String(row.getValue(columnId) || "").toLowerCase();
        return value.includes(String(filterValue).toLowerCase());
      },
    },
  });

  return (
    <Box
      sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column" }}
    >
      <PageHeader
        title={t("pipelines.title")}
        description={t("pipelines.description")}
        action={
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 3.5 }}>
              <IconButton
                onClick={handleRefresh}
                disabled={isLoading || isRefreshing}
                sx={{
                  backgroundColor: alpha(theme.palette.primary.main, 0.1),
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                  },
                }}
                title={t("common.refresh")}
              >
                <RefreshIcon
                  sx={{
                    animation: isRefreshing
                      ? "spin 1s linear infinite"
                      : "none",
                    "@keyframes spin": {
                      "0%": {
                        transform: "rotate(0deg)",
                      },
                      "100%": {
                        transform: "rotate(360deg)",
                      },
                    },
                  }}
                />
              </IconButton>
              <ButtonGroup
                variant="contained"
                ref={addPipelineButtonRef}
                aria-label="Pipeline actions"
              >
                <Button
                  startIcon={<AddIcon />}
                  onClick={() => navigate("/settings/pipelines/new")}
                  sx={{
                    borderRadius: "8px 0 0 8px",
                    textTransform: "none",
                    px: 3,
                    height: 40,
                  }}
                >
                  {t("pipelines.actions.create")}
                </Button>
                <Button
                  size="small"
                  sx={{
                    borderRadius: "0 8px 8px 0",
                    height: 40,
                  }}
                  aria-controls={
                    addPipelineMenuOpen ? "add-pipeline-menu" : undefined
                  }
                  aria-expanded={addPipelineMenuOpen ? "true" : undefined}
                  aria-label="select pipeline action"
                  aria-haspopup="menu"
                  onClick={handleAddPipelineMenuToggle}
                >
                  <ArrowDropDownIcon />
                </Button>
              </ButtonGroup>
            </Box>
            <input
              type="file"
              accept="application/json"
              id="pipeline-import-input"
              style={{ display: "none" }}
              onChange={(event) => {
                const fileReader = new FileReader();
                const files = event.target.files;
                if (files && files.length > 0) {
                  // Extract the file name without extension to use as pipeline name
                  const fileName = files[0].name;
                  const pipelineNameFromFile = fileName.endsWith(".json")
                    ? fileName.slice(0, -5) // Remove .json extension
                    : fileName;

                  fileReader.readAsText(files[0], "UTF-8");
                  fileReader.onload = (e) => {
                    try {
                      const flow = JSON.parse(e.target?.result as string);
                      if (flow) {
                        // Ensure the active property is preserved
                        // If active is not defined in the imported flow, default to true
                        // Process the imported flow to ensure all edges have the required data field
                        const processedFlow = { ...flow };

                        // Check if nodes and edges are under a configuration property
                        if (
                          processedFlow.configuration &&
                          processedFlow.configuration.nodes &&
                          processedFlow.configuration.edges
                        ) {
                          console.log(
                            "[PipelinesPage] Found nodes and edges under configuration property",
                          );
                          // Move nodes and edges to the top level
                          processedFlow.nodes =
                            processedFlow.configuration.nodes;
                          processedFlow.edges =
                            processedFlow.configuration.edges;
                        }

                        // If the flow has edges, ensure each edge has a data field
                        if (
                          processedFlow.edges &&
                          Array.isArray(processedFlow.edges)
                        ) {
                          processedFlow.edges = processedFlow.edges.map(
                            (edge) => {
                              // Ensure edge has data field with at least a text property
                              if (!edge.data) {
                                return {
                                  ...edge,
                                  data: {
                                    text: "",
                                    id: edge.id,
                                    type: "custom",
                                  },
                                };
                              } else if (
                                typeof edge.data === "object" &&
                                !edge.data.id
                              ) {
                                // If data exists but doesn't have id and type fields, add them
                                return {
                                  ...edge,
                                  data: {
                                    ...edge.data,
                                    id: edge.id,
                                    type: "custom",
                                  },
                                };
                              }
                              return edge;
                            },
                          );
                        }

                        const importedFlow = {
                          ...processedFlow,
                          active:
                            processedFlow.active !== undefined
                              ? processedFlow.active
                              : true,
                        };

                        console.log(
                          "[PipelinesPage] Processed imported flow:",
                          importedFlow,
                        );

                        // Navigate to new pipeline page with the imported flow and name
                        // Pass showImporting flag to indicate the editor should show the importing state
                        navigate("/settings/pipelines/new", {
                          state: {
                            importedFlow: importedFlow,
                            pipelineName: pipelineNameFromFile,
                            showImporting: true,
                          },
                        });
                      }
                    } catch (error) {
                      console.error("Error parsing flow JSON", error);
                      setApiStatus({
                        open: true,
                        status: "error",
                        action: "Import Failed",
                        message: "Failed to parse the pipeline file.",
                      });
                    } finally {
                      // Reset the file input
                      const fileInput = document.getElementById(
                        "pipeline-import-input",
                      ) as HTMLInputElement;
                      if (fileInput) fileInput.value = "";
                    }
                  };
                }
              }}
            />

            <Popper
              sx={{ zIndex: 1200 }}
              open={addPipelineMenuOpen}
              anchorEl={addPipelineButtonRef.current}
              role={undefined}
              transition
              disablePortal
            >
              {({ TransitionProps, placement }) => (
                <Grow
                  {...TransitionProps}
                  style={{
                    transformOrigin:
                      placement === "bottom" ? "center top" : "center bottom",
                  }}
                >
                  <Paper>
                    <ClickAwayListener onClickAway={handleAddPipelineMenuClose}>
                      <MenuList id="add-pipeline-menu" autoFocusItem>
                        <MenuItem onClick={handleImportPipeline}>
                          <FileUploadIcon sx={{ mr: 1 }} />{" "}
                          {t("pipelines.actions.import")}
                        </MenuItem>
                      </MenuList>
                    </ClickAwayListener>
                  </Paper>
                </Grow>
              )}
            </Popper>
          </>
        }
      />

      <TableFiltersProvider {...tableFiltersValue}>
        <BaseTableToolbar
          globalFilter={globalFilter}
          onGlobalFilterChange={setGlobalFilter}
          onColumnMenuOpen={(event) => setColumnMenuAnchor(event.currentTarget)}
          activeFilters={tableFiltersValue.activeFilters}
          activeSorting={tableFiltersValue.activeSorting}
          onRemoveFilter={tableFiltersValue.onRemoveFilter}
          onRemoveSort={tableFiltersValue.onRemoveSort}
          searchPlaceholder={t("pipelines.searchPlaceholder")}
        />

        <PageContent isLoading={isLoading} error={error as Error}>
          <PipelineList
            table={table}
            onFilterColumn={handleFilterColumn}
            togglingPipelines={togglingPipelines}
            onToggleActive={toggleActive}
          />
        </PageContent>

        <BaseFilterPopover
          anchorEl={filterMenuAnchor}
          column={
            activeFilterColumn ? table.getColumn(activeFilterColumn) : null
          }
          onClose={handleFilterMenuClose}
          data={pipelines || []}
          getUniqueValues={(columnId, data) => {
            return Array.from(
              new Set(
                data.map((item) => {
                  const value = item[columnId as keyof typeof item];
                  return value ? String(value) : "";
                }),
              ),
            ).filter(Boolean);
          }}
        />

        <ColumnVisibilityMenu
          anchorEl={columnMenuAnchor}
          onClose={() => setColumnMenuAnchor(null)}
          columns={table.getAllColumns()}
        />

        <PipelineDeleteDialog
          open={deleteDialog.open}
          pipelineName={deleteDialog.pipelineName}
          userInput={deleteDialog.userInput}
          onClose={closeDeleteDialog}
          onConfirm={handleDeleteConfirm}
          onUserInputChange={setDeleteDialogInput}
          isDeleting={isDeleting || isDeletingInProgress}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
        >
          <Alert
            onClose={handleCloseSnackbar}
            severity={snackbar.severity}
            sx={{ width: "100%" }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>

        {/* API Status Modal */}
        <ApiStatusModal
          open={apiStatus.open}
          onClose={handleCloseApiStatus}
          status={apiStatus.status}
          action={apiStatus.action}
          message={apiStatus.message}
        />
      </TableFiltersProvider>
    </Box>
  );
};

export default PipelinesPage;
