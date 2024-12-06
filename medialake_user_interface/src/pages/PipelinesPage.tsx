import React, { useMemo, useState, useEffect } from 'react';
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
    Chip,
    IconButton,
    useTheme,
    Button,
    CircularProgress,
    TableSortLabel,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    alpha,
    TextField,
    Stack,
    Snackbar,
    Alert,
} from '@mui/material';
import {
    Edit as EditIcon,
    Add as AddIcon,
    RocketLaunch as RocketLaunchIcon,
} from '@mui/icons-material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getPaginationRowModel,
    flexRender,
    ColumnDef,
} from '@tanstack/react-table';
import { useNavigate } from 'react-router-dom';
import { PipelineResponse, CreatePipelineRequest, Pipeline } from '@/api/types/pipeline.types';
import { usePipeline } from '../api/hooks/usePipelines';
import { useMediaQuery } from '@mui/material';
import Tooltip from '@mui/material/Tooltip';
import { useCreatePipeline } from '../api/hooks/usePipelines';
import { useTranslation } from 'react-i18next';

const PAGE_SIZE = 20;

const pipelineTypes = {
    INGEST: 'Ingest Triggered',
    MANUAL: 'Manually Triggered',
    ANALYSIS: 'Analysis Triggered',
} as const;



const PipelinesPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();
    const isSmallScreen = useMediaQuery(theme.breakpoints.down('lg'));
    const createPipeline = useCreatePipeline();
    const [pipelines, setPipelines] = useState<Pipeline[]>([]);
    const [isCreatingPipeline, setIsCreatingPipeline] = useState(false);

    const [globalSearch, setGlobalSearch] = useState('');


    const [filters, setFilters] = useState({
        type: '',
        name: '',
        system: '',
        sortBy: 'createdAt',
        sortOrder: 'desc' as 'asc' | 'desc'
    });
    const { data, isLoading, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } = usePipeline(PAGE_SIZE, {
        status: filters.type || undefined,
        sortBy: filters.sortBy,
        sortOrder: filters.sortOrder
    });

    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error',
    });

    const handleCloseSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };


    useEffect(() => {
        setGlobalSearch(filters.name);
    }, [filters.name, setGlobalSearch]);

    useEffect(() => {
        if (data && data.pages) {
            const allPipelines = data.pages.flatMap(page => page.data.s);
            setPipelines(allPipelines);
        }
    }, [data]);


    const getChipColor = (type: string) => {
        switch (type.toLowerCase()) {
            case 'Ingest Triggered':
                return theme.palette.primary.main;
            case 'Manually Triggered':
                return theme.palette.secondary.main;
            case 'Analysis Triggered':
                return theme.palette.success.main;
            default:
                return theme.palette.grey[500];
        }
    };


    const columns = useMemo<ColumnDef<Pipeline>[]>(
        () => [
            {
                header: 'Name',
                accessorKey: 'name',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ fontWeight: 500, color: theme.palette.primary.main }}>
                        {getValue() as string}
                    </Typography>
                ),
            },
            {
                header: 'Creation Date',
                accessorKey: 'createdAt',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        {new Date(getValue() as string).toLocaleString()}
                    </Typography>
                ),
            },
            {
                header: 'System',
                accessorKey: 'system',
                cell: ({ getValue }) => {
                    const isSystem = getValue() as boolean;
                    return (
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                            {isSystem ? 'Yes' : 'No'}
                        </Typography>
                    );
                },
            },
            {
                header: 'Type',
                accessorKey: 'type',
                cell: ({ getValue }) => {
                    const type = getValue() as string;
                    const color = getChipColor(type);
                    return (
                        <Chip
                            label={type}
                            size="small"
                            sx={{
                                backgroundColor: alpha(color, 0.1),
                                color: color,
                                fontWeight: 600,
                                borderRadius: '6px',
                                height: '24px',
                                '& .MuiChip-label': {
                                    px: 1.5,
                                },
                            }}
                        />
                    );
                },
            },
            {
                header: 'Actions',
                id: 'actions',
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        {!row.original.system && ( // Only render if system is false or undefined
                            <IconButton
                                size="small"
                                color="primary"
                                onClick={() => handleEdit(row.original.id)}
                                sx={{
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                    },
                                }}
                            >
                                <EditIcon fontSize="small" />
                            </IconButton>
                        )}
                    </Box>
                ),
            },
        ],
        [theme]
    );

    const table = useReactTable({
        data: pipelines,
        columns,
        state: { globalFilter: globalSearch },
        onGlobalFilterChange: setGlobalSearch,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        initialState: {
            pagination: {
                pageSize: PAGE_SIZE,
            },
        },

    });

    const handleEdit = (id: string) => {
        navigate(`/pipelines/${id}`);
    };

    const handleCreatePipeline = async (pipelineData: CreatePipelineRequest) => {
        setIsCreatingPipeline(true);
        try {
            const response: PipelineResponse = await createPipeline.mutateAsync(pipelineData);
            console.log('Pipeline creation response:', response);

            if (response.status === "409") {
                const errorMessage = `${response.message}: ${response.data.error || ''}`;
                setSnackbar({
                    open: true,
                    message: errorMessage,
                    severity: 'error'
                });
            } else if (response.status === "200") {
                setSnackbar({
                    open: true,
                    message: 'Pipeline created successfully',
                    severity: 'success'
                });
                refetch();
            } else {
                // Handle other status codes, including 500
                setSnackbar({
                    open: true,
                    message: response.message || 'Unknown response from server',
                    severity: 'error'
                });
            }
        } catch (err: any) {
            console.error('Pipeline creation error:', err);
            let errorMessage = 'Failed to create pipeline. Please try again.';

            if (err.response) {
                console.log('Error response:', err.response);
                const { status, data } = err.response;
                if (status === 500 && data.body) {
                    // Handle the specific 500 error response
                    const bodyData = typeof data.body === 'string' ? JSON.parse(data.body) : data.body;
                    errorMessage = bodyData.message || 'An unknown error occurred';
                } else if (status === 409) {
                    errorMessage = `${data.message}: ${data.data?.error || ''}`;
                } else if (data.message) {
                    errorMessage = data.message;
                }
            } else if (err.message) {
                errorMessage = err.message;
            }

            setSnackbar({
                open: true,
                message: errorMessage,
                severity: 'error'
            });
        } finally {
            setIsCreatingPipeline(false);
        }
    };




    const handleAddNew = () => {
        navigate('/pipeline');
    };

    const hardcodedPipelineData: CreatePipelineRequest = {
        "name": "image-pipeline",
        "type": "Ingest Triggered",
        "system": true,
        "definition": {
            "nodes": [
                {
                    "id": "dndnode_0",
                    "type": "custom",
                    "position": {
                        "x": 154,
                        "y": 273
                    },
                    "data": {
                        "id": "03c23094-d405-4aa7-a243-5a7a8f71d4a5",
                        "type": "imageasset",
                        "label": "Image Asset",
                        "icon": {
                            "key": null,
                            "ref": null,
                            "props": {
                                "size": 20
                            },
                            "_owner": null
                        },
                        "inputTypes": [
                            "image"
                        ],
                        "outputTypes": [
                            "image"
                        ]
                    },
                    "width": 60,
                    "height": 55,
                    "positionAbsolute": {
                        "x": 154,
                        "y": 273
                    }
                },
                {
                    "id": "dndnode_2",
                    "type": "custom",
                    "position": {
                        "x": 187,
                        "y": 380
                    },
                    "data": {
                        "id": "57207390-4b93-4c07-a1cc-e4733710b842",
                        "type": "imagemetadata",
                        "label": "Image Metadata",
                        "icon": {
                            "key": null,
                            "ref": null,
                            "props": {
                                "size": 20
                            },
                            "_owner": null
                        },
                        "inputTypes": [
                            "image"
                        ],
                        "outputTypes": [
                            "image"
                        ]
                    },
                    "width": 60,
                    "height": 55,
                    "positionAbsolute": {
                        "x": 187,
                        "y": 380
                    }
                },
                {
                    "id": "dndnode_3",
                    "type": "custom",
                    "position": {
                        "x": 196,
                        "y": 467
                    },
                    "data": {
                        "id": "9361ac53-13e9-4358-adde-3e4cd023954f",
                        "type": "imageproxy",
                        "label": "Image Proxy",
                        "icon": {
                            "key": null,
                            "ref": null,
                            "props": {
                                "size": 20
                            },
                            "_owner": null
                        },
                        "inputTypes": [
                            "image"
                        ],
                        "outputTypes": [
                            "image"
                        ]
                    },
                    "width": 60,
                    "height": 55,
                    "selected": true,
                    "positionAbsolute": {
                        "x": 196,
                        "y": 467
                    },
                    "dragging": false
                },
                {
                    "id": "dndnode_4",
                    "type": "custom",
                    "position": {
                        "x": 216,
                        "y": 582
                    },
                    "data": {
                        "id": "6773f9ef-2161-42c1-9485-11ef1c23f3b4",
                        "type": "imagethumbnail",
                        "label": "Image Thumbnail",
                        "icon": {
                            "key": null,
                            "ref": null,
                            "props": {
                                "size": 20
                            },
                            "_owner": null
                        },
                        "inputTypes": [
                            "image"
                        ],
                        "outputTypes": [
                            "image"
                        ]
                    },
                    "width": 60,
                    "height": 55,
                    "positionAbsolute": {
                        "x": 216,
                        "y": 582
                    }
                },
                {
                    "id": "dndnode_5",
                    "type": "custom",
                    "position": {
                        "x": 317.4421648673655,
                        "y": 644.8991829079268
                    },
                    "data": {
                        "id": "14a670a0-967d-452c-9e0e-cf2f9e92d634",
                        "type": "medialake",
                        "label": "MediaLake",
                        "icon": {
                            "key": null,
                            "ref": null,
                            "props": {
                                "size": 20
                            },
                            "_owner": null
                        },
                        "inputTypes": [
                            "video",
                            "audio",
                            "image",
                            "metadata"
                        ],
                        "outputTypes": []
                    },
                    "width": 60,
                    "height": 55,
                    "positionAbsolute": {
                        "x": 317.4421648673655,
                        "y": 644.8991829079268
                    }
                }
            ],
            "edges": [
                {
                    "source": "dndnode_0",
                    "sourceHandle": null,
                    "target": "dndnode_2",
                    "targetHandle": null,
                    "type": "custom",
                    "data": {
                        "text": "to Image Metadata"
                    },
                    "id": "reactflow__edge-dndnode_0-dndnode_2"
                },
                {
                    "source": "dndnode_2",
                    "sourceHandle": null,
                    "target": "dndnode_3",
                    "targetHandle": null,
                    "type": "custom",
                    "data": {
                        "text": "to Image Proxy"
                    },
                    "id": "reactflow__edge-dndnode_2-dndnode_3"
                },
                {
                    "source": "dndnode_3",
                    "sourceHandle": null,
                    "target": "dndnode_4",
                    "targetHandle": null,
                    "type": "custom",
                    "data": {
                        "text": "to Image Thumbnail"
                    },
                    "id": "reactflow__edge-dndnode_3-dndnode_4"
                },
                {
                    "source": "dndnode_4",
                    "sourceHandle": null,
                    "target": "dndnode_5",
                    "targetHandle": null,
                    "type": "custom",
                    "data": {
                        "text": "to MediaLake"
                    },
                    "id": "reactflow__edge-dndnode_4-dndnode_5"
                }
            ],
            "viewport": {
                "x": -130.31858746589876,
                "y": -141.11180335713357,
                "zoom": 0.9460576467255969
            }
        }
    };


    return (
        <Box sx={{ px: 4, py: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                        <Typography variant="h4" sx={{
                            fontWeight: 700,
                            mb: 1,
                            background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                            backgroundClip: 'text',
                            WebkitBackgroundClip: 'text',
                            color: 'transparent',
                        }}>
                            Pipelines
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            Manage and monitor your media pipelines
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                        <Stack direction="row" spacing={2}>
                            <Tooltip title={isCreatingPipeline ? "Deploying Image Pipeline" : "Deploy Image Pipeline"}>
                                {isSmallScreen ? (
                                    <Button
                                        onClick={() => handleCreatePipeline(hardcodedPipelineData)}
                                        disabled={isCreatingPipeline}
                                        sx={{
                                            minWidth: 0,
                                            p: 1,
                                            borderRadius: '50%',
                                            color: theme.palette.secondary.contrastText,
                                            backgroundColor: theme.palette.secondary.main,
                                            '&:hover': {
                                                backgroundColor: theme.palette.secondary.dark,
                                            },
                                        }}
                                    >
                                        {isCreatingPipeline ? (
                                            <CircularProgress size={24} color="inherit" />
                                        ) : (
                                            <RocketLaunchIcon />
                                        )}
                                    </Button>
                                ) : (
                                    <Button
                                        variant="contained"
                                        color="secondary"
                                        startIcon={isCreatingPipeline ? <CircularProgress size={24} color="inherit" /> : <RocketLaunchIcon />}
                                        onClick={() => handleCreatePipeline(hardcodedPipelineData)}
                                        disabled={isCreatingPipeline}
                                        sx={{
                                            borderRadius: '8px',
                                            textTransform: 'none',
                                            px: 3,
                                        }}
                                    >
                                        {isCreatingPipeline ? 'Deploying Image Pipeline' : 'Deploy Image Pipeline'}
                                    </Button>
                                )}
                            </Tooltip>

                            <Tooltip title="Add New Pipeline">
                                {isSmallScreen ? (
                                    <Button
                                        onClick={handleAddNew}
                                        sx={{
                                            minWidth: 0,
                                            p: 1,
                                            borderRadius: '50%',
                                            color: theme.palette.primary.contrastText,
                                            backgroundColor: theme.palette.primary.main,
                                            '&:hover': {
                                                backgroundColor: theme.palette.primary.dark,
                                            },
                                        }}
                                    >
                                        <AddIcon />
                                    </Button>
                                ) : (
                                    <Button
                                        variant="contained"
                                        color="primary"
                                        startIcon={<AddIcon />}
                                        onClick={handleAddNew}
                                        sx={{
                                            borderRadius: '8px',
                                            textTransform: 'none',
                                            px: 3,
                                        }}
                                    >
                                        Add New Pipeline
                                    </Button>
                                )}
                            </Tooltip>


                        </Stack>
                    </Box>

                </Box>
                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                    <TextField
                        size="small"
                        placeholder="Filter by name"
                        value={filters.name}
                        onChange={(e) => setFilters(prev => ({ ...prev, name: e.target.value }))}
                        sx={{
                            minWidth: 200,
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '8px',
                            }
                        }}
                    />
                    <FormControl size="small" sx={{
                        minWidth: 120,
                        '& .MuiOutlinedInput-root': {
                            borderRadius: '8px',
                        }
                    }}>
                        <InputLabel>Type</InputLabel>
                        <Select
                            value={filters.type}
                            label="Type"
                            onChange={(e) => setFilters(prev => ({ ...prev, type: e.target.value }))}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value={pipelineTypes.INGEST}>Ingest Triggered</MenuItem>
                            <MenuItem value={pipelineTypes.MANUAL}>Manually Triggered</MenuItem>
                            <MenuItem value={pipelineTypes.ANALYSIS}>Analysis Triggered</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{
                        minWidth: 120,
                        '& .MuiOutlinedInput-root': {
                            borderRadius: '8px',
                        }
                    }}>
                        <InputLabel>System</InputLabel>
                        <Select
                            value={filters.system}
                            label="System"
                            onChange={(e) => setFilters(prev => ({ ...prev, system: e.target.value }))}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="true">Yes</MenuItem>
                            <MenuItem value="false">No</MenuItem>
                        </Select>
                    </FormControl>
                </Box>
            </Box>

            <Paper elevation={0} sx={{
                flex: 1,
                borderRadius: '12px',
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                overflow: 'hidden',
                backgroundColor: theme.palette.background.paper,
            }}>
                <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)' }}>
                    <Table stickyHeader>
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <TableCell
                                            key={header.id}
                                            sx={{
                                                backgroundColor: theme.palette.background.paper,
                                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                py: 2,
                                            }}
                                        >
                                            {header.isPlaceholder ? null : (
                                                <TableSortLabel
                                                    active={header.column.getIsSorted() !== false}
                                                    direction={header.column.getIsSorted() === 'desc' ? 'desc' : 'asc'}
                                                    onClick={header.column.getToggleSortingHandler()}
                                                    sx={{
                                                        fontWeight: 600,
                                                        color: theme.palette.text.primary,
                                                    }}
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
                            {isLoading || !data ? (
                                <TableRow>
                                    <TableCell colSpan={5} align="center">
                                        <CircularProgress />
                                    </TableCell>
                                </TableRow>
                            ) : table.getRowModel().rows.map(row => (
                                <TableRow
                                    key={row.id}
                                    sx={{
                                        '&:hover': {
                                            backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                        },
                                        transition: 'background-color 0.2s ease',
                                    }}
                                >
                                    {row.getVisibleCells().map(cell => (
                                        <TableCell
                                            key={cell.id}
                                            sx={{
                                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                py: 2,
                                            }}
                                        >
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                            {!isLoading && data && table.getRowModel().rows.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={5} align="center">
                                        No pipelines found
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>

                    </Table>
                </TableContainer>

                <Box sx={{
                    p: 2,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}>
                    {hasNextPage && (
                        <Button
                            onClick={() => fetchNextPage()}
                            disabled={!hasNextPage || isFetchingNextPage}
                            sx={{
                                textTransform: 'none',
                                borderRadius: '8px',
                                color: theme.palette.text.secondary,
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                },
                            }}
                        >
                            {isFetchingNextPage
                                ? t('common.loading')
                                : t('common.loadMore')}
                        </Button>
                    )}
                </Box>
            </Paper>
            <Snackbar
                open={snackbar.open}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                autoHideDuration={6000}
                onClose={handleCloseSnackbar}>
                <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
                    {snackbar.message}
                </Alert>
            </Snackbar>

        </Box>
    );
};

export default PipelinesPage;
