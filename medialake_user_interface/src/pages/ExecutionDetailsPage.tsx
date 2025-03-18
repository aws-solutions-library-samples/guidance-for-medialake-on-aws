import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { formatLocalDateTime } from '@/shared/utils/dateUtils';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Chip,
    Card,
    CardContent,
    Divider,
    Stepper,
    Step,
    StepLabel,
    StepContent,
    CircularProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    IconButton,
    Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoIcon from '@mui/icons-material/Info';
import { useTheme } from '@mui/material/styles';
import type { ExecutionDetails, ExecutionHistoryEvent } from 'src/api/types/pipelineExecutionDetails.types';

// Mock data for development
const mockExecutionDetails: ExecutionDetails = {
    executionArn: "arn:aws:states:us-west-2:123456789012:execution:MyStateMachine:execution-123",
    stateMachineArn: "arn:aws:states:us-west-2:123456789012:stateMachine:MyStateMachine",
    name: "execution-123",
    status: "SUCCEEDED",
    startDate: "2024-01-15T10:00:00Z",
    stopDate: "2024-01-15T10:05:30Z",
    input: JSON.stringify({
        inputFile: "s3://bucket/input/image.jpg",
        metadata: {
            contentType: "image/jpeg",
            size: 1024567
        }
    }, null, 2),
    inputDetails: {
        included: true
    },
    output: JSON.stringify({
        processedFile: "s3://bucket/output/image_processed.jpg",
        thumbnails: ["s3://bucket/thumbnails/image_thumb.jpg"],
        metadata: {
            dimensions: "1920x1080",
            format: "JPEG",
            colorSpace: "sRGB"
        }
    }, null, 2),
    outputDetails: {
        included: true
    }
};

const mockExecutionHistory: ExecutionHistoryEvent[] = [
    {
        timestamp: "2024-01-15T10:00:00Z",
        type: "ExecutionStarted",
        id: 1,
        stateEnteredEventDetails: {
            name: "ExtractMetadata",
            input: JSON.stringify({ file: "s3://bucket/input/image.jpg" })
        }
    },
    {
        timestamp: "2024-01-15T10:01:00Z",
        type: "TaskSucceeded",
        id: 2,
        previousEventId: 1,
        taskSucceededEventDetails: {
            output: JSON.stringify({ metadata: { dimensions: "1920x1080" } }),
            resource: "lambda:ExtractMetadata"
        }
    },
    {
        timestamp: "2024-01-15T10:02:00Z",
        type: "TaskScheduled",
        id: 3,
        previousEventId: 2,
        taskScheduledEventDetails: {
            resource: "lambda:ProcessImage",
            resourceType: "lambda",
            parameters: JSON.stringify({ action: "process" })
        }
    },
    {
        timestamp: "2024-01-15T10:05:00Z",
        type: "ExecutionSucceeded",
        id: 4,
        previousEventId: 3
    }
];

