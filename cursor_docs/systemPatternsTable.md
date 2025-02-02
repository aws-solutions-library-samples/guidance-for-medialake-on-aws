# Table/List Pattern Documentation

This document outlines the standard pattern for implementing tables and lists in the application, using the Environments implementation as the reference example.

## Directory Structure

```
src/
  components/
    common/
      table/
        index.ts                # Barrel exports
        BaseTable.tsx           # Core table functionality
        ResizableTable.tsx      # Enhanced table with resizing
        TableDensityToggle.tsx  # Density control
        TableCellContent.tsx    # Cell content wrapper
        BaseTableToolbar.tsx    # Table toolbar
        BaseFilterPopover.tsx   # Filter popover
        ColumnVisibilityMenu.tsx# Column visibility control
  features/
    [feature-name]/
      components/
        [TableName]/
          index.tsx            # Main table component
          cells/              # Custom cell components
            ActionsCell.tsx
            StatusCell.tsx
      hooks/
        useTableVirtualizer.ts # Table virtualization
        useColumns.ts         # Column definitions
      context/
        TableFiltersContext.tsx# Filter/sort state
      types/
        table.types.ts        # Table-specific types
```

## Core Components

### 1. Base Components (src/components/common/table/)

#### BaseTable
The foundation component that provides core table functionality:
```typescript
interface BaseTableProps<T> {
    table: TanStackTable<T>;                           // TanStack table instance
    virtualizer: Virtualizer<HTMLDivElement, Element>; // Virtualization handler
    isLoading?: boolean;                              // Loading state
    activeFilters?: ColumnFilter[];                   // Active column filters
    activeSorting?: ColumnSort[];                     // Active sorting state
    onRemoveFilter: (id: string) => void;             // Filter removal handler
    onRemoveSort: (id: string) => void;               // Sort removal handler
    searchPlaceholder?: string;                       // Global search placeholder
}
```

#### ResizableTable
Extends BaseTable with additional features:
```typescript
interface ResizableTableProps<T> {
    table: TanStackTable<T>;                          // TanStack table instance
    containerRef: React.RefObject<HTMLDivElement>;    // Container reference
    virtualizer: Virtualizer<HTMLDivElement, Element>;// Virtualization handler
    rows: Row<T>[];                                   // Table rows
    maxHeight?: string;                               // Optional max height
    onFilterClick?: (                                 // Filter click handler
        event: React.MouseEvent<HTMLElement>, 
        columnId: string
    ) => void;
    activeFilters?: Array<{                          // Active filters
        columnId: string; 
        value: string;
    }>;
    activeSorting?: Array<{                          // Active sorting
        columnId: string; 
        desc: boolean;
    }>;
    onRemoveFilter?: (columnId: string) => void;     // Filter removal handler
    onRemoveSort?: (columnId: string) => void;       // Sort removal handler
    onRowClick?: (row: Row<T>) => void;              // Row click handler
}
```

#### BaseTableToolbar
Provides table controls and search functionality:
```typescript
interface BaseTableToolbarProps {
    globalFilter: string;                            // Global search value
    onGlobalFilterChange: (value: string) => void;   // Search handler
    onColumnMenuOpen: (                              // Column menu handler
        event: React.MouseEvent<HTMLElement>
    ) => void;
    activeFilters?: Array<{                         // Active filters
        columnId: string;
        value: string;
    }>;
    activeSorting?: Array<{                         // Active sorting
        columnId: string;
        desc: boolean;
    }>;
    onRemoveFilter?: (columnId: string) => void;    // Filter removal
    onRemoveSort?: (columnId: string) => void;      // Sort removal
    searchPlaceholder?: string;                     // Search placeholder
}
```

### 2. Context Providers

#### TableFiltersContext
Manages filter and sort state:
```typescript
interface TableFiltersContextType {
    activeFilters: TableFilter[];                    // Active filters
    activeSorting: TableSort[];                      // Active sorting
    onRemoveFilter: (columnId: string) => void;      // Remove filter
    onRemoveSort: (columnId: string) => void;        // Remove sort
    onFilterChange?: (                               // Update filter
        columnId: string, 
        value: string
    ) => void;
    onSortChange?: (                                // Update sort
        columnId: string, 
        desc: boolean
    ) => void;
}
```

