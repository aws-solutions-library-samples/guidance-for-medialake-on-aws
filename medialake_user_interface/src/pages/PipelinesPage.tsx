import React, { useState, useMemo } from 'react';
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
    IconButton,
    Tooltip,
    Button,
    Snackbar,
    Alert
} from '@mui/material';
import { CircularProgress } from '@mui/material';

import EditIcon from '@mui/icons-material/Edit';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import AddIcon from '@mui/icons-material/Add';
import { useNavigate } from 'react-router-dom';
import { PipelineResponse, CreatePipelineRequest } from '@/api/types/api.types';
import { useCreatePipeline } from '../api/hooks/usePipelines';


const pipelineTypes = {
    INGEST: 'Ingest Triggered',
    MANUAL: 'Manually Triggered',
    ANALYSIS: 'Analysis Triggered',
} as const;

type PipelineType = typeof pipelineTypes[keyof typeof pipelineTypes];

interface Pipeline {
    id: number;
    name: string;
    creationDate: string;
    type: PipelineType;
}

const mockPipelines: Pipeline[] = [
    { id: 1, name: 'Default Image Pipeline', creationDate: '2024-11-27', type: pipelineTypes.INGEST },
    { id: 2, name: 'Video Analysis', creationDate: '2023-05-01', type: pipelineTypes.INGEST },
    { id: 3, name: 'Image Analysis', creationDate: '2023-05-02', type: pipelineTypes.INGEST },
    { id: 4, name: 'Audio Analysis', creationDate: '2023-05-03', type: pipelineTypes.INGEST },
    { id: 5, name: 'Metadata Extraction', creationDate: '2023-05-04', type: pipelineTypes.MANUAL },
    { id: 6, name: 'Content Moderation', creationDate: '2023-05-05', type: pipelineTypes.MANUAL },
];

interface Node {
    id: string;
    type: string;
    position: { x: number; y: number };
    data: {
        label: string;
        icon: string;
        inputTypes: string[];
        outputTypes: string[];
    };
}

interface Edge {
    id: string;
    source: string;
    target: string;
    type: string;
    data: {
        text: string;
    };
}

interface PipelineData extends Pipeline {
    nodes: Node[];
    edges: Edge[];
}

// Simulated API call to fetch pipeline data
const fetchPipelineData = (id: number): Promise<PipelineData | null> => {
    return new Promise((resolve) => {
        setTimeout(() => {
            const pipeline = mockPipelines.find(p => p.id === id);
            if (pipeline) {
                // Simulate different data for each pipeline
                const nodes: Node[] = [
                    { id: '1', type: 'custom', position: { x: 0, y: 0 }, data: { label: 'Input', icon: 'FaFileVideo', inputTypes: ['video'], outputTypes: ['video'] } },
                    { id: '2', type: 'custom', position: { x: 200, y: 0 }, data: { label: pipeline.name, icon: 'FaVideo', inputTypes: ['video'], outputTypes: ['video'] } },
                    { id: '3', type: 'custom', position: { x: 400, y: 0 }, data: { label: 'Output', icon: 'FaDatabase', inputTypes: ['video'], outputTypes: [] } },
                ];
                const edges: Edge[] = [
                    { id: 'e1-2', source: '1', target: '2', type: 'custom', data: { text: 'Process' } },
                    { id: 'e2-3', source: '2', target: '3', type: 'custom', data: { text: 'Store' } },
                ];
                resolve({ ...pipeline, nodes, edges });
            } else {
                resolve(null);
            }
        }, 500);
    });
};

