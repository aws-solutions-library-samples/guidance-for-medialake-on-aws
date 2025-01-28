import React, { useMemo } from 'react';
import { Box, Tooltip } from '@mui/material';
import { format } from 'date-fns';
import { useTranslation } from 'react-i18next';
import { Integration, IntegrationListProps } from './types';
import { BaseTable, TableCellContent } from '@/components/common/table';
import ActionsCell from './cells/ActionsCell';

const IntegrationList = ({
    integrations,
    onEditIntegration,
    onDeleteIntegration,
    activeFilters,
    activeSorting,
    onFilterChange,
    onSortChange,
    onRemoveFilter,
    onRemoveSort,
}: IntegrationListProps) => {
    const { t } = useTranslation();

    // Memoized column definitions following best practices
    const columns = useMemo(
        () => [
            {
                header: t('integrations.columns.nodeName'),
                accessorKey: 'nodeName',
                minSize: 120,
                size: 180,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="primary">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('integrations.columns.environment'),
                accessorKey: 'environment',
                minSize: 120,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('integrations.columns.createdDate'),
                accessorKey: 'createdDate',
                minSize: 150,
                size: 200,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    const formattedDate = format(new Date(dateValue), 'MMM dd, yyyy');
                    const fullDate = format(new Date(dateValue), 'MMM dd, yyyy HH:mm');

                    return (
                        <Tooltip
                            title={fullDate}
                            placement="top"
                            aria-label={`Created on ${fullDate}`}
                        >
                            <Box>
                                <TableCellContent variant="secondary">
                                    {formattedDate}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                header: t('integrations.columns.modifiedDate'),
                accessorKey: 'modifiedDate',
                minSize: 150,
                size: 200,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    const formattedDate = format(new Date(dateValue), 'MMM dd, yyyy');
                    const fullDate = format(new Date(dateValue), 'MMM dd, yyyy HH:mm');

                    return (
                        <Tooltip
                            title={fullDate}
                            placement="top"
                            aria-label={`Modified on ${fullDate}`}
                        >
                            <Box>
                                <TableCellContent variant="secondary">
                                    {formattedDate}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                id: 'actions',
                header: () => (
                    <Box
                        sx={{ width: '100%', textAlign: 'center' }}
                        aria-label={t('integrations.columns.actions')}
                    >
                        {t('integrations.columns.actions')}
                    </Box>
                ),
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: false,
                cell: ({ row }) => (
                    <ActionsCell
                        row={row}
                        onEdit={onEditIntegration}
                        onDelete={onDeleteIntegration}
                    />
                ),
            },
        ],
        [t, onEditIntegration, onDeleteIntegration]
    );

    // Helper function to get unique values for filtering
    const getUniqueValues = (columnId: string, data: Integration[]) => {
        const values = new Set<string>();
        data.forEach(integration => {
            const value = integration[columnId as keyof Integration];
            if (value != null) {
                if (columnId === 'createdDate' || columnId === 'modifiedDate') {
                    values.add(format(new Date(value), 'MMM dd, yyyy'));
                } else {
                    values.add(String(value));
                }
            }
        });
        return Array.from(values).sort();
    };

    // Helper function to format values for display
    const formatValue = (columnId: string, value: string) => {
        if (columnId === 'createdDate' || columnId === 'modifiedDate') {
            return format(new Date(value), 'MMM dd, yyyy');
        }
        return value;
    };

    return (
        <BaseTable
            data={integrations}
            columns={columns}
            activeFilters={activeFilters}
            activeSorting={activeSorting}
            onFilterChange={onFilterChange}
            onSortChange={onSortChange}
            onRemoveFilter={onRemoveFilter}
            onRemoveSort={onRemoveSort}
            getUniqueValues={getUniqueValues}
            formatValue={formatValue}
            searchPlaceholder={t('integrations.search')}
        />
    );
};

IntegrationList.displayName = 'IntegrationList';

export default React.memo(IntegrationList);