#### TableDensityContext
Manages table row density:
```typescript
interface TableDensityContextType {
    mode: 'compact' | 'normal';                      // Density mode
    toggleMode: () => void;                          // Toggle density
}
```

### 3. Custom Hooks

#### useTableVirtualizer
```typescript
interface UseTableVirtualizerOptions {
    rowHeight?: number;                              // Row height
    overscan?: number;                               // Overscan amount
}

const useTableVirtualizer = <T extends HTMLElement>(
    rows: any[],
    containerRef: React.RefObject<T>,
    options?: UseTableVirtualizerOptions
) => Virtualizer;
```

#### useColumns
```typescript
const useColumns = <T>() => {
    return useMemo(
        () => [
            columnHelper.accessor('field', {
                header: 'Header',
                size: 200,
                enableSorting: true,
                cell: (props) => <CustomCell {...props} />
            }),
            // ... other columns
        ],
        []
    );
};
```

### BaseFilterPopover
Provides standardized filter popover functionality:
```typescript
interface BaseFilterPopoverProps<T> {
    anchorEl: HTMLElement | null;                    // Anchor element for popover
    column: Column<T, unknown> | null;               // Current column being filtered
    onClose: () => void;                            // Close handler
    data: T[];                                      // Data for generating unique values
    getUniqueValues: (                              // Function to get unique values
        columnId: string, 
        data: T[]
    ) => string[];
    formatValue?: (                                 // Optional value formatter
        columnId: string, 
        value: string
    ) => string;
}
```

## Filter Modal Behavior

### 1. Modal Interaction Patterns
```typescript
// Implementation in BaseFilterPopover
const BaseFilterPopover = <T,>({ 
    anchorEl, 
    column, 
    onClose,
    data,
    getUniqueValues,
    formatValue 
}: BaseFilterPopoverProps<T>) => {
    // Close handlers
    const handleTextFilterSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation();
            onClose();
        }
    };

    const handleSelectFilterChange = (value: string) => {
        if (value) {
            column.setFilterValue(value);
        } else {
            column.setFilterValue('');
        }
        onClose();  // Auto-close on select
    };

    return (
        <Popover
            open={Boolean(anchorEl)}
            anchorEl={anchorEl}
            onClose={onClose}
            // ... other Popover props
        >
            <IconButton
                onClick={onClose}
                size="small"
                sx={{
                    position: 'absolute',
                    right: 8,
                    top: 8,
                }}
            >
                <CloseIcon fontSize="small" />
            </IconButton>
            {/* Filter content */}
        </Popover>
    );
};
```

### 2. Filter Tags Implementation
```typescript
// In BaseTableToolbar
interface FilterTag {
    columnId: string;
    value: string;
}

const FilterTags: React.FC<{
    activeFilters: FilterTag[];
    onRemoveFilter: (columnId: string) => void;
}> = ({ activeFilters, onRemoveFilter }) => {
    return (
        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            {activeFilters.map(({ columnId, value }) => (
                <Chip
                    key={columnId}
                    label={`${columnId}: ${value}`}
                    onDelete={() => onRemoveFilter(columnId)}
                    size="small"
                />
            ))}
        </Stack>
    );
};
```

### 3. Required Behaviors
The following behaviors must be implemented in any table filter implementation:

1. **Modal Closing**:
   - Close on 'X' button click
   - Close on 'Enter' key in text input
   - Close on selection from dropdown
   - Close on click outside (handled by Popover)

2. **Filter Application**:
   - Text filters should apply immediately on input
   - Dropdown selection should apply and close modal
   - Clear filter button should clear and remain open

3. **Filter Tags**:
   - Display above or below toolbar
   - Show column name and filter value
   - Include delete functionality
   - Update in real-time

4. **Sort Tag Behavior**:
   - Tags appear when columns are sorted
   - Each tag shows column name and sort direction
   - Clicking × removes the sort
   - Tags use secondary theme color with alpha transparency
   - Tags appear after filter tags in the flow

