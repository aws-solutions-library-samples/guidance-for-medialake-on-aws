import React from 'react';
import { Box, Typography, Pagination } from '@mui/material';

interface AssetPaginationProps {
    page: number;
    pageSize: number;
    totalResults: number;
    onPageChange: (event: React.ChangeEvent<unknown>, value: number) => void;
}

const AssetPagination: React.FC<AssetPaginationProps> = ({
    page,
    pageSize,
    totalResults,
    onPageChange,
}) => {
    if (totalResults <= pageSize) {
        return null;
    }

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mt: 6,
            mb: 2,
            backgroundColor: 'transparent' // the background color of the pagination container/box
        }}>
            <Typography variant="body2" color="text.secondary">
                Showing {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, totalResults)} of {totalResults} results
            </Typography>
            <Pagination
                count={Math.ceil(totalResults / pageSize)}
                page={page}
                onChange={onPageChange}
                color="primary"
                size="medium"
                shape="circular"
                showFirstButton
                showLastButton
                sx={{
                    '& .MuiPaginationItem-root': {
                        borderRadius: '50%',
                        minWidth: 40,
                        height: 40,
                        '&.Mui-selected': {
                            fontWeight: 'bold',
                            backgroundColor: 'primary.main',
                            color: 'white', //the color of the text for selected pagination item
                            '&:hover': {
                                backgroundColor: 'primary.dark',
                            }
                        }
                    }
                }}
            />
        </Box>
    );
};

export default AssetPagination;
