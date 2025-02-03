import React from 'react';
import { TableCellContent } from '@/components/common/table';

interface DateCellProps {
    value: string;
}

export const DateCell: React.FC<DateCellProps> = ({ value }) => {
    return (
        <TableCellContent variant="secondary">
            {new Date(value).toLocaleDateString()}
        </TableCellContent>
    );
}; 