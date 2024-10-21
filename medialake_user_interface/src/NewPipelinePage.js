import React, { useCallback, useRef, useEffect, useState } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    ReactFlowProvider,
    useReactFlow,
    getBezierPath,
    Handle,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Box, Modal, TextField, Button, IconButton, Select, MenuItem, Typography } from '@mui/material';
import { FaAmazon, FaVideo, FaDatabase, FaFileVideo, FaFileAudio, FaFileImage, FaTrash, FaPencilAlt } from 'react-icons/fa';

const CustomNode = ({ data, id }) => {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedOption, setSelectedOption] = useState('');
    const { getNodes, setNodes } = useReactFlow();

    const onDelete = () => {
        setNodes(getNodes().filter((node) => node.id !== id));
    };

    const onEdit = () => {
        setIsModalOpen(true);
    };

    const onSaveChanges = () => {
        // Handle saving changes (API call)
        setIsModalOpen(false);
    };

    return (
        <>
            <div style={{
                width: '60px',
                height: '55px',
                border: '1px solid #1a192b',
                borderRadius: '5px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'white',
                position: 'relative',
                padding: '3px 5px 4px',
            }}>
                <Handle type="target" position="left" />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    {data.icon}
                    <div style={{ marginTop: '2px', fontSize: '10px', textAlign: 'center' }}>{data.label}</div>
                </div>
                <Handle type="source" position="right" />
                <div style={{ position: 'absolute', bottom: '2px', right: '2px', display: 'flex' }}>
                    <IconButton size="small" onClick={onEdit} style={{ marginRight: '2px' }}>
                        <FaPencilAlt size={10} />
                    </IconButton>
                    <IconButton size="small" onClick={onDelete}>
                        <FaTrash size={10} />
                    </IconButton>
                </div>
            </div>
            <Modal
                open={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                aria-labelledby="node-config-modal"
                aria-describedby="modal-to-configure-node"
            >
                <Box sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: 400,
                    bgcolor: 'background.paper',
                    border: '2px solid #000',
                    boxShadow: 24,
                    p: 4,
                }}>
                    <Select
                        fullWidth
                        value={selectedOption}
                        onChange={(e) => setSelectedOption(e.target.value)}
                        sx={{ mb: 2 }}
                    >
                        <MenuItem value="option1">Option 1</MenuItem>
                        <MenuItem value="option2">Option 2</MenuItem>
                        <MenuItem value="option3">Option 3</MenuItem>
                    </Select>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <Button onClick={() => setIsModalOpen(false)} sx={{ mr: 1 }}>Cancel</Button>
                        <Button onClick={onSaveChanges} variant="contained">Save</Button>
                    </Box>
                </Box>
            </Modal>
        </>
    );
};

const nodeTypes = {
    custom: CustomNode,
};

const CustomEdge = ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    data,
    markerEnd,
}) => {
    const edgePath = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    const { getEdges, setEdges } = useReactFlow();

    const onEdgeDelete = (event) => {
        event.stopPropagation();
        setEdges(getEdges().filter((edge) => edge.id !== id));
    };

    // Calculate the position of the trash can icon
    const iconSize = 20;
    const iconOffset = 15;
    const iconX = targetX - iconOffset;
    const iconY = targetY - iconSize / 2;

    return (
        <>
            <path
                id={id}
                style={style}
                className="react-flow__edge-path"
                d={edgePath}
                markerEnd={markerEnd}
            />
            <text>
                <textPath href={`#${id}`} style={{ fontSize: '12px' }} startOffset="50%" textAnchor="middle">
                    {data.text}
                </textPath>
            </text>
            <foreignObject
                width={iconSize}
                height={iconSize}
                x={iconX}
                y={iconY}
                requiredExtensions="http://www.w3.org/1999/xhtml"
            >
                <div>
                    <IconButton size="small" onClick={onEdgeDelete}>
                        <FaTrash size={10} />
                    </IconButton>
                </div>
            </foreignObject>
        </>
    );
};

const edgeTypes = {
    custom: CustomEdge,
};

