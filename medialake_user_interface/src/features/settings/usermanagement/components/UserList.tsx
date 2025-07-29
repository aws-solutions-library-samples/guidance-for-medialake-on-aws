import React, { useMemo, useState, useRef } from "react";
import {
  Box,
  Typography,
  Chip,
  Tooltip,
  IconButton,
  useTheme,
  alpha,
  Menu,
  MenuItem,
} from "@mui/material";
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  FilterFn,
  ColumnResizeMode,
  ColumnSizingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import LockIcon from "@mui/icons-material/Lock";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { User } from "@/api/types/api.types";
import { useGetGroups } from "@/api/hooks/useGroups";
import { useGetPermissionSets } from "@/api/hooks/usePermissionSets";
import {
  useAddGroupMembers,
  useRemoveGroupMember,
} from "@/api/hooks/useGroups";
import { useListUserAssignments } from "@/api/hooks/useAssignments";
import { useTranslation } from "react-i18next";
import { UserFilterPopover } from "./UserFilterPopover";
import {
  ResizableTable,
  ColumnVisibilityMenu,
  TableCellContent,
} from "@/components/common/table";
import { UserTableToolbar } from "./UserTableToolbar";
import {
  TableFiltersProvider,
  TableFilter,
  TableSort,
} from "@/components/common/table/context/TableFiltersContext";

interface UserListProps {
  users: User[];
  onEditUser: (user: User) => void;
  onDeleteUser: (username: string) => void;
  onToggleUserStatus: (username: string, newStatus: boolean) => void;
  activeFilters?: { columnId: string; value: string }[];
  activeSorting?: { columnId: string; desc: boolean }[];
  onRemoveFilter?: (columnId: string) => void;
  onRemoveSort?: (columnId: string) => void;
  onFilterChange?: (columnId: string, value: string) => void;
  onSortChange?: (columnId: string, desc: boolean) => void;
}

// Helper component for managing permission set chips
const PermissionSetCell: React.FC<{
  user: User;
  theme: any;
  permissionSets: any[] | undefined;
}> = ({ user, theme, permissionSets }) => {
  const { data: userAssignments } = useListUserAssignments(user.username);

  return (
    <PermissionSetChips
      user={user}
      theme={theme}
      permissionSets={permissionSets}
      userAssignments={userAssignments}
    />
  );
};

// Helper component for managing group chips
const GroupChips: React.FC<{
  user: User;
  theme: any;
  groups: any[] | undefined;
}> = ({ user, theme, groups }) => {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const addGroupMembersMutation = useAddGroupMembers();
  const removeGroupMemberMutation = useRemoveGroupMember();

  const handleAddClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleAddToGroup = async (groupId: string) => {
    try {
      await addGroupMembersMutation.mutateAsync({
        groupId,
        request: { userIds: [user.username] },
      });
      handleClose();
    } catch (error) {
      console.error("Error adding user to group:", error);
    }
  };

  const handleRemoveFromGroup = async (groupId: string) => {
    try {
      await removeGroupMemberMutation.mutateAsync({
        groupId,
        userId: user.username,
      });
    } catch (error) {
      console.error("Error removing user from group:", error);
    }
  };

  // Filter out groups the user is not a member of
  const availableGroups =
    groups?.filter((group) => !user.groups?.includes(group.name)) || [];

  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        gap: 1,
        alignItems: "center",
      }}
    >
      {user.groups && user.groups.length > 0 ? (
        user.groups.map((groupName) => (
          <Chip
            key={groupName}
            label={groupName}
            size="small"
            onDelete={() => {
              const group = groups?.find((g) => g.name === groupName);
              if (group) {
                handleRemoveFromGroup(group.id);
              }
            }}
            deleteIcon={<CloseIcon fontSize="small" />}
            sx={{
              backgroundColor: alpha(theme.palette.primary.main, 0.1),
              color: theme.palette.primary.main,
              fontWeight: 600,
              borderRadius: "6px",
              height: "24px",
              "& .MuiChip-label": {
                px: 1.5,
              },
            }}
          />
        ))
      ) : (
        <Typography variant="body2" color="text.secondary">
          {t("common.noGroups")}
        </Typography>
      )}

      <IconButton
        size="small"
        onClick={handleAddClick}
        sx={{
          width: 24,
          height: 24,
          backgroundColor: alpha(theme.palette.primary.main, 0.1),
        }}
      >
        <AddIcon fontSize="small" />
      </IconButton>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}>
        {availableGroups.length > 0 ? (
          availableGroups.map((group) => (
            <MenuItem key={group.id} onClick={() => handleAddToGroup(group.id)}>
              {group.name}
            </MenuItem>
          ))
        ) : (
          <MenuItem disabled>{t("groups.noAvailableGroups")}</MenuItem>
        )}
      </Menu>
    </Box>
  );
};

