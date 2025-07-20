import React, { useState, useMemo } from "react";
import { Box, Button } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useTranslation } from "react-i18next";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnResizeMode,
  SortingState,
  ColumnFiltersState,
  ColumnSizingState,
} from "@tanstack/react-table";
import { PageHeader, PageContent } from "@/components/common/layout";
import { BaseTableToolbar } from "@/components/common/table/BaseTableToolbar";
import { BaseFilterPopover } from "@/components/common/table/BaseFilterPopover";
import { ColumnVisibilityMenu } from "@/components/common/table/ColumnVisibilityMenu";
import EnvironmentList from "@/features/settings/environments/components/EnvironmentList";
import { EnvironmentForm } from "@/features/settings/environments/components/EnvironmentForm";
import ApiStatusModal from "@/components/ApiStatusModal";
import { useEnvironmentColumns } from "@/features/settings/environments/hooks/useEnvironmentColumns";
import { TableFiltersProvider } from "@/features/settings/environments/context/TableFiltersContext";
import {
  useEnvironmentsQuery,
  useCreateEnvironmentMutation,
  useUpdateEnvironmentMutation,
  useDeleteEnvironmentMutation,
} from "@/features/settings/environments/hooks/useEnvironmentsQuery";
import {
  Environment,
  EnvironmentCreate,
  EnvironmentUpdate,
} from "@/types/environment";
import { defaultColumnVisibility } from "@/features/settings/environments/config";

