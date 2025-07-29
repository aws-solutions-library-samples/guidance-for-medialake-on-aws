import React from "react";
import {
  Box,
  Typography,
  Pagination,
  Select,
  MenuItem,
  FormControl,
  SelectChangeEvent,
} from "@mui/material";

interface AssetPaginationProps {
  page: number;
  pageSize: number;
  totalResults: number;
  onPageChange: (event: React.ChangeEvent<unknown>, value: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

const AssetPagination: React.FC<AssetPaginationProps> = ({
  page,
  pageSize,
  totalResults,
  onPageChange,
  onPageSizeChange,
}) => {
  if (totalResults === 0) {
    return null;
  }

  const handlePageSizeChange = (event: SelectChangeEvent<number>) => {
    onPageSizeChange(event.target.value as number);
  };

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        mt: 6,
        mb: 2,
        backgroundColor: "transparent",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Showing {(page - 1) * pageSize + 1} -{" "}
          {Math.min(page * pageSize, totalResults)} of {totalResults} results
        </Typography>
        <FormControl size="small" variant="outlined">
          <Select
            value={pageSize}
            onChange={handlePageSizeChange}
            sx={{
              minWidth: 80,
              height: 32,
              "& .MuiSelect-select": {
                py: 0.5,
                px: 1.5,
              },
            }}
          >
            <MenuItem value={50}>50</MenuItem>
            <MenuItem value={75}>75</MenuItem>
            <MenuItem value={100}>100</MenuItem>
            <MenuItem value={150}>150</MenuItem>
            <MenuItem value={200}>200</MenuItem>
          </Select>
        </FormControl>
      </Box>
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
          "& .MuiPaginationItem-root": {
            borderRadius: "50%",
            minWidth: 40,
            height: 40,
            "&.Mui-selected": {
              fontWeight: "bold",
              backgroundColor: "primary.main",
              color: "white",
              "&:hover": {
                backgroundColor: "primary.dark",
              },
            },
          },
        }}
      />
    </Box>
  );
};

export default AssetPagination;