const ExecutionDetailsPage: React.FC = () => {
    const { executionId } = useParams<{ executionId: string }>();
    const theme = useTheme();
    const [loading, setLoading] = useState(true);
    const [execution, setExecution] = useState<ExecutionDetails | null>(null);
    const [history, setHistory] = useState<ExecutionHistoryEvent[]>([]);

    useEffect(() => {
        // Simulate API call
        const fetchExecutionDetails = async () => {
            try {
                // In production, this would be an actual API call
                await new Promise(resolve => setTimeout(resolve, 1000));
                setExecution(mockExecutionDetails);
                setHistory(mockExecutionHistory);
            } catch (error) {
                console.error('Error fetching execution details:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchExecutionDetails();
    }, [executionId]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'SUCCEEDED':
                return 'success';
            case 'FAILED':
            case 'TIMED_OUT':
                return 'error';
            case 'RUNNING':
                return 'info';
            default:
                return 'default';
        }
    };

    const formatDuration = (startDate: string, stopDate?: string) => {
        if (!stopDate) return 'In Progress';
        
        // Parse ISO dates and calculate duration
        const start = new Date(startDate).getTime();
        const end = new Date(stopDate).getTime();
        const seconds = Math.floor((end - start) / 1000);
        
        return `${seconds} seconds`;
    };

    const renderJsonContent = (content: string) => {
        try {
            const parsed = JSON.parse(content);
            return (
                <pre style={{
                    backgroundColor: theme.palette.grey[100],
                    padding: theme.spacing(2),
                    borderRadius: theme.shape.borderRadius,
                    overflow: 'auto',
                    maxHeight: '200px'
                }}>
                    {JSON.stringify(parsed, null, 2)}
                </pre>
            );
        } catch {
            return <Typography variant="body2">{content}</Typography>;
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (!execution) {
        return (
            <Box p={3}>
                <Typography variant="h6" color="error">
                    Execution not found or error loading details
                </Typography>
            </Box>
        );
    }

    return (
        <Box p={3}>
            <Paper elevation={0} sx={{ p: 3, mb: 3 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h4" gutterBottom>
                        Pipeline Execution Details
                    </Typography>
                    <Chip
                        label={execution.status}
                        color={getStatusColor(execution.status)}
                        size="medium"
                    />
                </Box>

                <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                        <Typography variant="subtitle2" color="textSecondary">
                            Execution Name
                        </Typography>
                        <Typography variant="body1">
                            {execution.name}
                        </Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                        <Typography variant="subtitle2" color="textSecondary">
                            Duration
                        </Typography>
                        <Typography variant="body1">
                            {formatDuration(execution.startDate, execution.stopDate)}
                        </Typography>
                    </Grid>
                    <Grid item xs={12}>
                        <Typography variant="subtitle2" color="textSecondary">
                            State Machine ARN
                        </Typography>
                        <Typography variant="body1" sx={{ wordBreak: 'break-all' }}>
                            {execution.stateMachineArn}
                        </Typography>
                    </Grid>
                </Grid>
            </Paper>

            <Grid container spacing={3}>
                <Grid item xs={12}>
                    <Accordion defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="h6">Input</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            {renderJsonContent(execution.input)}
                        </AccordionDetails>
                    </Accordion>

                    {execution.output && (
                        <Accordion defaultExpanded>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography variant="h6">Output</Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                {renderJsonContent(execution.output)}
                            </AccordionDetails>
                        </Accordion>
                    )}

                    {execution.error && (
                        <Accordion defaultExpanded>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography variant="h6" color="error">Error Details</Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Typography color="error" gutterBottom>
                                    Error: {execution.error}
                                </Typography>
                                {execution.cause && (
                                    <Typography color="error">
                                        Cause: {execution.cause}
                                    </Typography>
                                )}
                            </AccordionDetails>
                        </Accordion>
                    )}
                </Grid>

                <Grid item xs={12}>
                    <Paper elevation={0} sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Execution History
                        </Typography>
                        <Stepper orientation="vertical">
                            {history.map((event) => (
                                <Step key={event.id} active={true} completed={true}>
                                    <StepLabel>
                                        <Box>
                                            <Typography variant="subtitle1">
                                                {event.type}
                                            </Typography>
                                            <Typography variant="caption" color="textSecondary">
                                                {formatLocalDateTime(event.timestamp, { showSeconds: true })}
                                            </Typography>
                                        </Box>
                                    </StepLabel>
                                    <StepContent>
                                        {event.stateEnteredEventDetails && (
                                            <Box mt={1}>
                                                <Typography variant="subtitle2">
                                                    State: {event.stateEnteredEventDetails.name}
                                                </Typography>
                                                <Typography variant="body2">
                                                    Input: {event.stateEnteredEventDetails.input}
                                                </Typography>
                                            </Box>
                                        )}
                                        {event.taskSucceededEventDetails && (
                                            <Box mt={1}>
                                                <Typography variant="subtitle2">
                                                    Resource: {event.taskSucceededEventDetails.resource}
                                                </Typography>
                                                <Typography variant="body2">
                                                    Output: {event.taskSucceededEventDetails.output}
                                                </Typography>
                                            </Box>
                                        )}
                                        {event.taskFailedEventDetails && (
                                            <Box mt={1}>
                                                <Typography variant="subtitle2" color="error">
                                                    Error: {event.taskFailedEventDetails.error}
                                                </Typography>
                                                <Typography variant="body2" color="error">
                                                    Cause: {event.taskFailedEventDetails.cause}
                                                </Typography>
                                            </Box>
                                        )}
                                    </StepContent>
                                </Step>
                            ))}
                        </Stepper>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ExecutionDetailsPage;
