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
    Edge,
    Position,
    BackgroundVariant,  // Add this import
    EdgeTypes,  // Add this import
    EdgeProps,  // Add this import
    Connection,  // Add this import
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Box, Modal, TextField, Button, IconButton, Select, MenuItem, Typography } from '@mui/material';
import { FaAmazon, FaVideo, FaDatabase, FaFileVideo, FaFileAudio, FaFileImage, FaPencilAlt, FaTrash, FaRobot, FaCloud, FaBrain } from 'react-icons/fa';
import { useLocation, useParams } from 'react-router-dom';

// Define the type for your custom edge data
interface CustomEdgeData {
    text: string;
}

interface SavePipelineButtonProps {
    onClick: () => void;
}

const SavePipelineButton: React.FC<SavePipelineButtonProps> = ({ onClick }) => {
    return (
        <div
            style={{
                position: 'absolute',
                right: 10,
                top: 10,
                zIndex: 4,
                backgroundColor: '#0972d3',
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
            }}
            onClick={onClick}
        >
            Save
        </div>
    );
};

interface PipelineNameInputProps {
    value: string;
    onChange: (newValue: string) => void;
}

const PipelineNameInput: React.FC<PipelineNameInputProps> = ({ value, onChange }) => {
    return (
        <Box
            style={{
                position: 'absolute',
                left: 10,
                top: 10,
                zIndex: 4,
                backgroundColor: 'white',
                color: 'black',
                border: 'none',
                padding: '8px 16px',
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
            }}
            sx={{ p: 2 }}
        >
            <TextField
                label="Pipeline Name"
                variant="outlined"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                sx={{ width: '300px' }}
            />
        </Box>
    );
};