const initialNodes = [
    { id: '1', type: 'custom', position: { x: 0, y: 0 }, data: { label: 'Video Asset', icon: <FaFileVideo size={20} />, inputTypes: ['video'], outputTypes: ['video'] } },
    { id: '2', type: 'custom', position: { x: 150, y: 0 }, data: { label: 'MediaConvert', icon: <FaVideo size={20} />, inputTypes: ['video'], outputTypes: ['video'] } },
    { id: '3', type: 'custom', position: { x: 300, y: 0 }, data: { label: 'TwelveLabs', icon: <FaDatabase size={20} />, inputTypes: ['video'], outputTypes: ['metadata'] } },
    { id: '4', type: 'custom', position: { x: 450, y: 0 }, data: { label: 'MediaLake', icon: <FaAmazon size={20} />, inputTypes: ['video', 'metadata'], outputTypes: [] } },
];

const initialEdges = [
    { id: 'e1-2', source: '1', target: '2', type: 'custom', data: { text: 'Transcode assets' } },
    { id: 'e2-3', source: '2', target: '3', type: 'custom', data: { text: 'Edge 2' } },
    { id: 'e3-4', source: '3', target: '4', type: 'custom', data: { text: 'Edge 3' } },
];

let id = 0;
const getId = () => `dndnode_${id++}`;

