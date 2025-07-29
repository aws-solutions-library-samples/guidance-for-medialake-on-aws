import React, { useMemo, useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  useTheme,
  alpha,
  Chip,
  Popover,
  IconButton,
} from "@mui/material";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import { useDebounce } from "@/hooks/useDebounce";
import {
  Visibility as VisibilityIcon,
  RestartAlt as RestartIcon,
  Replay as ReplayIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  ColumnSizingState,
  ColumnResizeMode,
} from "@tanstack/react-table";

import { PageHeader, PageContent } from "@/components/common/layout";
import { BaseTableToolbar } from "@/components/common/table/BaseTableToolbar";
import { ExecutionsTable } from "../components/ExecutionsTable";
import { TableCellContent } from "@/components/common/table";
import { BaseFilterPopover } from "@/components/common/table/BaseFilterPopover";
import { usePipelineExecutions } from "../api/hooks/usePipelineExecutions";
import {
  useRetryFromCurrent,
  useRetryFromStart,
} from "../api/hooks/useRetryExecution";
import type {
  PipelineExecution,
  PipelineExecutionFilters,
} from "../types/pipelineExecutions.types";
import ExecutionSideBar from "../components/ExecutionSideBar";

const PAGE_SIZE = 20;

const ExecutionsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();

  // State declarations
  const [sorting, setSorting] = useState<SortingState>([
    { id: "start_time", desc: true },
  ]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] =
    useState<PipelineExecution | null>(null);

  // Retry mutations
  const retryFromCurrentMutation = useRetryFromCurrent();
  const retryFromStartMutation = useRetryFromStart();

  // Debounce the search input to avoid excessive API calls
  const debouncedGlobalFilter = useDebounce(globalFilter, 500); // 500ms delay

  const filters = useMemo<PipelineExecutionFilters>(
    () => ({
      sortBy: sorting[0]?.id || "start_time",
      sortOrder: sorting[0]?.desc ? ("desc" as const) : ("asc" as const),
      // If globalFilter is empty, clear search immediately; otherwise use debounced value
      ...(globalFilter === ""
        ? {}
        : debouncedGlobalFilter && { search: debouncedGlobalFilter }),
      ...columnFilters.reduce(
        (acc, filter) => ({
          ...acc,
          [filter.id]: filter.value,
        }),
        {},
      ),
    }),
    [sorting, columnFilters, globalFilter, debouncedGlobalFilter],
  );

  // Data fetching and memoization
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = usePipelineExecutions(PAGE_SIZE, filters);

  const executions = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) => page.data.executions);
  }, [data]);

  const handleSortingChange = useCallback((newSorting: SortingState) => {
    setSorting(newSorting);
  }, []);

  const handleFilterColumn = useCallback(
    (event: React.MouseEvent<HTMLElement>, columnId: string) => {
      setActiveFilterColumn(columnId);
      setColumnMenuAnchor(event.currentTarget);
    },
    [],
  );

  const handleFilterMenuClose = useCallback(() => {
    setColumnMenuAnchor(null);
    setActiveFilterColumn(null);
  }, []);

  const handleFilterChange = useCallback((columnId: string, value: string) => {
    setColumnFilters((prev) => {
      const existing = prev.find((f) => f.id === columnId);
      if (existing) {
        return prev.map((f) => (f.id === columnId ? { ...f, value } : f));
      }
      return [...prev, { id: columnId, value }];
    });
    setColumnMenuAnchor(null);
  }, []);

  const getStatusColor = useCallback(
    (status: string) => {
      switch (status) {
        case "RUNNING":
          return theme.palette.info.main;
        case "SUCCEEDED":
          return theme.palette.success.main;
        case "FAILED":
          return theme.palette.error.main;
        case "TIMED_OUT":
        case "ABORTED":
          return theme.palette.warning.main;
        default:
          return theme.palette.grey[500];
      }
    },
    [theme],
  );

  const formatDate = useCallback((dateString: string) => {
    return formatLocalDateTime(dateString, { showSeconds: true });
  }, []);

  const formatDuration = useCallback((seconds: string | null | undefined) => {
    if (!seconds) return "";
    const duration = parseFloat(seconds);
    if (isNaN(duration)) return "";
    if (duration < 60) {
      return `${duration.toFixed(2)}s`;
    }
    const minutes = Math.floor(duration / 60);
    const remainingSeconds = (duration % 60).toFixed(2);
    return `${minutes}m ${remainingSeconds}s`;
  }, []);

  const handleRetryFromCurrent = useCallback(
    (executionId: string) => {
      retryFromCurrentMutation.mutate(executionId);
    },
    [retryFromCurrentMutation],
  );

  const handleRetryFromStart = useCallback(
    (executionId: string) => {
      retryFromStartMutation.mutate(executionId);
    },
    [retryFromStartMutation],
  );

  // const handleViewDetails = useCallback((executionId: string) => {
  //     navigate(`/executions/${executionId}`);
  // }, [navigate]);

  const handleViewDetails = useCallback((execution: PipelineExecution) => {
    console.log("handleViewDetails:", execution);

    console.log("Found execution:", execution); // Add this log
    if (execution) {
      console.log("Setting execution:", execution);
      console.log("Opening panel");
      setSelectedExecution(execution);
      setIsSidePanelOpen(true);
    }
  }, []);

  useEffect(() => {
    console.log("isSidePanelOpen changed:", isSidePanelOpen);
    console.log("selectedExecution:", selectedExecution);
  }, [isSidePanelOpen, selectedExecution]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const columns = useMemo<ColumnDef<PipelineExecution>[]>(
    () => [
      {
        header: t("executions.columns.pipelineName"),
        accessorKey: "pipeline_name",
        minSize: 120,
        size: 180,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        filterFn: "includesString",
        filter: "includesString",
        cell: ({ getValue }) => (
          <TableCellContent variant="primary">
            {getValue() as string}
          </TableCellContent>
        ),
      },
      {
        header: t("executions.columns.status"),
        accessorKey: "status",
        minSize: 100,
        size: 120,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => {
          const status = getValue() as string;
          const color = getStatusColor(status);
          return (
            <Chip
              label={status}
              size="small"
              sx={{
                backgroundColor: alpha(color, 0.1),
                color: color,
                fontWeight: 600,
                borderRadius: "6px",
                height: "24px",
                "& .MuiChip-label": {
                  px: 1.5,
                },
              }}
            />
          );
        },
      },
      {
        header: t("executions.columns.startTime"),
        accessorKey: "start_time",
        minSize: 150,
        size: 180,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">
            {formatDate(getValue() as string)}
          </TableCellContent>
        ),
      },
      {
        header: t("executions.columns.endTime"),
        accessorKey: "end_time",
        minSize: 150,
        size: 180,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">
            {formatDate(getValue() as string)}
          </TableCellContent>
        ),
      },
      {
        header: t("executions.columns.duration"),
        accessorKey: "duration_seconds",
        minSize: 100,
        size: 120,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">
            {formatDuration(getValue() as string)}
          </TableCellContent>
        ),
      },
      {
        id: "actions",
        header: t("executions.columns.actions"),
        minSize: 100,
        size: 120,
        enableResizing: true,
        enableSorting: false,
        cell: ({ row }) => (
          <TableCellContent>
            <Box sx={{ display: "flex", gap: 1 }}>
              <IconButton
                size="small"
                color="primary"
                title="View Details"
                onClick={() => handleViewDetails(row.original)}
                sx={{
                  backgroundColor: alpha(theme.palette.primary.main, 0.1),
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                  },
                }}
              >
                <VisibilityIcon fontSize="small" />
              </IconButton>
              {row.original.status === "FAILED" && (
                <>
                  <IconButton
                    size="small"
                    color="primary"
                    title={t("executions.actions.retryFromCurrent")}
                    onClick={() =>
                      handleRetryFromCurrent(row.original.execution_id)
                    }
                    disabled={
                      retryFromCurrentMutation.isPending ||
                      retryFromStartMutation.isPending
                    }
                    sx={{
                      backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      "&:hover": {
                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                      },
                      "&:disabled": {
                        backgroundColor: alpha(theme.palette.grey[500], 0.1),
                        color: theme.palette.grey[500],
                      },
                    }}
                  >
                    <ReplayIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="primary"
                    title={t("executions.actions.retryFromStart")}
                    onClick={() =>
                      handleRetryFromStart(row.original.execution_id)
                    }
                    disabled={
                      retryFromCurrentMutation.isPending ||
                      retryFromStartMutation.isPending
                    }
                    sx={{
                      backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      "&:hover": {
                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                      },
                      "&:disabled": {
                        backgroundColor: alpha(theme.palette.grey[500], 0.1),
                        color: theme.palette.grey[500],
                      },
                    }}
                  >
                    <RestartIcon fontSize="small" />
                  </IconButton>
                </>
              )}
            </Box>
          </TableCellContent>
        ),
      },
    ],
    [
      theme,
      t,
      getStatusColor,
      formatDate,
      formatDuration,
      handleRetryFromCurrent,
      handleRetryFromStart,
      retryFromCurrentMutation.isPending,
      retryFromStartMutation.isPending,
    ],
  );

  const table = useReactTable({
    data: executions,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      columnSizing,
      globalFilter,
    },
    enableSorting: true,
    enableFilters: true,
    manualSorting: true,
    manualFiltering: true,
    onSortingChange: handleSortingChange,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange" as ColumnResizeMode,
    filterFns: {
      includesString: (row, columnId, filterValue) => {
        const value = String(row.getValue(columnId) || "").toLowerCase();
        return value.includes(String(filterValue).toLowerCase());
      },
    },
  });

  const activeColumn = activeFilterColumn
    ? table.getColumn(activeFilterColumn)
    : null;

  return (
    <Box
      sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column" }}
    >
      {/* Main content */}

      <PageHeader
        title={t("executions.title")}
        description={t("executions.description")}
        action={
          <IconButton
            onClick={handleRefresh}
            disabled={isLoading}
            sx={{
              backgroundColor: alpha(theme.palette.primary.main, 0.1),
              "&:hover": {
                backgroundColor: alpha(theme.palette.primary.main, 0.2),
              },
            }}
            title={t("common.refresh")}
          >
            <RefreshIcon />
          </IconButton>
        }
      />
      <BaseTableToolbar
        globalFilter={globalFilter}
        onGlobalFilterChange={setGlobalFilter}
        onColumnMenuOpen={(event) => setColumnMenuAnchor(event.currentTarget)}
        activeFilters={columnFilters.map((f) => ({
          columnId: f.id,
          value: f.value as string,
        }))}
        activeSorting={sorting.map((s) => ({ columnId: s.id, desc: s.desc }))}
        onRemoveFilter={(columnId) => {
          setColumnFilters((prev) => prev.filter((f) => f.id !== columnId));
        }}
        onRemoveSort={(columnId) => {
          setSorting((prev) => prev.filter((s) => s.id !== columnId));
        }}
        searchPlaceholder={t("executions.searchPlaceholder")}
      />

      <PageContent isLoading={isLoading} error={error as Error}>
        {/* Container for table and sidebar */}
        <Box
          sx={{
            position: "relative",
            display: "flex",
            flex: 1,
            overflow: "hidden",
            gap: 1,
          }}
        >
          {/* Table wrapper */}
          <Box
            sx={{
              flex: 1,
              overflow: "auto",
              transition: (theme) =>
                theme.transitions.create("width", {
                  easing: theme.transitions.easing.sharp,
                  duration: theme.transitions.duration.leavingScreen,
                }),
              ...(isSidePanelOpen && {
                width: "calc(100% - 500px)",
              }),
            }}
          >
            <ExecutionsTable
              table={table}
              isLoading={isLoading}
              data={executions}
              onViewDetails={handleViewDetails}
              onRetryFromCurrent={handleRetryFromCurrent}
              onRetryFromStart={handleRetryFromStart}
              onFilterColumn={handleFilterColumn}
              activeFilters={columnFilters.map((f) => ({
                columnId: f.id,
                value: f.value as string,
              }))}
              activeSorting={sorting.map((s) => ({
                columnId: s.id,
                desc: s.desc,
              }))}
              onRemoveFilter={(columnId) => {
                setColumnFilters((prev) =>
                  prev.filter((f) => f.id !== columnId),
                );
              }}
              onRemoveSort={(columnId) => {
                setSorting((prev) => prev.filter((s) => s.id !== columnId));
              }}
            />
          </Box>
          {/* Sidebar panel */}
          <ExecutionSideBar
            isOpen={isSidePanelOpen}
            execution={selectedExecution}
            onClose={() => {
              setIsSidePanelOpen(false);
              setSelectedExecution(null);
            }}
          />
        </Box>

        {hasNextPage && (
          <Box
            sx={{
              p: 2,
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <Button
              onClick={() => fetchNextPage()}
              disabled={!hasNextPage || isFetchingNextPage}
              sx={{
                textTransform: "none",
                borderRadius: "8px",
                color: theme.palette.text.secondary,
                "&:hover": {
                  backgroundColor: alpha(theme.palette.primary.main, 0.1),
                },
              }}
            >
              {isFetchingNextPage ? t("common.loading") : t("common.loadMore")}
            </Button>
          </Box>
        )}
      </PageContent>
      <BaseFilterPopover
        anchorEl={columnMenuAnchor}
        column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
        onClose={handleFilterMenuClose}
        data={executions}
        getUniqueValues={(columnId, data) => {
          return Array.from(
            new Set(
              data.map((item) => {
                const value = item[columnId as keyof PipelineExecution];
                return value ? String(value) : "";
              }),
            ),
          ).filter(Boolean);
        }}
        formatValue={(columnId, value) => {
          switch (columnId) {
            case "start_time":
              return formatDate(value);
            case "duration_seconds":
              return formatDuration(value);
            default:
              return value;
          }
        }}
      />
    </Box>
  );
};

export default ExecutionsPage;
