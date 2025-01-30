import React from 'react';
import { Box, Typography, Paper, CircularProgress } from '@mui/material';
import { useGetNodes } from '@/shared/nodes/api/nodesController';
import { Node as NodeType } from '@/shared/nodes/types/nodes.types';

const Sidebar: React.FC = () => {
    const { data: nodesResponse, isLoading, error } = useGetNodes();

    const onDragStart = (event: React.DragEvent, node: NodeType) => {
        const nodeData = {
            id: node.nodeId, // Store the original node ID
            type: node.info.nodeType.toLowerCase(),
            label: node.info.title,
            description: node.info.description,
            inputTypes: node.info.inputTypes || ['video', 'audio', 'image'], // TODO: Get these from the API
            outputTypes: node.info.outputTypes || ['video', 'audio', 'image'], // TODO: Get these from the API
            methods: node.methods || [], // Pass methods for configuration
            icon: node.info.iconUrl,
        };

        event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeData));
        event.dataTransfer.effectAllowed = 'move';
    };

    if (isLoading) {
        return (
            <Box
                sx={{
                    width: 250,
                    backgroundColor: 'background.paper',
                    borderLeft: 1,
                    borderColor: 'divider',
                    p: 2,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center'
                }}
            >
                <CircularProgress />
            </Box>
        );
    }

    if (error || !nodesResponse?.data) {
        return (
            <Box
                sx={{
                    width: 250,
                    backgroundColor: 'background.paper',
                    borderLeft: 1,
                    borderColor: 'divider',
                    p: 2,
                }}
            >
                <Typography color="error">
                    Failed to load nodes. Please try again later.
                </Typography>
            </Box>
        );
    }

    return (
        <Box
            sx={{
                width: 250,
                backgroundColor: 'background.paper',
                borderLeft: 1,
                borderColor: 'divider',
                p: 2,
                overflowY: 'auto',
            }}
        >
            <Typography variant="h6" gutterBottom>
                Node Types
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {nodesResponse.data.map((node) => (
                    <Paper
                        key={node.info.nodeType}
                        elevation={2}
                        onDragStart={(event) => onDragStart(event, node)}
                        draggable
                        sx={{
                            p: 2,
                            cursor: 'grab',
                            '&:hover': {
                                backgroundColor: 'action.hover',
                            },
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 1,
                        }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="subtitle1">
                                {node.info.title}
                            </Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                            {node.info.description}
                        </Typography>
                        {node.info.tags && node.info.tags.length > 0 && (
                            <Box sx={{ mt: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    Tags: {node.info.tags.join(', ')}
                                </Typography>
                            </Box>
                        )}
                    </Paper>
                ))}
            </Box>
        </Box>
    );
}

export default Sidebar; 