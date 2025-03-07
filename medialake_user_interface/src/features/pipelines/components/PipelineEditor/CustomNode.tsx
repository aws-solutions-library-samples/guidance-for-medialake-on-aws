import React, { useCallback } from 'react';
import { Handle, Position, NodeProps, useReactFlow } from 'reactflow';
import { Box, Typography, IconButton } from '@mui/material';
import { FaCog, FaTrash } from 'react-icons/fa';

const HANDLE_CONNECT_RADIUS = 50;

export interface OutputType {
    name: string;
    description?: string;
}

export interface CustomNodeData {
    label: string;
    icon: React.ReactNode;
    inputTypes: string[];
    outputTypes: string[] | OutputType[]; // Can be either simple strings or objects with name/description
    nodeId: string; // Original node ID from the API
    description: string; // Node description
    configuration?: any; // Node configuration
    onDelete?: (id: string) => void;
    onConfigure?: (id: string) => void;
    type?: string; // Node type (e.g., 'TRIGGER', 'INTEGRATION', 'FLOW')
}

const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ id, data, isConnectable }) => {
    const { project } = useReactFlow();

    // Debug logging
    console.log('[CustomNode] Rendering node:', id);
    console.log('[CustomNode] Node data:', data);
    console.log('[CustomNode] Output types:', data.outputTypes);
    console.log('[CustomNode] Is array of objects?',
        Array.isArray(data.outputTypes) &&
        data.outputTypes.length > 0 &&
        typeof data.outputTypes[0] === 'object' &&
        'name' in (data.outputTypes[0] as any)
    );

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
        const clickX = event.clientX;
        const clickY = event.clientY;

        // Helper function to check if click is near a handle
        const isNearHandle = (handleElement: Element | null) => {
            if (!handleElement) return false;
            const handleRect = handleElement.getBoundingClientRect();
            const handleX = handleRect.left + handleRect.width / 2;
            const handleY = handleRect.top + handleRect.height / 2;

            const distance = Math.sqrt(
                Math.pow(clickX - handleX, 2) + Math.pow(clickY - handleY, 2)
            );

            return distance <= HANDLE_CONNECT_RADIUS;
        };

        // Find the closest handle
        const handles = Array.from(document.querySelectorAll(`[data-nodeid="${id}"] .react-flow__handle-source`));
        for (const handle of handles) {
            if (isNearHandle(handle)) {
                const event = new MouseEvent('mousedown', {
                    clientX: clickX,
                    clientY: clickY,
                    bubbles: true,
                });
                handle.dispatchEvent(event);
                break;
            }
        }
    }, [id, project]);

    const isTriggerNode = data.type?.includes('TRIGGER');

    return (
        <Box
            onClick={handleNodeClick}
            sx={{
                padding: '12px',
                borderRadius: '8px',
                backgroundColor: 'background.paper',
                border: 1,
                borderColor: data.configuration ? 'primary.main' : 'divider',
                width: '200px', // Set fixed width to half of original
                maxWidth: '200px',
                minHeight: '100px',
                position: 'relative',
                boxShadow: 2,
                cursor: 'pointer',
                '&:hover': {
                    boxShadow: 3
                }
            }}
        >
            {!isTriggerNode && (
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
            )}

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

            {/* Check if we have multiple output types or a single output */}
            {Array.isArray(data.outputTypes) && data.outputTypes.length > 0 &&
                typeof data.outputTypes[0] === 'object' && 'name' in (data.outputTypes[0] as any) ? (
                // Multiple output types as objects with name/description
                <Box sx={{
                    position: 'absolute',
                    right: 0,
                    top: '25%',
                    height: '75%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between'
                }}>
                    {(data.outputTypes as OutputType[]).map((output, index) => (
                        <Box
                            key={output.name}
                            sx={{
                                position: 'relative',
                                height: '24px',
                                display: 'flex',
                                alignItems: 'center',
                                mr: '-6px'
                            }}
                        >
                            <Typography variant="caption" sx={{ mr: 1, fontSize: '0.7rem' }}>
                                {output.name}
                            </Typography>
                            <Handle
                                type="source"
                                position={Position.Right}
                                id={output.name}
                                isConnectable={isConnectable}
                                style={{
                                    background: index === 0 ? '#4CAF50' : index === 1 ? '#2196F3' : '#F44336',
                                    width: '10px',
                                    height: '10px',
                                    border: '2px solid #fff',
                                    borderRadius: '5px',
                                }}
                            />
                        </Box>
                    ))}
                </Box>
            ) : (
                // Single output handle (default behavior)
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
            )}
        </Box>
    );
};

export default CustomNode;
