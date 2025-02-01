import React from 'react';
import { Box, Typography, Paper, CircularProgress } from '@mui/material';
import { useGetUnconfiguredNodeMethods } from '@/shared/nodes/api/nodesController';
import { Node as NodeType } from '@/shared/nodes/types/nodes.types';
import { RightSidebar } from '@/components/common/RightSidebar/RightSidebar';

const SidebarContent: React.FC = () => {
    const { data: nodesResponse, isLoading, error } = useGetUnconfiguredNodeMethods();

    const onDragStart = (event: React.DragEvent, node: NodeType, methodName: string) => {
        const method = node.methods?.[methodName];
        const nodeData = {
            id: node.nodeId,
            type: node.info.nodeType.toLowerCase(),
            label: node.info.title,
            description: method?.description || node.info.description,
            inputTypes: node.info.inputTypes || [],
            outputTypes: node.info.outputTypes || [],
            methods: node.methods || {},
            icon: node.info.iconUrl,
            selectedMethod: methodName,
            methodConfig: {
                method: methodName,
                parameters: method?.parameters || {},
                inputMapping: method?.inputMapping,
                outputMapping: method?.outputMapping,
                path: method?.path,
                operationId: method?.operationId,
            },
        };

        event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeData));
        event.dataTransfer.effectAllowed = 'move';
    };

    if (isLoading) {
        return (
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error || !nodesResponse?.data) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography color="error">
                    Failed to load nodes. Please try again later.
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Available Methods
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {nodesResponse.data.map((node) => (
                    node.methods && Object.entries(node.methods).map(([methodName, method]) => (
                        <Paper
                            key={`${node.nodeId}-${methodName}`}
                            elevation={2}
                            onDragStart={(event) => onDragStart(event, node, methodName)}
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
                                {method.description || node.info.description}
                            </Typography>
                            {node.info.tags && node.info.tags.length > 0 && (
                                <Box sx={{ mt: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                        Tags: {node.info.tags.join(', ')}
                                    </Typography>
                                </Box>
                            )}
                        </Paper>
                    ))
                ))}
            </Box>
        </Box>
    );
};

const Sidebar: React.FC = () => {
    return (
        <RightSidebar>
            <SidebarContent />
        </RightSidebar>
    );
};

export default Sidebar;
