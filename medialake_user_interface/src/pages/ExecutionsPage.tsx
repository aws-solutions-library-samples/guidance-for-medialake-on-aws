import React from 'react';
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
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    PlayArrow as PlayArrowIcon,
    Stop as StopIcon,
    Visibility as VisibilityIcon,
} from '@mui/icons-material';

interface Execution {
    id: string;
    pipelineName: string;
    status: 'running' | 'completed' | 'failed' | 'pending';
    startTime: string;
    duration: string;
    progress: number;
}

const mockExecutions: Execution[] = [
    {
        id: 'exec-001',
        pipelineName: 'Video Transcoding Pipeline',
        status: 'running',
        startTime: '2024-01-20 10:30:00',
        duration: '45m 20s',
        progress: 75,
    },
    {
        id: 'exec-002',
        pipelineName: 'Image Processing Pipeline',
        status: 'completed',
        startTime: '2024-01-20 09:15:00',
        duration: '30m 15s',
        progress: 100,
    },
    {
        id: 'exec-003',
        pipelineName: 'Metadata Extraction',
        status: 'failed',
        startTime: '2024-01-20 08:45:00',
        duration: '15m 30s',
        progress: 45,
    },
    {
        id: 'exec-004',
        pipelineName: 'Audio Processing',
        status: 'pending',
        startTime: '2024-01-20 11:00:00',
        duration: '-',
        progress: 0,
    },
];

const ExecutionsPage: React.FC = () => {
    const theme = useTheme();

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running':
                return theme.palette.info.main;
            case 'completed':
                return theme.palette.success.main;
            case 'failed':
                return theme.palette.error.main;
            default:
                return theme.palette.grey[500];
        }
    };

    return (
        <Box>
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                        Pipeline Executions
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Monitor and manage your pipeline executions
                    </Typography>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<RefreshIcon />}
                    onClick={() => { }}
                >
                    Refresh
                </Button>
            </Box>

            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>ID</TableCell>
                            <TableCell>Pipeline Name</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Start Time</TableCell>
                            <TableCell>Duration</TableCell>
                            <TableCell align="right">Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {mockExecutions.map((execution) => (
                            <TableRow key={execution.id}>
                                <TableCell>{execution.id}</TableCell>
                                <TableCell>{execution.pipelineName}</TableCell>
                                <TableCell>
                                    <Chip
                                        label={execution.status}
                                        size="small"
                                        sx={{
                                            backgroundColor: `${getStatusColor(execution.status)}15`,
                                            color: getStatusColor(execution.status),
                                            fontWeight: 500,
                                        }}
                                    />
                                </TableCell>
                                <TableCell>{execution.startTime}</TableCell>
                                <TableCell>{execution.duration}</TableCell>
                                <TableCell align="right">
                                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                                        {execution.status === 'running' && (
                                            <IconButton size="small" color="error">
                                                <StopIcon />
                                            </IconButton>
                                        )}
                                        {execution.status === 'pending' && (
                                            <IconButton size="small" color="success">
                                                <PlayArrowIcon />
                                            </IconButton>
                                        )}
                                        <IconButton size="small" color="primary">
                                            <VisibilityIcon />
                                        </IconButton>
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
};

export default ExecutionsPage;
