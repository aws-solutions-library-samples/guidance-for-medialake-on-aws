import React, { useCallback } from 'react';
import { Handle, Position, NodeProps, useReactFlow } from 'reactflow';
import { Box, Typography, IconButton } from '@mui/material';
import { FaCog, FaTrash } from 'react-icons/fa';

const HANDLE_CONNECT_RADIUS = 50;

export interface CustomNodeData {
    label: string;
    icon: React.ReactNode;
    inputTypes: string[];
    outputTypes: string[];
    nodeId: string; // Original node ID from the API
    description: string; // Node description
    configuration?: any; // Node configuration
    onDelete?: (id: string) => void;
    onConfigure?: (id: string) => void;
}

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ id, data, isConnectable }) => {
    const { project } = useReactFlow();

    const handleDelete = (event: React.MouseEvent) => {
        event.stopPropagation();
        data.onDelete?.(id);
    };

    const handleConfigure = (event: React.MouseEvent) => {
        event.stopPropagation();
        data.onConfigure?.(id);
    };

    const handleNodeClick = useCallback((event: React.MouseEvent) => {
        const rect = (event.target as HTMLElement).getBoundingClientRect();
        const sourceHandleX = rect.right;
        const sourceHandleY = rect.top + rect.height / 2;

        const clickX = event.clientX;
        const clickY = event.clientY;

        // Calculate distance from click to source handle
        const distance = Math.sqrt(
            Math.pow(clickX - sourceHandleX, 2) +
            Math.pow(clickY - sourceHandleY, 2)
        );

        // If click is within radius of source handle, start connection
        if (distance <= HANDLE_CONNECT_RADIUS) {
            const { x, y } = project({ x: clickX, y: clickY });
            const event = new MouseEvent('mousedown', {
                clientX: sourceHandleX,
                clientY: sourceHandleY,
                bubbles: true
            });
            const sourceHandle = document.querySelector(`[data-nodeid="${id}"] .react-flow__handle-source`);
            sourceHandle?.dispatchEvent(event);
        }
    }, [id, project]);

    return (
        <Box
            onClick={handleNodeClick}
            sx={{
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: 'background.paper',
                border: 1,
                borderColor: data.configuration ? 'primary.main' : 'divider',
                width: '200px', // Set fixed width to half of original
                maxWidth: '200px',
                position: 'relative',
                boxShadow: 2,
                cursor: 'pointer',
                '&:hover': {
                    boxShadow: 3
                }
            }}
        >
            <Handle
                type="target"
                position={Position.Left}
                isConnectable={isConnectable}
                style={{
                    background: '#555',
                    width: '12px',
                    height: '12px',
                    border: '2px solid #fff',
                    borderRadius: '6px'
                }}
            />

            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, position: 'relative' }}>
                {data.icon}
                <Box sx={{ flex: 1, minWidth: 0 }}> {/* Add minWidth: 0 to enable text wrapping */}
                    <Typography 
                        variant="subtitle1" 
                        sx={{ 
                            lineHeight: 1.2, 
                            fontWeight: 'medium',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                        }}
                    >
                        {data.label}
                    </Typography>
                    <Typography 
                        variant="body2" 
                        color="text.secondary" 
                        sx={{ 
                            lineHeight: 1.2,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            display: '-webkit-box'
                        }}
                    >
                        {data.description}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5, ml: 0.5 }}>
                    <IconButton
                        size="small"
                        onClick={handleConfigure}
                        sx={{ p: 0.5 }}
                    >
                        <FaCog size={14} />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={handleDelete}
                        sx={{ p: 0.5 }}
                    >
                        <FaTrash size={14} />
                    </IconButton>
                </Box>
            </Box>

            <Handle
                type="source"
                position={Position.Right}
                isConnectable={isConnectable}
                style={{
                    background: '#555',
                    width: '12px',
                    height: '12px',
                    border: '2px solid #fff',
                    borderRadius: '6px'
                }}
            />
        </Box>
    );
};

export default CustomNode;