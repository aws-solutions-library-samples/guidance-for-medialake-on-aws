import { useMemo } from 'react';
import { createColumnHelper } from '@tanstack/react-table';
import { Environment } from '@/types/environment';
import { format } from 'date-fns';
import { Box, Tooltip } from '@mui/material';
import { TableCellContent } from '@/components/common/table';

const columnHelper = createColumnHelper<Environment>();

export const useEnvironmentColumns = () => {
    return useMemo(
        () => [
            columnHelper.accessor('name', {
                header: 'Name',
                size: 200,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="primary">
                        {getValue()}
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('region', {
                header: 'Region',
                size: 150,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue()}
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('status', {
                header: 'Status',
                size: 150,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue()}
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('created_at', {
                header: 'Created At',
                size: 200,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue();
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
            }),
            columnHelper.accessor('updated_at', {
                header: 'Updated At',
                size: 200,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue();
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
            }),
        ],
        []
    );
};