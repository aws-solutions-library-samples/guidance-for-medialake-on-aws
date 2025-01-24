import React, { useMemo } from 'react';
import { Box, Tooltip, useTheme, alpha } from '@mui/material';
import { format } from 'date-fns';
import { Environment } from '@/types/environment';
import { BaseTable, TableCellContent } from '@/components/common/table';
import { ActionsCell } from './cells/ActionsCell';
import { StatusCell } from './cells/StatusCell';
import { useTranslation } from 'react-i18next';

interface EnvironmentListProps {
    environments: Environment[];
    onEditEnvironment: (environment: Environment) => void;
    onDeleteEnvironment: (id: string) => void;
    activeFilters: { columnId: string; value: string }[];
    activeSorting: { columnId: string; desc: boolean }[];
    onFilterChange: (columnId: string, value: string) => void;
    onSortChange: (columnId: string, desc: boolean) => void;
    onRemoveFilter: (columnId: string) => void;
    onRemoveSort: (columnId: string) => void;
}

const EnvironmentList: React.FC<EnvironmentListProps> = ({
    environments,
    onEditEnvironment,
    onDeleteEnvironment,
    activeFilters,
    activeSorting,
    onFilterChange,
    onSortChange,
    onRemoveFilter,
    onRemoveSort,
}) => {
    const { t } = useTranslation();
    const theme = useTheme();

    const columns = useMemo(
        () => [
            {
                header: t('settings.environments.columns.name'),
                accessorKey: 'name',
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
                header: t('settings.environments.columns.region'),
                accessorKey: 'region',
                minSize: 100,
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
                header: t('settings.environments.columns.status'),
                accessorKey: 'status',
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <StatusCell status={getValue() as 'active' | 'disabled'} />
                ),
            },
            {
                header: t('settings.environments.columns.team'),
                accessorFn: (row) => row.tags?.team,
                id: 'team',
                minSize: 120,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string || '-'}
                    </TableCellContent>
                ),
            },
            {
                header: t('settings.environments.columns.costCenter'),
                accessorFn: (row) => row.tags?.['cost-center'],
                id: 'cost-center',
                minSize: 120,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string || '-'}
                    </TableCellContent>
                ),
            },
            {
                header: t('settings.environments.columns.createdAt'),
                accessorKey: 'created_at',
                minSize: 150,
                size: 200,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    return (
                        <Tooltip title={format(new Date(dateValue), 'MMM dd, yyyy HH:mm')} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {format(new Date(dateValue), 'MMM dd, yyyy')}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                header: t('settings.environments.columns.updatedAt'),
                accessorKey: 'updated_at',
                minSize: 150,
                size: 200,
                enableResizing: true,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    return (
                        <Tooltip title={format(new Date(dateValue), 'MMM dd, yyyy HH:mm')} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {format(new Date(dateValue), 'MMM dd, yyyy')}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                id: 'actions',
                header: () => (
                    <Box sx={{ width: '100%', textAlign: 'center' }}>
                        {t('settings.environments.columns.actions')}
                    </Box>
                ),
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: false,
                cell: ({ row }) => (
                    <ActionsCell
                        environment={row.original}
                        onEdit={onEditEnvironment}
                    />
                ),
            },
        ],
        [t, onEditEnvironment]
    );

    const getUniqueValues = (columnId: string, data: Environment[]) => {
        const values = new Set<string>();
        data.forEach(env => {
            let value: any;
            if (columnId === 'team' || columnId === 'cost-center') {
                value = env.tags?.[columnId];
            } else {
                value = env[columnId as keyof Environment];
            }

            if (value != null) {
                if (columnId === 'created_at' || columnId === 'updated_at') {
                    values.add(format(new Date(value), 'MMM dd, yyyy'));
                } else {
                    values.add(String(value));
                }
            }
        });
        return Array.from(values).sort();
    };

    const formatValue = (columnId: string, value: string) => {
        if (columnId === 'status') {
            return value === 'active' ? t('settings.environments.status.active') : t('settings.environments.status.disabled');
        }
        return value;
    };

    return (
        <BaseTable
            data={environments}
            columns={columns}
            activeFilters={activeFilters}
            activeSorting={activeSorting}
            onFilterChange={onFilterChange}
            onSortChange={onSortChange}
            onRemoveFilter={onRemoveFilter}
            onRemoveSort={onRemoveSort}
            getUniqueValues={getUniqueValues}
            formatValue={formatValue}
            searchPlaceholder={t('settings.environments.search')}
        />
    );
};

export default React.memo(EnvironmentList);