const PipelinesPage: React.FC = () => {
    const [pipelines, setPipelines] = useState<Pipeline[]>(mockPipelines);
    const [sortColumn, setSortColumn] = useState<keyof Pipeline>('name');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
    const [filterText, setFilterText] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isCreatingPipeline, setIsCreatingPipeline] = useState(false);


    const createPipeline = useCreatePipeline();
    const navigate = useNavigate();

    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
        open: false,
        message: '',
        severity: 'success',
    });

    const handleCloseSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    const handleEdit = (id: number) => {
        navigate(`/pipelines/${id}`);
    };

    const hardcodedPipelineData: CreatePipelineRequest = {
        "name": "image-pipeline",
        "type": "s3",
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
            } else {
                // Changed from 'warning' to 'error' for unknown responses
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
                if (status === 409) {
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

    const handleSort = (column: keyof Pipeline) => {
        if (column === sortColumn) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(column);
            setSortOrder('asc');
        }
    };

    const filteredPipelines = useMemo(() => {
        return pipelines.filter((pipeline) =>
            pipeline.name.toLowerCase().includes(filterText.toLowerCase())
        );
    }, [pipelines, filterText]);

    const sortedPipelines = useMemo(() => {
        return [...filteredPipelines].sort((a, b) => {
            const order = sortOrder === 'asc' ? 1 : -1;
            if (a[sortColumn] < b[sortColumn]) {
                return -1 * order;
            }
            if (a[sortColumn] > b[sortColumn]) {
                return 1 * order;
            }
            return 0;
        });
    }, [filteredPipelines, sortColumn, sortOrder]);

    const getChipColor = (type: PipelineType) => {
        switch (type) {
            case pipelineTypes.INGEST:
                return 'primary';
            case pipelineTypes.MANUAL:
                return 'secondary';
            case pipelineTypes.ANALYSIS:
                return 'success';
            default:
                return 'default';
        }
    };

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Pipelines
                </Typography>
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<AddIcon />}
                    onClick={handleAddNew}
                >
                    Add New Pipeline
                </Button>
            </Box>
            <Box sx={{ width: '80%', margin: '0 auto' }}>
                <TextField
                    label="Filter Pipelines"
                    variant="outlined"
                    fullWidth
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    sx={{ mb: 2 }}
                />
                <TableContainer component={Paper}>
                    <Table sx={{ minWidth: 650 }} aria-label="pipelines table">
                        <TableHead>
                            <TableRow>
                                <TableCell>
                                    <TableSortLabel
                                        active={sortColumn === 'name'}
                                        direction={sortColumn === 'name' ? sortOrder : 'asc'}
                                        onClick={() => handleSort('name')}
                                    >
                                        Name
                                    </TableSortLabel>
                                </TableCell>
                                <TableCell align="right">
                                    <TableSortLabel
                                        active={sortColumn === 'creationDate'}
                                        direction={sortColumn === 'creationDate' ? sortOrder : 'asc'}
                                        onClick={() => handleSort('creationDate')}
                                    >
                                        Creation Date
                                    </TableSortLabel>
                                </TableCell>
                                <TableCell align="right">
                                    <TableSortLabel
                                        active={sortColumn === 'type'}
                                        direction={sortColumn === 'type' ? sortOrder : 'asc'}
                                        onClick={() => handleSort('type')}
                                    >
                                        Type
                                    </TableSortLabel>
                                </TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {sortedPipelines.map((pipeline) => (
                                <TableRow
                                    key={pipeline.id}
                                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                                >
                                    <TableCell component="th" scope="row">
                                        {pipeline.name}
                                    </TableCell>
                                    <TableCell align="right">{pipeline.creationDate}</TableCell>
                                    <TableCell align="right">
                                        <Chip
                                            label={pipeline.type}
                                            color={getChipColor(pipeline.type)}
                                            size="small"
                                        />
                                    </TableCell>
                                    <TableCell align="right">
                                        {pipeline.id !== 1 && (
                                            <Tooltip title="Edit Pipeline">
                                                <IconButton onClick={() => handleEdit(pipeline.id)} size="small">
                                                    <EditIcon />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                        {pipeline.id === 1 && (
                                            <Tooltip title="Deploy Pipeline">
                                                <IconButton
                                                    onClick={() => handleCreatePipeline(hardcodedPipelineData)}
                                                    size="small"
                                                    disabled={isCreatingPipeline}
                                                >
                                                    {isCreatingPipeline ? (
                                                        <CircularProgress size={24} />
                                                    ) : (
                                                        <RocketLaunchIcon />
                                                    )}
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
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