5. **State Management**:
   - Filter state managed through TableFiltersContext
   - Sort state managed through TableFiltersContext
   - State updates trigger re-renders of tags
   - State persists during table operations

6. **Accessibility**:
   - Tags should be keyboard navigable
   - Delete buttons should have proper ARIA labels
   - Color contrast should meet WCAG standards
   - Screen reader support for tag actions

### 4. Example Implementation
```typescript
const FeatureFilterPopover: React.FC<FilterPopoverProps> = ({
    anchorEl,
    column,
    onClose,
    data,
}) => {
    const getUniqueValues = (columnId: string, data: T[]) => {
        const values = new Set<string>();
        data.forEach(item => {
            const value = item[columnId as keyof T];
            if (value != null) {
                values.add(String(value));
            }
        });
        return Array.from(values).sort();
    };

    const formatValue = (columnId: string, value: string) => {
        // Custom value formatting logic
        return value;
    };

    return (
        <BaseFilterPopover<T>
            anchorEl={anchorEl}
            column={column}
            onClose={onClose}
            data={data}
            getUniqueValues={getUniqueValues}
            formatValue={formatValue}
        />
    );
};
```

### 5. Filter State Management
```typescript
// In TableFiltersContext
interface TableFiltersState {
    activeFilters: FilterTag[];
    activeSorting: SortTag[];
}

const TableFiltersProvider: React.FC = ({ children }) => {
    const [state, setState] = useState<TableFiltersState>({
        activeFilters: [],
        activeSorting: [],
    });

    const onRemoveFilter = (columnId: string) => {
        setState(prev => ({
            ...prev,
            activeFilters: prev.activeFilters.filter(
                filter => filter.columnId !== columnId
            ),
        }));
    };

    // ... other state management logic

    return (
        <TableFiltersContext.Provider value={{
            ...state,
            onRemoveFilter,
            // ... other handlers
        }}>
            {children}
        </TableFiltersContext.Provider>
    );
};
```

## Table State Management Pattern

### 1. State Management Layers

#### Internal Table State (`useTable` hook)
- Manages the TanStack table's internal state
- Handles immediate UI updates
- Manages column visibility and sizing
- Handles global filter

#### External Filter/Sort State (`TableFiltersContext`)
- Manages persistent filter/sort state
- Handles filter/sort tag display
- Manages filter/sort synchronization across components

### 2. Implementation Steps

1. **Setup Table State**
```typescript
const {
    table,
    sorting,
    columnFilters,
    setGlobalFilter,
    handleColumnMenuOpen
} = useTable({
    data,
    columns,
    activeFilters,    // From TableFiltersContext
    activeSorting,    // From TableFiltersContext
    onFilterChange,   // Callback to update TableFiltersContext
    onSortChange     // Callback to update TableFiltersContext
});
```

2. **Setup Filter Context State**
```typescript
const tableFiltersValue = useMemo(() => ({
    activeFilters: columnFilters.map(f => ({ 
        columnId: f.id, 
        value: f.value as string 
    })),
    activeSorting: sorting.map(s => ({ 
        columnId: s.id, 
        desc: s.desc 
    })),
    onRemoveFilter,
    onRemoveSort,
    onFilterChange,
    onSortChange
}), [columnFilters, sorting]);
```

3. **Component Integration**
```typescript
return (
    <TableFiltersProvider {...tableFiltersValue}>
        <BaseTableToolbar
            globalFilter={globalFilter}
            onGlobalFilterChange={setGlobalFilter}
            activeFilters={tableFiltersValue.activeFilters}
            activeSorting={tableFiltersValue.activeSorting}
            onRemoveFilter={tableFiltersValue.onRemoveFilter}
            onRemoveSort={tableFiltersValue.onRemoveSort}
        />
        <ResizableTable
            table={table}
            containerRef={containerRef}
            virtualizer={virtualizer}
            rows={rows}
            activeFilters={tableFiltersValue.activeFilters}
            activeSorting={tableFiltersValue.activeSorting}
            onRemoveFilter={tableFiltersValue.onRemoveFilter}
            onRemoveSort={tableFiltersValue.onRemoveSort}
        />
    </TableFiltersProvider>
);
```