// Helper component for displaying permission set chips (read-only)
const PermissionSetChips: React.FC<{
  user: User;
  theme: any;
  permissionSets: any[] | undefined;
  userAssignments: any | undefined;
}> = ({ user, theme, permissionSets, userAssignments }) => {
  const { t } = useTranslation();

  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        gap: 1,
        alignItems: "center",
      }}
    >
      {userAssignments?.assignments &&
      userAssignments.assignments.length > 0 ? (
        userAssignments.assignments.map((assignment) => (
          <Chip
            key={assignment.permissionSetId}
            label={assignment.permissionSetName}
            size="small"
            sx={{
              backgroundColor: alpha(theme.palette.secondary.main, 0.1),
              color: theme.palette.secondary.main,
              fontWeight: 600,
              borderRadius: "6px",
              height: "24px",
              "& .MuiChip-label": {
                px: 1.5,
              },
            }}
          />
        ))
      ) : (
        <Typography variant="body2" color="text.secondary">
          {t("permissionSets.noAssignments")}
        </Typography>
      )}
    </Box>
  );
};

const containsFilter: FilterFn<any> = (row, columnId, filterValue) => {
  const cellValue = row.getValue(columnId);
  if (cellValue == null) return false;

  // Handle date filtering
  if (typeof filterValue === "object" && filterValue.filterDate) {
    const cellDate = new Date(cellValue as string);
    const dateStr = cellDate.toLocaleDateString();
    return dateStr === filterValue.value;
  }

  return String(cellValue)
    .toLowerCase()
    .includes(String(filterValue).toLowerCase());
};

