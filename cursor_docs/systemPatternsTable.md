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