const EnvironmentsPage: React.FC = () => {
  const { t } = useTranslation();
  const [openEnvironmentForm, setOpenEnvironmentForm] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<
    Environment | undefined
  >();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState(() => {
    try {
      const saved = localStorage.getItem("environmentTableColumns");
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
  const [columnVisibilityAnchor, setColumnVisibilityAnchor] =
    useState<null | HTMLElement>(null);
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );
  const [apiStatus, setApiStatus] = useState<{
    show: boolean;
    status: "loading" | "success" | "error";
    action: string;
    message?: string;
  }>({
    show: false,
    status: "loading",
    action: "",
  });

  // API Hooks
  const {
    data: environments,
    isLoading: isLoadingEnvironments,
    error: environmentsError,
  } = useEnvironmentsQuery();
  const createEnvironmentMutation = useCreateEnvironmentMutation();
  const updateEnvironmentMutation = useUpdateEnvironmentMutation();
  const deleteEnvironmentMutation = useDeleteEnvironmentMutation();

  const columns = useEnvironmentColumns();

  const handleAddEnvironment = () => {
    setEditingEnvironment(undefined);
    setOpenEnvironmentForm(true);
  };

  const handleEditEnvironment = (environment: Environment) => {
    setEditingEnvironment(environment);
    setOpenEnvironmentForm(true);
  };

  const handleSaveEnvironment = async (environmentData: EnvironmentCreate) => {
    const isNewEnvironment = !editingEnvironment;
    const action = isNewEnvironment
      ? "Creating environment..."
      : "Updating environment...";

    setApiStatus({
      show: true,
      status: "loading",
      action,
    });
    setOpenEnvironmentForm(false);

    try {
      if (editingEnvironment) {
        const updateData: EnvironmentUpdate = {
          name: environmentData.name,
          region: environmentData.region,
          status: environmentData.status,
          tags: environmentData.tags,
        };
        await updateEnvironmentMutation.mutateAsync({
          id: editingEnvironment.environment_id,
          data: updateData,
        });

        setApiStatus({
          show: true,
          status: "success",
          action: "Environment Updated",
          message: t("settings.environments.updateSuccess"),
        });
      } else {
        await createEnvironmentMutation.mutateAsync(environmentData);

        setApiStatus({
          show: true,
          status: "success",
          action: "Environment Created",
          message: t("settings.environments.createSuccess"),
        });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : t("settings.environments.submitError");
      setApiStatus({
        show: true,
        status: "error",
        action: isNewEnvironment
          ? "Environment Creation Failed"
          : "Environment Update Failed",
        message: errorMessage,
      });
      console.error("Error saving environment:", error);
      throw error;
    }
  };

  const handleCloseApiStatus = () => {
    setApiStatus((prev) => ({ ...prev, show: false }));
  };

  const handleFilterColumn = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    setActiveFilterColumn(columnId);
    setColumnMenuAnchor(event.currentTarget);
  };

  const handleFilterMenuClose = () => {
    setColumnMenuAnchor(null);
    setActiveFilterColumn(null);
  };

  const environmentsList = useMemo(() => {
    if (!environments?.data?.environments) return [];
    return environments.data.environments.map((env) => ({
      ...env,
      status: env.status || "active",
      tags: {
        "cost-center": env.tags?.["cost-center"] || "",
        team: env.tags?.team || "",
        ...env.tags,
      },
    }));
  }, [environments]);

  // Handle visibility changes with persistence
  const handleColumnVisibilityChange = (
    updatedVisibility: Record<string, boolean>,
  ) => {
    if (!updatedVisibility) return;
    setColumnVisibility(updatedVisibility);
    try {
      if (Object.keys(updatedVisibility).length > 0) {
        localStorage.setItem(
          "environmentTableColumns",
          JSON.stringify(updatedVisibility),
        );
      }
    } catch (error) {
      console.error("Error saving column visibility to localStorage:", error);
    }
  };

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

  const table = useReactTable({
    data: environmentsList,
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
    columnResizeMode: "onChange" as ColumnResizeMode,
    filterFns: {
      includesString: (row, columnId, filterValue) => {
        const value = String(row.getValue(columnId) || "").toLowerCase();
        return value.includes(String(filterValue).toLowerCase());
      },
    },
  });

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flex: 1,
        width: "100%",
        position: "relative",
        maxWidth: "100%",
        p: 3,
      }}
    >
      <PageHeader
        title={t("settings.environments.title")}
        description={t("settings.environments.description")}
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddEnvironment}
            sx={{
              borderRadius: "8px",
              textTransform: "none",
              px: 3,
              height: 40,
            }}
          >
            {t("settings.environments.addButton")}
          </Button>
        }
      />

      <TableFiltersProvider {...tableFiltersValue}>
        <BaseTableToolbar
          globalFilter={globalFilter}
          onGlobalFilterChange={setGlobalFilter}
          onColumnMenuOpen={(event) =>
            setColumnVisibilityAnchor(event.currentTarget)
          }
          activeFilters={tableFiltersValue.activeFilters}
          activeSorting={tableFiltersValue.activeSorting}
          onRemoveFilter={tableFiltersValue.onRemoveFilter}
          onRemoveSort={tableFiltersValue.onRemoveSort}
          searchPlaceholder={t("settings.environments.searchPlaceholder")}
        />

        <PageContent
          isLoading={isLoadingEnvironments}
          error={environmentsError as Error}
        >
          <EnvironmentList table={table} onFilterColumn={handleFilterColumn} />

          <BaseFilterPopover
            anchorEl={columnMenuAnchor}
            column={
              activeFilterColumn ? table.getColumn(activeFilterColumn) : null
            }
            onClose={handleFilterMenuClose}
            data={environmentsList}
            getUniqueValues={(columnId, data) => {
              return Array.from(
                new Set(
                  data.map((item) => {
                    const value = item[columnId as keyof Environment];
                    return value ? String(value) : "";
                  }),
                ),
              ).filter(Boolean);
            }}
          />

          <ColumnVisibilityMenu
            anchorEl={columnVisibilityAnchor}
            onClose={() => setColumnVisibilityAnchor(null)}
            columns={table.getAllColumns()}
          />

          <EnvironmentForm
            open={openEnvironmentForm}
            onClose={() => setOpenEnvironmentForm(false)}
            onSave={handleSaveEnvironment}
            environment={editingEnvironment}
          />

          <ApiStatusModal
            open={apiStatus.show}
            status={apiStatus.status}
            action={apiStatus.action}
            message={apiStatus.message}
            onClose={handleCloseApiStatus}
          />
        </PageContent>
      </TableFiltersProvider>
    </Box>
  );
};

export default EnvironmentsPage;