const UserList: React.FC<UserListProps> = ({
  users,
  onEditUser,
  onDeleteUser,
  onToggleUserStatus,
  activeFilters = [],
  activeSorting = [],
  onRemoveFilter,
  onRemoveSort,
  onFilterChange,
  onSortChange,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

  // Fetch groups and permission sets at the parent level
  const { data: groups } = useGetGroups(true);
  const { data: permissionSets } = useGetPermissionSets(true); // Enable API call when this component is loaded

  // Sync external state with internal state
  React.useEffect(() => {
    if (activeSorting) {
      setSorting(
        activeSorting.map((sort) => ({
          id: sort.columnId,
          desc: sort.desc,
        })),
      );
    }
  }, [activeSorting]);

  React.useEffect(() => {
    if (activeFilters) {
      setColumnFilters(
        activeFilters.map((filter) => ({
          id: filter.columnId,
          value: filter.value,
        })),
      );
    }
  }, [activeFilters]);

  // Handle internal state changes
  const handleSortingChange = (newSorting: SortingState) => {
    setSorting(newSorting);
    if (onSortChange && newSorting.length > 0) {
      newSorting.forEach((sort) => {
        onSortChange(sort.id, sort.desc);
      });
    } else if (onSortChange) {
      onSortChange("", false);
    }
  };

  const handleFilterChange = (newFilters: ColumnFiltersState) => {
    setColumnFilters(newFilters);
    if (onFilterChange && newFilters.length > 0) {
      newFilters.forEach((filter) => {
        onFilterChange(filter.id, filter.value as string);
      });
    }
  };
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnVisibility, setColumnVisibility] = useState({
    username: false,
    modified: true, // Show modified column by default
    permissionSets: false, // Hide permission sets column by default
  });
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );

  const formatDate = (dateString: string, includeTime: boolean = false) => {
    const date = new Date(dateString);
    if (includeTime) {
      return date.toLocaleString(undefined, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  };

  const columns = useMemo<ColumnDef<User>[]>(() => {
    console.log("Theme in columns useMemo:", theme);
    return [
      {
        header: t("common.columns.username"),
        accessorKey: "username",
        minSize: 120,
        size: 180,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => {
          console.log("Cell theme:", theme);
          return (
            <TableCellContent variant="primary">
              {getValue() as string}
            </TableCellContent>
          );
        },
      },
      {
        header: t("common.columns.firstName"),
        accessorKey: "name",
        minSize: 100,
        size: 160,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">
            {(getValue() as string) || "-"}
          </TableCellContent>
        ),
      },
      {
        header: t("common.columns.lastName"),
        accessorKey: "family_name",
        minSize: 120,
        size: 160,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary">
            {(getValue() as string) || "-"}
          </TableCellContent>
        ),
      },
      {
        header: t("common.columns.email"),
        accessorKey: "email",
        minSize: 150,
        size: 275,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => (
          <TableCellContent variant="secondary" wordBreak="break-all">
            {getValue() as string}
          </TableCellContent>
        ),
      },
      {
        header: t("common.columns.status"),
        accessorKey: "enabled",
        minSize: 100,
        size: 100,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => {
          const enabled = getValue() as boolean;
          return (
            <Chip
              label={
                enabled
                  ? t("common.status.active")
                  : t("common.status.inactive")
              }
              size="small"
              sx={{
                backgroundColor: enabled
                  ? alpha(theme.palette.success.main, 0.1)
                  : alpha(theme.palette.grey[500], 0.1),
                color: enabled
                  ? theme.palette.success.main
                  : theme.palette.grey[500],
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
        header: t("common.columns.groups"),
        accessorKey: "groups",
        minSize: 200,
        size: 250,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ row }) => {
          return (
            <GroupChips user={row.original} theme={theme} groups={groups} />
          );
        },
      },
      {
        header: t("common.columns.permissionSets"),
        id: "permissionSets",
        minSize: 200,
        size: 250,
        enableResizing: true,
        enableSorting: false,
        enableFiltering: false,
        cell: ({ row }) => {
          return (
            <PermissionSetCell
              user={row.original}
              theme={theme}
              permissionSets={permissionSets}
            />
          );
        },
      },
      {
        header: t("common.columns.created"),
        accessorKey: "created",
        minSize: 120,
        size: 120,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => {
          const dateValue = getValue() as string;
          return (
            <Tooltip title={formatDate(dateValue, true)} placement="top">
              <Box>
                <TableCellContent variant="secondary">
                  {formatDate(dateValue)}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      },
      {
        header: t("common.columns.modified"),
        accessorKey: "modified",
        minSize: 150,
        size: 200,
        enableResizing: true,
        enableSorting: true,
        enableFiltering: true,
        cell: ({ getValue }) => {
          const dateValue = getValue() as string;
          return (
            <Tooltip title={formatDate(dateValue, true)} placement="top">
              <Box>
                <TableCellContent variant="secondary">
                  {formatDate(dateValue)}
                </TableCellContent>
              </Box>
            </Tooltip>
          );
        },
      },
      {
        id: "actions",
        header: () => (
          <Box sx={{ width: "100%", textAlign: "center" }}>
            {t("common.columns.actions")}
          </Box>
        ),
        minSize: 100,
        size: 120,
        enableResizing: true,
        enableSorting: false,
        cell: ({ row }) => (
          <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
            <Tooltip title={t("common.actions.edit")}>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onEditUser(row.original);
                }}
                sx={{
                  backgroundColor: alpha(theme.palette.primary.main, 0.1),
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                  },
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip
              title={
                row.original.enabled
                  ? t("common.actions.deactivate")
                  : t("common.actions.activate")
              }
            >
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleUserStatus(
                    row.original.username,
                    !row.original.enabled,
                  );
                }}
                sx={{
                  backgroundColor: row.original.enabled
                    ? alpha(theme.palette.success.main, 0.1)
                    : alpha(theme.palette.grey[500], 0.1),
                  "&:hover": {
                    backgroundColor: row.original.enabled
                      ? alpha(theme.palette.success.main, 0.2)
                      : alpha(theme.palette.grey[500], 0.2),
                  },
                }}
              >
                {row.original.enabled ? (
                  <LockOpenIcon fontSize="small" />
                ) : (
                  <LockIcon fontSize="small" />
                )}
              </IconButton>
            </Tooltip>
            <Tooltip title={t("common.actions.delete")}>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteUser(row.original.username);
                }}
                sx={{
                  backgroundColor: alpha(theme.palette.error.main, 0.1),
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.error.main, 0.2),
                  },
                }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      },
    ];
  }, [
    theme,
    t,
    onEditUser,
    onDeleteUser,
    onToggleUserStatus,
    groups,
    permissionSets,
  ]);

  const table = useReactTable({
    data: users,
    columns,
    filterFns: {
      contains: containsFilter,
    },
    state: {
      sorting,
      columnFilters,
      globalFilter,
      columnVisibility,
      columnSizing,
    },
    onSortingChange: handleSortingChange,
    onColumnFiltersChange: handleFilterChange,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange" as ColumnResizeMode,
  });

  const { rows } = table.getRowModel();
  const containerRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 10,
  });

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

  const tableFiltersValue = useMemo(
    () => ({
      activeFilters: columnFilters.map((f) => ({
        columnId: f.id,
        value: f.value as string,
      })) as TableFilter[],
      activeSorting: sorting.map((s) => ({
        columnId: s.id,
        desc: s.desc,
      })) as TableSort[],
      onRemoveFilter,
      onRemoveSort,
      onFilterChange: (columnId: string, value: string) => {
        const newFilters = columnFilters.map((f) =>
          f.id === columnId ? { ...f, value } : f,
        );
        handleFilterChange(newFilters);
      },
      onSortChange: (columnId: string, desc: boolean) => {
        const newSorting = sorting.map((s) =>
          s.id === columnId ? { ...s, desc } : s,
        );
        handleSortingChange(newSorting);
      },
    }),
    [
      columnFilters,
      sorting,
      onRemoveFilter,
      onRemoveSort,
      handleFilterChange,
      handleSortingChange,
    ],
  );

  return (
    <TableFiltersProvider {...tableFiltersValue}>
      <Box
        sx={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          flex: 1,
        }}
      >
        <UserTableToolbar
          globalFilter={globalFilter}
          onGlobalFilterChange={setGlobalFilter}
          onColumnMenuOpen={handleColumnMenuOpen}
          activeFilters={activeFilters}
          activeSorting={activeSorting}
          onRemoveFilter={onRemoveFilter}
          onRemoveSort={onRemoveSort}
        />

        <ResizableTable
          table={table}
          containerRef={containerRef}
          virtualizer={rowVirtualizer}
          rows={rows}
          onFilterClick={handleFilterMenuOpen}
          activeFilters={activeFilters}
          activeSorting={activeSorting}
          onRemoveFilter={onRemoveFilter}
          onRemoveSort={onRemoveSort}
        />

        <ColumnVisibilityMenu
          anchorEl={columnMenuAnchor}
          columns={table.getAllLeafColumns()}
          onClose={handleColumnMenuClose}
          excludeIds={["actions", "permissionSets"]}
        />

        <UserFilterPopover
          anchorEl={filterMenuAnchor}
          column={
            activeFilterColumn ? table.getColumn(activeFilterColumn) : null
          }
          onClose={handleFilterMenuClose}
          users={users}
        />
      </Box>
    </TableFiltersProvider>
  );
};

export default UserList;