const Sidebar = () => {
    const onDragStart = (event, nodeType) => {
        event.dataTransfer.setData('application/reactflow', nodeType);
        event.dataTransfer.effectAllowed = 'move';
    };

    return (
        <aside style={{ padding: '15px', borderLeft: '1px solid #ccc', height: '100%', width: '200px', overflowY: 'auto' }}>
            <div style={{ marginBottom: '10px' }}>Drag nodes to the pane</div>
            <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {[
                    { type: 'videoasset', label: 'Video Asset', icon: <FaFileVideo size={20} />, inputTypes: ['video'], outputTypes: ['video'] },
                    { type: 'audioasset', label: 'Audio Asset', icon: <FaFileAudio size={20} />, inputTypes: ['audio'], outputTypes: ['audio'] },
                    { type: 'imageasset', label: 'Image Asset', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                    { type: 'mediaconvert', label: 'MediaConvert', icon: <FaVideo size={20} />, inputTypes: ['video', 'audio'], outputTypes: ['video', 'audio'] },
                    { type: 'twelvelabs', label: 'TwelveLabs', icon: <FaDatabase size={20} />, inputTypes: ['video'], outputTypes: ['metadata'] },
                    { type: 'medialake', label: 'MediaLake', icon: <FaAmazon size={20} />, inputTypes: ['video', 'audio', 'image', 'metadata'], outputTypes: [] },
                ].map((item) => (
                    <div
                        key={item.type}
                        style={{
                            width: '60px',
                            height: '70px',
                            border: '1px solid #1a192b',
                            borderRadius: '5px',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'white',
                            margin: '5px',
                            cursor: 'grab',
                        }}
                        onDragStart={(event) => onDragStart(event, JSON.stringify(item))}
                        draggable
                    >
                        {item.icon}
                        <div style={{ marginTop: '5px', fontSize: '10px' }}>{item.label}</div>
                    </div>
                ))}
            </div>
        </aside>
    );
};

const NewPipelinePage = () => {
    const reactFlowWrapper = useRef(null);
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { project } = useReactFlow();
    const [isEdgeModalOpen, setIsEdgeModalOpen] = useState(false);
    const [selectedEdge, setSelectedEdge] = useState(null);
    const [edgeLabel, setEdgeLabel] = useState('');
    const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);

    useEffect(() => {
        setEdges(initialEdges);
    }, [setEdges]);

    const onConnect = useCallback(
        (params) => {
            const sourceNode = nodes.find((node) => node.id === params.source);
            const targetNode = nodes.find((node) => node.id === params.target);

            if (sourceNode && targetNode) {
                const isCompatible = sourceNode.data.outputTypes.every((outputType) =>
                    targetNode.data.inputTypes.includes(outputType)
                );

                if (isCompatible) {
                    const edgeLabel = `to ${targetNode.data.label}`;
                    setEdges((eds) => addEdge({ ...params, type: 'custom', data: { text: edgeLabel } }, eds));
                } else {
                    setIsErrorModalOpen(true);
                }
            }
        },
        [nodes, setEdges]
    );

    const onEdgeClick = useCallback((event, edge) => {
        setSelectedEdge(edge);
        setEdgeLabel(edge.data.text);
        setIsEdgeModalOpen(true);
    }, []);

    const onSaveEdgeLabel = () => {
        setEdges((eds) =>
            eds.map((ed) =>
                ed.id === selectedEdge.id ? { ...ed, data: { ...ed.data, text: edgeLabel } } : ed
            )
        );
        setIsEdgeModalOpen(false);
    };

    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback(
        (event) => {
            event.preventDefault();

            const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
            const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));

            if (typeof nodeData === 'undefined' || !nodeData) {
                return;
            }

            const position = project({
                x: event.clientX - reactFlowBounds.left,
                y: event.clientY - reactFlowBounds.top,
            });

            const newNode = {
                id: getId(),
                type: 'custom',
                position,
                data: nodeData,
            };

            setNodes((nds) => nds.concat(newNode));

            // Check for proximity to other nodes
            const nodeWidth = 60;
            const proximityThreshold = nodeWidth;

            const nearbyNodes = nodes.filter((node) => {
                const distance = Math.sqrt(
                    Math.pow(node.position.x - position.x, 2) + Math.pow(node.position.y - position.y, 2)
                );
                return distance <= proximityThreshold;
            });

            if (nearbyNodes.length > 0) {
                const nearestNode = nearbyNodes[0];
                const isCompatible = newNode.data.outputTypes.every((outputType) =>
                    nearestNode.data.inputTypes.includes(outputType)
                );

                if (isCompatible) {
                    const edgeLabel = `to ${nearestNode.data.label}`;
                    setEdges((eds) => addEdge({ source: newNode.id, target: nearestNode.id, type: 'custom', data: { text: edgeLabel } }, eds));
                }
            }
        },
        [project, setNodes, nodes, setEdges]
    );

    return (
        <Box sx={{
            display: 'flex',
            height: 'calc(100vh - 64px)',
            width: 'calc(100vw - 60px)',
            position: 'absolute',
            left: '60px',
            top: '64px',
        }}>
            <div style={{ flex: 1, height: '100%' }} ref={reactFlowWrapper}>
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onEdgeClick={onEdgeClick}
                    onDragOver={onDragOver}
                    onDrop={onDrop}
                    fitView
                    style={{ width: '100%', height: '100%' }}
                    minZoom={0.1}
                    maxZoom={4}
                    proOptions={{ hideAttribution: true }}
                    nodeTypes={nodeTypes}
                    edgeTypes={edgeTypes}
                >
                    <Background variant="dots" gap={12} size={1} />
                    <Controls />
                    <MiniMap position="bottom-right" />
                </ReactFlow>
            </div>
            <Sidebar />
            <Modal
                open={isEdgeModalOpen}
                onClose={() => setIsEdgeModalOpen(false)}
                aria-labelledby="edge-label-modal"
                aria-describedby="modal-to-edit-edge-label"
            >
                <Box sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: 400,
                    bgcolor: 'background.paper',
                    border: '2px solid #000',
                    boxShadow: 24,
                    p: 4,
                }}>
                    <TextField
                        fullWidth
                        label="Edge Label"
                        value={edgeLabel}
                        onChange={(e) => setEdgeLabel(e.target.value)}
                        sx={{ mb: 2 }}
                    />
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <Button onClick={() => setIsEdgeModalOpen(false)} sx={{ mr: 1 }}>Cancel</Button>
                        <Button onClick={onSaveEdgeLabel} variant="contained">Save</Button>
                    </Box>
                </Box>
            </Modal>
            <Modal
                open={isErrorModalOpen}
                onClose={() => setIsErrorModalOpen(false)}
                aria-labelledby="error-modal"
                aria-describedby="modal-to-show-error"
            >
                <Box sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: 400,
                    bgcolor: 'background.paper',
                    border: '2px solid #000',
                    boxShadow: 24,
                    p: 4,
                }}>
                    <Typography id="modal-modal-title" variant="h6" component="h2">
                        Error
                    </Typography>
                    <Typography id="modal-modal-description" sx={{ mt: 2 }}>
                        The output of the previous node is not compatible with the input of the destination node.
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <Button onClick={() => setIsErrorModalOpen(false)} variant="contained">OK</Button>
                    </Box>
                </Box>
            </Modal>
        </Box>
    );
};

const WrappedNewPipelinePage = () => (
    <ReactFlowProvider>
        <NewPipelinePage />
    </ReactFlowProvider>
);

export default WrappedNewPipelinePage;
