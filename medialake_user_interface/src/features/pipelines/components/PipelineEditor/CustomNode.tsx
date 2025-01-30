import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Box, Typography, IconButton } from '@mui/material';
import { FaCog, FaTrash } from 'react-icons/fa';

interface CustomNodeData {
    label: string;
    icon: React.ReactNode;
    inputTypes: string[];
    outputTypes: string[];
    nodeId: string; // Original node ID from the API
    configuration?: any; // Node configuration
    onDelete?: (id: string) => void;
    onConfigure?: (id: string) => void;
}

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ id, data, isConnectable }) => {
    const handleDelete = (event: React.MouseEvent) => {
        event.stopPropagation();
        data.onDelete?.(id);
    };

    const handleConfigure = (event: React.MouseEvent) => {
        event.stopPropagation();
        data.onConfigure?.(id);
    };

    return (
        <Box
            sx={{
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: 'background.paper',
                border: 1,
                borderColor: data.configuration ? 'primary.main' : 'divider',
                minWidth: 150,
                position: 'relative',
                boxShadow: 2,
            }}
        >
            {data.inputTypes.length > 0 && (
                <Handle
                    type="target"
                    position={Position.Left}
                    isConnectable={isConnectable}
                    style={{ background: '#555' }}
                />
            )}

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {data.icon}
                <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle1" sx={{ lineHeight: 1.2 }}>
                        {data.label}
                    </Typography>
                    {data.configuration?.method && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                            Method: {data.configuration.method}
                        </Typography>
                    )}
                </Box>
                <Box sx={{ ml: 'auto', display: 'flex', gap: 0.5 }}>
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

            {data.outputTypes.length > 0 && (
                <Handle
                    type="source"
                    position={Position.Right}
                    isConnectable={isConnectable}
                    style={{ background: '#555' }}
                />
            )}
        </Box>
    );
};

export default CustomNode; 