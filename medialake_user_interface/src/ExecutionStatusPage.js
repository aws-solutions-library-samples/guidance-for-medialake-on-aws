import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Typography,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TableSortLabel,
    TextField,
    Chip,
    Button,
    CircularProgress,
    IconButton,
    Tooltip,
    Menu,
    MenuItem,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoIcon from '@mui/icons-material/Info';
import { useReactTable, getCoreRowModel, getFilteredRowModel, getSortedRowModel, getPaginationRowModel, flexRender } from '@tanstack/react-table';

// Mock API call - replace this with your actual API call
const fetchExecutionStatus = async () => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return [
        { id: 1, pipelineName: 'Video Transcoding', status: 'Completed', startTime: '2023-05-15T10:00:00Z', endTime: '2023-05-15T10:30:00Z' },
        { id: 2, pipelineName: 'Image Processing', status: 'Running', startTime: '2023-05-15T11:00:00Z', endTime: null },
        { id: 3, pipelineName: 'Audio Analysis', status: 'Failed', startTime: '2023-05-15T09:00:00Z', endTime: '2023-05-15T09:15:00Z' },
        // Add more mock data as needed
    ];
};

const retryExecution = async (executionId, retryFrom) => {
    // Make the API call to retry the execution
    // Replace this with your actual API call
    console.log(`Retrying execution ${executionId} from ${retryFrom}`);
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulating API call
};

const ExecutionStatusPage = () => {
    const navigate = useNavigate();
    const { data: executionData, isLoading, error, refetch } = useQuery({
        queryKey: ['executionStatus'],
        queryFn: fetchExecutionStatus,
    });

    const [anchorEl, setAnchorEl] = useState(null);
    const [selectedExecutionId, setSelectedExecutionId] = useState(null);

    const handleRetryClick = (event, executionId) => {
        setAnchorEl(event.currentTarget);
        setSelectedExecutionId(executionId);
    };

    const handleRetryClose = () => {
        setAnchorEl(null);
    };

    const handleRetryOption = async (retryFrom) => {
        try {
            await retryExecution(selectedExecutionId, retryFrom);
            refetch();
        } catch (error) {
            console.error('Failed to retry execution:', error);
        }
        handleRetryClose();
    };

    const handleDetails = (executionId) => {
        navigate(`/executions/${executionId}`);
    };

    const columns = useMemo(
        () => [
            {
                header: 'Pipeline Name',
                accessorKey: 'pipelineName',
            },
            {
                header: 'Status',
                accessorKey: 'status',
                cell: ({ getValue }) => (
                    <Chip
                        label={getValue()}
                        color={getValue() === 'Completed' ? 'success' : getValue() === 'Running' ? 'primary' : 'error'}
                        size="small"
                    />
                ),
            },
            {
                header: 'Start Time',
                accessorKey: 'startTime',
                cell: ({ getValue }) => new Date(getValue()).toLocaleString(),
            },
            {
                header: 'End Time',
                accessorKey: 'endTime',
                cell: ({ getValue }) => getValue() ? new Date(getValue()).toLocaleString() : 'N/A',
            },
            {
                header: 'Actions',
                cell: ({ row }) => (
                    <>
                        {row.original.status === 'Failed' && (
                            <Tooltip title="Retry Execution">
                                <IconButton
                                    onClick={(event) => handleRetryClick(event, row.original.id)}
                                    size="small"
                                >
                                    <RefreshIcon />
                                </IconButton>
                            </Tooltip>
                        )}
                        <Tooltip title="Execution Details">
                            <IconButton
                                onClick={() => handleDetails(row.original.id)}
                                size="small"
                            >
                                <InfoIcon />
                            </IconButton>
                        </Tooltip>
                    </>
                ),
            },
        ],
        []
    );

    const table = useReactTable({
        data: executionData || [],
        columns,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
    });

    if (isLoading) return <CircularProgress />;
    if (error) return <Typography color="error">Error loading execution status data</Typography>;

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Pipeline Execution Status
                </Typography>
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<RefreshIcon />}
                    onClick={() => refetch()}
                >
                    Refresh
                </Button>
            </Box>
            <Box sx={{ width: '80%', margin: '0 auto' }}>
                <TextField
                    label="Filter by Pipeline Name"
                    variant="outlined"
                    fullWidth
                    onChange={e => table.getColumn('pipelineName').setFilterValue(e.target.value)}
                    sx={{ mb: 2 }}
                />
                <TableContainer component={Paper}>
                    <Table sx={{ minWidth: 650 }} aria-label="execution status table">
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <TableCell key={header.id}>
                                            {header.isPlaceholder ? null : (
                                                <TableSortLabel
                                                    active={header.column.getIsSorted() !== false}
                                                    direction={header.column.getIsSorted() === 'desc' ? 'desc' : 'asc'}
                                                    onClick={header.column.getToggleSortingHandler()}
                                                >
                                                    {flexRender(
                                                        header.column.columnDef.header,
                                                        header.getContext()
                                                    )}
                                                </TableSortLabel>
                                            )}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableHead>
                        <TableBody>
                            {table.getRowModel().rows.map(row => (
                                <TableRow key={row.id}>
                                    {row.getVisibleCells().map(cell => (
                                        <TableCell key={cell.id}>
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Button onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
                        <Button onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
                    </Box>
                    <Typography>
                        Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                    </Typography>
                    <select
                        value={table.getState().pagination.pageSize}
                        onChange={e => table.setPageSize(Number(e.target.value))}
                    >
                        {[10, 25, 50].map(pageSize => (
                            <option key={pageSize} value={pageSize}>
                                Show {pageSize}
                            </option>
                        ))}
                    </select>
                </Box>
            </Box>
            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleRetryClose}
            >
                <MenuItem onClick={() => handleRetryOption('failure')}>Retry from failure</MenuItem>
                <MenuItem onClick={() => handleRetryOption('start')}>Retry from start</MenuItem>
            </Menu>
        </Box>
    );
};

export default ExecutionStatusPage;
