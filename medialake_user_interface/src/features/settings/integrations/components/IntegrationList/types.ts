import { Integration as BaseIntegration } from '../../types/integrations.types';

export interface Integration extends BaseIntegration {
    // Additional fields specific to the list view can be added here
}

export interface IntegrationListProps {
    integrations: Integration[];
    onEditIntegration: (id: string, data: Partial<Integration>) => void;
    onDeleteIntegration: (id: string) => void;
    activeFilters: Array<{ columnId: string; value: string }>;
    activeSorting: Array<{ columnId: string; desc: boolean }>;
    onFilterChange: (columnId: string, value: string) => void;
    onSortChange: (columnId: string, desc: boolean) => void;
    onRemoveFilter: (columnId: string) => void;
    onRemoveSort: (columnId: string) => void;
}
