import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ColumnFiltersState, PaginationState } from "@tanstack/react-table";
import {
  useGetPipelines,
  useDeletePipeline,
  useStartPipeline,
  useStopPipeline,
  useUpdatePipeline,
} from "../api/pipelinesController";
import type { Pipeline, PipelinesResponse } from "../types/pipelines.types";
import queryClient from "@/api/queryClient";

const PAGE_SIZE = 20;

export const usePipelineManager = () => {
  // Track which pipelines are currently being toggled
  const [togglingPipelines, setTogglingPipelines] = useState<
    Record<string, boolean>
  >({});
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showDeleteButton, setShowDeleteButton] = useState(false);
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: PAGE_SIZE,
  });

  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    pipelineId: "",
    pipelineName: "",
    userInput: "",
  });

  const [filters, setFilters] = useState({
    type: "",
    name: "",
    system: "",
    sortBy: "createdAt",
    sortOrder: "desc" as "asc" | "desc",
  });

  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success" as "success" | "error",
  });

  const {
    data: pipelinesResponse,
    isLoading,
    error,
    refetch,
  } = useGetPipelines();

  const deletePipelineMutation = useDeletePipeline();
  const startPipelineMutation = useStartPipeline();
  const stopPipelineMutation = useStopPipeline();
  const updatePipelineMutation = useUpdatePipeline();

  // Keyboard shortcut effect for delete button
  useEffect(() => {
    let keySequence: string[] = [];
    let shiftKeyPressed = false;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.shiftKey) {
        shiftKeyPressed = true;
      }

      if (
        shiftKeyPressed &&
        ["d", "e", "l"].includes(event.key.toLowerCase())
      ) {
        keySequence.push(event.key.toLowerCase());
        if (keySequence.join("") === "del") {
          event.preventDefault();
          setShowDeleteButton((prev) => !prev);
          keySequence = [];
        }
      } else if (shiftKeyPressed) {
        keySequence = [];
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === "Shift") {
        shiftKeyPressed = false;
        keySequence = [];
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleEdit = (id: string) => {
    navigate(`/pipelines/${id}`);
  };

  // We don't need the handleDeletePipeline function anymore since we're using the mutation directly in PipelinesPage.tsx

  const openDeleteDialog = (id: string, name: string) => {
    setDeleteDialog({
      open: true,
      pipelineId: id,
      pipelineName: name,
      userInput: "",
    });
  };

  const closeDeleteDialog = () => {
    setDeleteDialog({
      open: false,
      pipelineId: "",
      pipelineName: "",
      userInput: "",
    });
  };

  const setDeleteDialogInput = (value: string) => {
    setDeleteDialog((prev) => ({ ...prev, userInput: value }));
  };

  const handleColumnMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setColumnMenuAnchor(event.currentTarget);
  };

  const handleColumnMenuClose = () => {
    setColumnMenuAnchor(null);
  };

  const handleFilterMenuOpen = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    setFilterMenuAnchor(event.currentTarget);
    setActiveFilterColumn(columnId);
  };

  const handleFilterMenuClose = () => {
    setFilterMenuAnchor(null);
    setActiveFilterColumn(null);
  };

  const pipelines = pipelinesResponse?.data?.s || [];
  const searchMetadata = pipelinesResponse?.data?.searchMetadata || {
    totalResults: 0,
    pageSize: PAGE_SIZE,
    nextToken: null,
  };

  return {
    // State
    pipelines,
    searchMetadata,
    showDeleteButton,
    globalFilter,
    columnFilters,
    columnVisibility,
    columnMenuAnchor,
    filterMenuAnchor,
    activeFilterColumn,
    pagination,
    deleteDialog,
    snackbar,
    isLoading,
    error,
    isDeleting: deletePipelineMutation.isPending,
    // Non-blocking function that handles errors and timeouts
    deletePipeline: (id: string) => {
      const startTime = performance.now();
      console.log(
        `[usePipelineManager] Starting delete operation for pipeline ID: ${id}`,
      );

      // Create a timeout promise to prevent hanging
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          console.error(
            `[usePipelineManager] Delete operation timed out after 30 seconds for pipeline ID: ${id}`,
          );
          reject(new Error("Delete operation timed out after 30 seconds"));
        }, 30000);
      });

      // Return a promise that resolves when the operation completes
      return new Promise((resolve, reject) => {
        // Race the deletion against the timeout
        Promise.race([deletePipelineMutation.mutateAsync(id), timeoutPromise])
          .then(() => {
            console.log(
              `[usePipelineManager] Delete operation completed successfully for pipeline ID: ${id} in ${
                performance.now() - startTime
              }ms`,
            );

            // Refresh the pipeline list in the background
            refetch().catch((refetchError) => {
              console.error(
                `[usePipelineManager] Error refreshing pipeline list after deletion:`,
                refetchError,
              );
            });

            resolve(true);
          })
          .catch((error) => {
            console.error(
              `[usePipelineManager] Error in delete operation for pipeline ID: ${id} after ${
                performance.now() - startTime
              }ms`,
              error,
            );

            // Still try to refresh the list in case the deletion actually succeeded
            refetch().catch((refetchError) => {
              console.error(
                `[usePipelineManager] Error refreshing pipeline list after deletion:`,
                refetchError,
              );
            });

            reject(error);
          });
      });
    },
    startPipeline: startPipelineMutation.mutate,
    stopPipeline: stopPipelineMutation.mutate,
    // Track which pipelines are currently being toggled
    togglingPipelines,

    // Enhanced toggleActive with optimistic updates
    toggleActive: (id: string, active: boolean) => {
      console.log(
        `[usePipelineManager] Toggling pipeline ${id} active state to ${active}`,
      );

      // Mark this pipeline as currently toggling
      setTogglingPipelines((prev) => ({ ...prev, [id]: true }));

      // Create a copy of the current pipelines for optimistic update
      const updatedPipelines = pipelines.map((pipeline) =>
        pipeline.id === id ? { ...pipeline, active } : pipeline,
      );

      // Optimistically update the query data
      queryClient.setQueryData(["pipelines", "list"], {
        ...pipelinesResponse,
        data: {
          ...pipelinesResponse?.data,
          s: updatedPipelines,
        },
      });

      return updatePipelineMutation
        .mutateAsync({
          id,
          data: { active },
        })
        .then(() => {
          console.log(
            `[usePipelineManager] Successfully toggled pipeline ${id} active state to ${active}`,
          );
          // Remove from toggling state
          setTogglingPipelines((prev) => {
            const updated = { ...prev };
            delete updated[id];
            return updated;
          });
          // Refetch to ensure data consistency
          refetch();
        })
        .catch((error) => {
          console.error(
            `[usePipelineManager] Error toggling pipeline ${id} active state:`,
            error,
          );

          // Revert the optimistic update on error
          queryClient.setQueryData(["pipelines", "list"], pipelinesResponse);

          // Remove from toggling state
          setTogglingPipelines((prev) => {
            const updated = { ...prev };
            delete updated[id];
            return updated;
          });

          // Show error in snackbar
          setSnackbar({
            open: true,
            message: `Failed to ${active ? "enable" : "disable"} pipeline: ${
              error.message || "Unknown error"
            }`,
            severity: "error",
          });

          throw error;
        });
    },
    refetch,

    // Actions
    setPagination,
    setGlobalFilter,
    setColumnFilters,
    setColumnVisibility,
    handleCloseSnackbar,
    handleEdit,
    openDeleteDialog,
    closeDeleteDialog,
    setDeleteDialogInput,
    handleColumnMenuOpen,
    handleColumnMenuClose,
    handleFilterMenuOpen,
    handleFilterMenuClose,
  };
};
