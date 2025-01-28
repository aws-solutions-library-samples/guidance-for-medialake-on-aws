export interface Integration {
    id: string;
    nodeName: string;
    environment: string;
    createdDate: string;
    modifiedDate: string;
}

export interface IntegrationListProps {
    integrations: Integration[];
    onEditIntegration: (integration: Integration) => void;
    onDeleteIntegration: (id: string) => void;
    activeFilters: { columnId: string; value: string }[];
    activeSorting: { columnId: string; desc: boolean }[];
    onFilterChange: (columnId: string, value: string) => void;
    onSortChange: (columnId: string, desc?: boolean) => void;
    onRemoveFilter: (columnId: string) => void;
    onRemoveSort: (columnId: string) => void;
}
