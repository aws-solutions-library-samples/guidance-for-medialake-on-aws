import React from 'react';
import {
  Box,
  Pagination,
  FormControl,
  Select,
  MenuItem,
  Typography,
  useTheme,
  SelectChangeEvent,
  alpha
} from '@mui/material';

interface AssetPaginationProps {
  page: number;
  pageSize: number;
  totalResults: number;
  onPageChange: (event: React.ChangeEvent<unknown>, page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

const AssetPagination: React.FC<AssetPaginationProps> = ({
  page,
  pageSize,
  totalResults,
  onPageChange,
  onPageSizeChange
}) => {
  const theme = useTheme();
  const totalPages = Math.ceil(totalResults / pageSize);
  
  const handlePageSizeChange = (event: SelectChangeEvent<number>) => {
    onPageSizeChange(Number(event.target.value));
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mt: 4,
        pt: 2,
        borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary" mr={2}>
          Items per page:
        </Typography>
        <FormControl size="small" variant="outlined">
          <Select
            value={pageSize}
            onChange={handlePageSizeChange}
            sx={{
              minWidth: 80,
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: alpha(theme.palette.divider, 0.2),
              },
            }}
          >
            <MenuItem value={10}>10</MenuItem>
            <MenuItem value={25}>25</MenuItem>
            <MenuItem value={50}>50</MenuItem>
            <MenuItem value={100}>100</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary" mr={2}>
          {`${(page - 1) * pageSize + 1}-${Math.min(
            page * pageSize,
            totalResults
          )} of ${totalResults}`}
        </Typography>
        <Pagination
          count={totalPages}
          page={page}
          onChange={onPageChange}
          color="primary"
          shape="rounded"
          size="medium"
          showFirstButton
          showLastButton
        />
      </Box>
    </Box>
  );
};

export default AssetPagination;