const CustomNode = ({ data, id }: { data: any, id: string }) => {
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
                <Handle type="target" position={Position.Left} />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    {data.icon}
                    <div style={{ marginTop: '2px', fontSize: '10px', textAlign: 'center' }}>{data.label}</div>
                </div>
                <Handle type="source" position={Position.Right} />
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

// Update the CustomEdge component with proper typing
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
}: EdgeProps<CustomEdgeData>) => {
    const [edgePath] = getBezierPath({  // Add array destructuring here
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
                key={id}
                className="react-flow__edge-path"
                d={edgePath}  // This will now be a string
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

// Now the edgeTypes can be properly typed
const edgeTypes: EdgeTypes = {
    custom: CustomEdge,
};

let id = 0;
const getId = () => `dndnode_${id++}`;

const Sidebar = ({ pipelineName, setPipelineName }: { pipelineName: string, setPipelineName: (name: string) => void }) => {
    const onDragStart = (event, nodeType) => {
        const nodeData = {
            id: nodeType.id,
            type: nodeType.type,
            label: nodeType.label,
            icon: nodeType.icon.type.name,
            inputTypes: nodeType.inputTypes,
            outputTypes: nodeType.outputTypes
        };
        event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeData));
        event.dataTransfer.effectAllowed = 'move';
    };

    return (
        <aside style={{ padding: '15px', borderLeft: '1px solid #ccc', height: '100%', width: '200px', overflowY: 'auto' }}>
            {/* <TextField
                label="Pipeline Name"
                variant="outlined"
                value={pipelineName}
                onChange={(e) => setPipelineName(e.target.value)}
                sx={{ width: '100%', mb: 2 }}
            /> */}
            <Typography variant="subtitle1" sx={{ mb: 1 }}>Drag nodes to the pane</Typography>
            <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {[
                    { id: '60fb5fc1-372a-45e8-8767-f1690d5bc5bb', type: 'videoasset', label: 'Video Asset', icon: <FaFileVideo size={20} />, inputTypes: ['video'], outputTypes: ['video'] },
                    { id: '71366379-46c5-4583-8400-25002bf01b5c', type: 'audioasset', label: 'Audio Asset', icon: <FaFileAudio size={20} />, inputTypes: ['audio'], outputTypes: ['audio'] },
                    { id: '03c23094-d405-4aa7-a243-5a7a8f71d4a5', type: 'imageasset', label: 'Image Asset', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                    { id: '9cd66662-884a-4010-b230-8a2c440e675e', type: 'mediaconvert', label: 'MediaConvert', icon: <FaVideo size={20} />, inputTypes: ['video', 'audio'], outputTypes: ['video', 'audio'] },
                    { id: '9408d6dc-021b-46c1-b22c-19e4721b7d44', type: 'twelvelabs', label: 'TwelveLabs', icon: <FaDatabase size={20} />, inputTypes: ['video'], outputTypes: ['metadata'] },
                    { id: '14a670a0-967d-452c-9e0e-cf2f9e92d634', type: 'medialake', label: 'MediaLake', icon: <FaAmazon size={20} />, inputTypes: ['video', 'audio', 'image', 'metadata'], outputTypes: [] },
                    { id: '57207390-4b93-4c07-a1cc-e4733710b842', type: 'imagemetadata', label: 'Image Metadata', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                    { id: '9361ac53-13e9-4358-adde-3e4cd023954f', type: 'imageproxy', label: 'Image Proxy', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                    { id: '6773f9ef-2161-42c1-9485-11ef1c23f3b4', type: 'imagethumbnail', label: 'Image Thumbnail', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                    // { type: 'bedrockautomation', label: 'Bedrock Data Automation', icon: <FaRobot size={20} />, inputTypes: ['data'], outputTypes: ['data'] },
                    // { type: 'media2cloud', label: 'Media2Cloud', icon: <FaCloud size={20} />, inputTypes: ['video', 'audio', 'image'], outputTypes: ['metadata'] },
                    // { type: 'bedrockClaude', label: 'Bedrock Claude', icon: <FaBrain size={20} />, inputTypes: ['text'], outputTypes: ['text'] },
                    // { type: 'briaAI', label: 'Bria.AI', icon: <FaBrain size={20} />, inputTypes: ['image'], outputTypes: ['image'] },
                ].map((item) => (
                    <div
                        key={item.id}
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
                        onDragStart={(event) => onDragStart(event, item)}
                        draggable
                    >
                        {item.icon}
                        <div style={{ marginTop: '5px', fontSize: '10px', textAlign: 'center' }}>{item.label}</div>
                    </div>
                ))}
            </div>
        </aside>
    );
};

const NewPipelinePage = () => {
    const reactFlowWrapper = useRef(null);
    const { id } = useParams(); // Get the pipeline ID from the URL
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { project } = useReactFlow();
    const [isEdgeModalOpen, setIsEdgeModalOpen] = useState(false);
    const [selectedEdge, setSelectedEdge] = useState(null);
    const [edgeLabel, setEdgeLabel] = useState('');
    const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);
    const [pipelineName, setPipelineName] = useState('untitled');
    const [rfInstance, setRfInstance] = useState(null);

    useEffect(() => {
        // Fetch pipeline data based on the pipeline ID
        const fetchPipelineData = async () => {
            try {
                // Make an API call to fetch the pipeline data based on the ID
                // const response = await fetch(`/api/pipelines/${id}`);
                // const pipelineData = await response.json();

                // For demonstration purposes, let's use a predefined set of data
                const pipelineData = getPipelineDataById(id);

                // Set the nodes and edges based on the fetched pipeline data
                setNodes(pipelineData.nodes);
                setEdges(pipelineData.edges);
            } catch (error) {
                console.error('Error fetching pipeline data:', error);
            }
        };

        fetchPipelineData();
    }, [id, setNodes, setEdges]);

    const onSave = useCallback(() => {
        if (rfInstance) {
            const flow = rfInstance.toObject();
            console.log(flow);
        }
    }, [rfInstance]);

    const onConnect = useCallback(
        (connection: Connection) => {  // Change type from Edge to Connection
            const sourceNode = nodes.find((node) => node.id === connection.source);
            const targetNode = nodes.find((node) => node.id === connection.target);

            if (sourceNode && targetNode) {
                const isCompatible =
                    sourceNode.data.outputTypes &&
                    targetNode.data.inputTypes &&
                    sourceNode.data.outputTypes.every((outputType) =>
                        targetNode.data.inputTypes.includes(outputType)
                    );

                if (isCompatible) {
                    const edgeLabel = `to ${targetNode.data.label}`;
                    setEdges((eds) => addEdge({
                        ...connection,
                        type: 'custom',
                        data: { text: edgeLabel }
                    }, eds));
                } else {
                    setIsErrorModalOpen(true);
                }
            }
        },
        [nodes, setEdges]
    );

    const onEdgeClick = useCallback((event: React.MouseEvent, edge: Edge) => {
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

    const onDragOver = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback(
        (event: React.DragEvent) => {
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

            // Reconstruct the icon component
            const IconComponent =
                nodeData.icon === 'FaFileVideo' ? FaFileVideo :
                    nodeData.icon === 'FaVideo' ? FaVideo :
                        nodeData.icon === 'FaDatabase' ? FaDatabase :
                            nodeData.icon === 'FaAmazon' ? FaAmazon :
                                nodeData.icon === 'FaFileAudio' ? FaFileAudio :
                                    nodeData.icon === 'FaFileImage' ? FaFileImage :
                                        nodeData.icon === 'FaRobot' ? FaRobot :
                                            nodeData.icon === 'FaCloud' ? FaCloud :
                                                nodeData.icon === 'FaBrain' ? FaBrain :
                                                    nodeData.icon === 'FaBrain' ? FaBrain :
                                                        FaFileVideo; // Default to FaFileVideo if not found

            const newNode = {
                id: getId(),
                type: 'custom',
                position,
                data: {
                    ...nodeData,
                    icon: <IconComponent size={20} />
                },
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
                    const newEdge = {
                        id: `e${newNode.id}-${nearestNode.id}`,
                        source: newNode.id,
                        target: nearestNode.id,
                        type: 'custom',
                        data: { text: edgeLabel }
                    };
                    setEdges((eds) => addEdge(newEdge, eds));
                }
            }
        },
        [project, setNodes, nodes, setEdges]
    );

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            height: 'calc(100vh - 64px)',
            width: 'calc(100vw - 60px)',
            position: 'absolute',
            left: '60px',
            top: '64px',
        }}>

            <PipelineNameInput
                value={pipelineName}
                onChange={setPipelineName}
            />
            <Box sx={{ display: 'flex', flex: 1 }}>
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
                        onInit={setRfInstance}
                        fitView={false} // prevents auto zoom on drop
                        style={{ width: '100%', height: '100%' }}
                        minZoom={0.1}
                        maxZoom={4}
                        // zoomOnScroll={false}
                        // zoomOnPinch={false}
                        // zoomOnDoubleClick={false}
                        proOptions={{ hideAttribution: true }}
                        nodeTypes={nodeTypes}
                        edgeTypes={edgeTypes}
                    >
                        <Background
                            variant={BackgroundVariant.Dots}
                            gap={12}
                            size={1}
                            color="#81818a"
                        />
                        <Controls />
                        <MiniMap position="bottom-right" />
                        <SavePipelineButton onClick={onSave} />
                    </ReactFlow>
                </div>
                <Sidebar
                    pipelineName={pipelineName}
                    setPipelineName={setPipelineName}
                />
            </Box>
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

// Helper function to get pipeline data based on the ID (for demonstration purposes)
const getPipelineDataById = (id: string) => {
    // Define a mapping of pipeline IDs to their corresponding data
    const pipelineData = {
        '1': {
            nodes: [
                { id: '1', type: 'custom', position: { x: 0, y: 0 }, data: { label: 'Video Asset', icon: <FaFileVideo size={20} />, inputTypes: ['video'], outputTypes: ['video'] } },
                { id: '2', type: 'custom', position: { x: 100, y: 100 }, data: { label: 'Node 2' } },
            ],
            edges: [{ id: 'e1-2', source: '1', target: '2', type: 'custom', data: { text: 'Edge 1' } }],
        },
        '2': {
            nodes: [
                { id: '1', type: 'custom', position: { x: 0, y: 0 }, data: { label: 'Image Asset', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] } },
                { id: '2', type: 'custom', position: { x: 200, y: 0 }, data: { label: 'Image Metadata', icon: <FaFileImage size={20} />, inputTypes: ['image'], outputTypes: ['image'] } },
                { id: '3', type: 'custom', position: { x: 400, y: 0 }, data: { label: 'MediaLake', icon: <FaAmazon size={20} />, inputTypes: ['image'], outputTypes: ['image'] } },
            ],
            edges: [
                { id: 'e1-2', source: '1', target: '2', type: 'custom', data: { text: 'Image Metadata' } },
                { id: 'e1-3', source: '2', target: '3', type: 'custom', data: { text: 'Store in MediaLake' } },
            ],
        },
    };

    return pipelineData[id] || { nodes: [], edges: [] };
};

const WrappedNewPipelinePage = () => (
    <ReactFlowProvider>
        <NewPipelinePage />
    </ReactFlowProvider>
);

export default WrappedNewPipelinePage;