### 3. State Flow

1. **Filter/Sort Application**
   - User clicks filter/sort icon
   - Internal table state updates via `useTable`
   - `useTable` callbacks trigger context updates
   - Context updates trigger tag renders

2. **Tag Removal**
   - User clicks tag remove button
   - Context state updates
   - Context changes sync back to table via `useTable` props
   - Table re-renders with updated state

### 4. Required Implementation Checks

- [ ] `useTable` hook properly configured with callbacks
- [ ] TableFiltersProvider wrapped around table components
- [ ] Filter/sort state properly mapped between formats
- [ ] All removal handlers properly connected
- [ ] Tag rendering tied to context state

## Implementation Example

### 1. Feature Table Component
```typescript
const FeatureTable: React.FC = () => {
    const containerRef = useRef<HTMLDivElement>(null);
    const columns = useColumns();
    const { data, isLoading } = useFeatureData();
    
    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
    });
    
    const { rows } = table.getRowModel();
    const virtualizer = useTableVirtualizer(rows, containerRef);
    const { 
        activeFilters, 
        activeSorting,
        onRemoveFilter,
        onRemoveSort 
    } = useTableFilters();

    return (
        <Box ref={containerRef} sx={{ height: '100%', overflow: 'auto' }}>
            <BaseTableToolbar
                globalFilter={table.getState().globalFilter}
                onGlobalFilterChange={table.setGlobalFilter}
                activeFilters={activeFilters}
                activeSorting={activeSorting}
                onRemoveFilter={onRemoveFilter}
                onRemoveSort={onRemoveSort}
            />
            <ResizableTable
                table={table}
                containerRef={containerRef}
                virtualizer={virtualizer}
                rows={rows}
                isLoading={isLoading}
                activeFilters={activeFilters}
                activeSorting={activeSorting}
                onRemoveFilter={onRemoveFilter}
                onRemoveSort={onRemoveSort}
            />
        </Box>
    );
};
```

### 2. Custom Cell Components
```typescript
const CustomCell: React.FC<CellProps<T>> = ({ 
    getValue,
    row 
}) => {
    return (
        <TableCellContent variant="primary">
            {getValue()}
        </TableCellContent>
    );
};
```

## Best Practices

1. **Performance**
   - Always use virtualization for large datasets
   - Memoize column definitions and callbacks
   - Use TableCellContent for consistent cell rendering
   - Implement proper loading states

2. **State Management**
   - Use TableFiltersContext for filter/sort state
   - Use TableDensityContext for density controls
   - Keep table state at appropriate level
   - Implement proper error boundaries

3. **Accessibility**
   - Include proper ARIA labels
   - Ensure keyboard navigation
   - Use semantic table markup
   - Support screen readers

4. **Type Safety**
   - Use proper generics with table components
   - Define strict interfaces for data
   - Type column definitions properly
   - Use proper event types

5. **Customization**
   - Create custom cell components for complex data
   - Use theme-aware styling
   - Support dark/light modes
   - Follow MUI design patterns

## Testing

1. **Unit Tests**
```typescript
describe('FeatureTable', () => {
    it('renders with data', () => {
        render(
            <TableFiltersProvider>
                <TableDensityProvider>
                    <FeatureTable />
                </TableDensityProvider>
            </TableFiltersProvider>
        );
    });
});
```

2. **Integration Tests**
- Test sorting functionality
- Test filtering functionality
- Test virtualization
- Test row interactions

3. **E2E Tests**
- Test full table workflows
- Test data loading
- Test error states
- Test accessibility

## Error Handling

1. **Loading States**
```typescript
{isLoading ? (
    <LinearProgress />
) : error ? (
    <ErrorMessage error={error} />
) : (
    <ResizableTable {...props} />
)}
```

2. **Error Boundaries**
```typescript
<ErrorBoundary fallback={<TableErrorFallback />}>
    <FeatureTable />
</ErrorBoundary>
```

## Conclusion

This pattern provides a robust, performant, and maintainable approach to implementing tables and lists. The component hierarchy (BaseTable → ResizableTable) with supporting contexts (TableFilters, TableDensity) provides flexibility while maintaining consistency across the application. 

