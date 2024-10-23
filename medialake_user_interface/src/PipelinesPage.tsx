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
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import { useNavigate } from 'react-router-dom';

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
    { id: 1, name: 'Video Analysis', creationDate: '2023-05-01', type: pipelineTypes.INGEST },
    { id: 2, name: 'Image Analysis', creationDate: '2023-05-02', type: pipelineTypes.INGEST },
    { id: 3, name: 'Audio Analysis', creationDate: '2023-05-03', type: pipelineTypes.INGEST },
    { id: 4, name: 'Metadata Extraction', creationDate: '2023-05-04', type: pipelineTypes.MANUAL },
    { id: 5, name: 'Content Moderation', creationDate: '2023-05-05', type: pipelineTypes.MANUAL },
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
    const navigate = useNavigate();

    const handleEdit = async (id: number) => {
        const pipelineData = await fetchPipelineData(id);
        if (pipelineData) {
            navigate(`/pipelines/edit/${id}`, { state: { pipelineData } });
        } else {
            console.error('Pipeline not found');
        }
    };

    const handleAddNew = () => {
        navigate('/pipelines/new');
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
                                        <Tooltip title="Edit Pipeline">
                                            <IconButton onClick={() => handleEdit(pipeline.id)} size="small">
                                                <EditIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        </Box>
    );
};

export default PipelinesPage;
