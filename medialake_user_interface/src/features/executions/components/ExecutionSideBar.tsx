import React from 'react';
import {
    Box,
    Typography,
    IconButton,
    Divider,
    Paper,
    Stack,
    Slide,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import type { PipelineExecution } from '../types/pipelineExecutions.types';

interface ExecutionSideBarProps {
    isOpen: boolean;
    execution: PipelineExecution | null;
    onClose: () => void;
}

export const ExecutionSideBar: React.FC<ExecutionSideBarProps> = ({
    isOpen,
    execution,
    onClose
}) => {
    if (!execution) return null;

    return (
        <Slide direction="left" in={isOpen} mountOnEnter unmountOnExit>
            <Box
                sx={{
                    right: 16,
                    top: 16,
                    bottom: 16,
                    width: '500px',
                    height: '100%',
                    bgcolor: 'background.paper',
                    borderLeft: '1px solid',
                    borderColor: 'divider',
                    borderRadius: '8px !important', // Force border radius
                    zIndex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    boxShadow: (theme) => theme.shadows[1],
                    overflow: 'hidden',
                    '& .MuiPaper-root': {
                        borderRadius: '8px',
                    },
                }}
            >
                {/* Header */}
                <Box sx={{ 
                    p: 2, 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between',
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    bgcolor: 'background.paper',
                }}>
                    <Typography variant="h6">Execution Details</Typography>
                    <IconButton onClick={onClose} size="small">
                        <CloseIcon />
                    </IconButton>
                </Box>

                {/* Content */}
                <Box sx={{ 
                    flex: 1, 
                    overflow: 'auto',
                    p: 2,
                }}>
                    <Stack spacing={2}>
                        {/* Basic Information */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                Basic Information
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Stack spacing={2}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Pipeline Name
                                    </Typography>
                                    <Typography>
                                        {execution.pipeline_name}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Execution ID
                                    </Typography>
                                    <Typography>
                                        {execution.execution_id}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Status
                                    </Typography>
                                    <Typography>
                                        {execution.status}
                                    </Typography>
                                </Box>
                            </Stack>
                        </Paper>

                        {/* Timing Information */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                Timing Information
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Stack spacing={2}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Start Time
                                    </Typography>
                                    <Typography>
                                        {new Date(execution.start_time).toLocaleString()}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        End Time
                                    </Typography>
                                    <Typography>
                                        {execution.end_time ? new Date(execution.end_time).toLocaleString() : 'N/A'}
                                    </Typography>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Duration
                                    </Typography>
                                    <Typography>
                                        {execution.duration_seconds ? `${execution.duration_seconds} seconds` : 'N/A'}
                                    </Typography>
                                </Box>
                            </Stack>
                        </Paper>
                        {/*  
                        Execution Details
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                Execution Details
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Stack spacing={2}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Input Parameters
                                    </Typography>
                                    <Box sx={{ 
                                        mt: 1,
                                        p: 1.5,
                                        bgcolor: 'background.default',
                                        borderRadius: 1,
                                        border: '1px solid',
                                        borderColor: 'divider',
                                    }}>
                                        <Typography sx={{ 
                                            whiteSpace: 'pre-wrap',
                                            fontFamily: 'monospace',
                                            fontSize: '0.875rem'
                                        }}>
                                            {JSON.stringify(execution.input_parameters, null, 2)}
                                        </Typography>
                                    </Box>
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">
                                        Output
                                    </Typography>
                                    <Box sx={{ 
                                        mt: 1,
                                        p: 1.5,
                                        bgcolor: 'background.default',
                                        borderRadius: 1,
                                        border: '1px solid',
                                        borderColor: 'divider',
                                    }}>
                                        <Typography sx={{ 
                                            whiteSpace: 'pre-wrap',
                                            fontFamily: 'monospace',
                                            fontSize: '0.875rem'
                                        }}>
                                            {JSON.stringify(execution.output, null, 2)}
                                        </Typography>
                                    </Box>
                                </Box>
                            </Stack>
                        </Paper>
                       
                        
                        {execution.error && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="subtitle2" color="error" gutterBottom>
                                    Error Information
                                </Typography>
                                <Divider sx={{ my: 1 }} />
                                <Box sx={{ 
                                    mt: 1,
                                    p: 1.5,
                                    bgcolor: 'background.default',
                                    borderRadius: 1,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                }}>
                                    <Typography color="error" sx={{ 
                                        whiteSpace: 'pre-wrap',
                                        fontFamily: 'monospace',
                                        fontSize: '0.875rem'
                                    }}>
                                        {execution.error}
                                    </Typography>
                                </Box>
                            </Paper>
                        )}
                        */}
                    </Stack>
                </Box>
            </Box>
        </Slide>
    );
};

export default ExecutionSideBar;
