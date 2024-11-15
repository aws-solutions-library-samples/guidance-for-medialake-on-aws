import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Button, CircularProgress } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

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

const pipelineTypes = {
    INGEST: 'Ingest Triggered',
    MANUAL: 'Manually Triggered',
    ANALYSIS: 'Analysis Triggered',
} as const;

type PipelineType = typeof pipelineTypes[keyof typeof pipelineTypes];

interface PipelineData {
    id: number;
    name: string;
    creationDate: string;
    type: PipelineType;
    nodes: Node[];
    edges: Edge[];
}

// Mock pipelines data
const mockPipelines = [
    { id: 1, name: 'Video Analysis', creationDate: '2023-05-01', type: pipelineTypes.INGEST },
    { id: 2, name: 'Image Analysis', creationDate: '2023-05-02', type: pipelineTypes.INGEST },
    { id: 3, name: 'Audio Analysis', creationDate: '2023-05-03', type: pipelineTypes.INGEST },
    { id: 4, name: 'Metadata Extraction', creationDate: '2023-05-04', type: pipelineTypes.MANUAL },
    { id: 5, name: 'Content Moderation', creationDate: '2023-05-05', type: pipelineTypes.MANUAL },
];

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

interface PipelineEditorProps { }

const PipelineEditorPage: React.FC<PipelineEditorProps> = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);

    useEffect(() => {
        const loadPipelineData = async () => {
            try {
                if (id) {
                    const data = await fetchPipelineData(parseInt(id));
                    setPipelineData(data);
                } else {
                    // Initialize empty pipeline data for new pipeline
                    setPipelineData({
                        id: 0,
                        name: 'New Pipeline',
                        creationDate: new Date().toISOString().split('T')[0],
                        type: pipelineTypes.MANUAL,
                        nodes: [],
                        edges: []
                    });
                }
            } catch (error) {
                console.error('Error loading pipeline:', error);
                // Handle error state here if needed
            } finally {
                setLoading(false);
            }
        };

        loadPipelineData();
    }, [id]);

    const handleBack = () => {
        navigate('/pipelines');
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!pipelineData && id) {
        return (
            <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                    <Button
                        startIcon={<ArrowBackIcon />}
                        onClick={handleBack}
                        sx={{ mr: 2 }}
                    >
                        Back to Pipelines
                    </Button>
                </Box>
                <Typography color="error">
                    Pipeline not found
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={handleBack}
                    sx={{ mr: 2 }}
                >
                    Back to Pipelines
                </Button>
                <Typography variant="h4" component="h1">
                    {id ? 'Edit Pipeline' : 'Create New Pipeline'}
                </Typography>
            </Box>

            <Box sx={{ mt: 2 }}>
                <Typography variant="h6">
                    {pipelineData?.name}
                </Typography>
                {/* Add your pipeline editor components here */}
            </Box>
        </Box>
    );
};

export default PipelineEditorPage;
