import React, { useCallback, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    ReactFlowProvider,
    useReactFlow,
    BackgroundVariant,
    Connection,
    Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Box, Modal, Typography, TextField, Stack, Dialog, DialogTitle, DialogContent, Button } from '@mui/material';
import { FaFileVideo } from 'react-icons/fa';
import { useGetPipeline, useCreatePipeline, useUpdatePipeline } from '../api/pipelinesController';
import { useGetNode } from '@/shared/nodes/api/nodesController';
import type { Pipeline, CreatePipelineDto, PipelineEdge, PipelineNode } from '../types/pipelines.types';
import type { NodesResponse, Node as ApiNode, NodeInfo, NodeAuth, NodeMethod } from '@/shared/nodes/types/nodes.types';
import {
    CustomNode,
    CustomEdge,
    Sidebar,
    NodeConfigurationForm,
    PipelineToolbar,
} from '../components/PipelineEditor';
import type { PipelineToolbarProps } from '../components/PipelineEditor/PipelineToolbar';

// Define the custom node data type
interface CustomNodeData {
    label: string;
    icon: React.ReactNode;
    inputTypes: string[];
    outputTypes: string[];
    nodeId: string;
    configuration?: any;
    onDelete?: (id: string) => void;
    onConfigure?: (id: string) => void;
}

const nodeTypes = {
    custom: CustomNode,
};

const edgeTypes = {
    custom: CustomEdge,
};

let id = 0;
const getId = () => `dndnode_${id++}`;

const convertToPipelineNode = (node: Node<CustomNodeData>): PipelineNode => ({
    id: node.id,
    type: node.type || 'custom',
    position: {
        x: node.position.x.toString(),
        y: node.position.y.toString()
    },
    width: node.width?.toString() || '180',
    height: node.height?.toString() || '40',
    data: {
        id: node.data.nodeId,
        type: 'default',
        label: node.data.label,
        icon: {
            props: {
                size: 20
            }
        },
        inputTypes: node.data.inputTypes,
        outputTypes: node.data.outputTypes
    },
    positionAbsolute: node.positionAbsolute ? {
        x: node.positionAbsolute.x.toString(),
        y: node.positionAbsolute.y.toString()
    } : undefined,
    selected: node.selected,
    dragging: node.dragging
});

const convertApiResponseToNode = (response: NodesResponse): ApiNode | null => {
    if (!response || !response.data || !response.data[0]) {
        return null;
    }

    const nodeData = response.data[0];
    return {
        nodeId: nodeData.nodeId,
        info: {
            enabled: nodeData.info?.enabled || false,
            categories: nodeData.info?.categories || [],
            updatedAt: nodeData.info?.updatedAt || new Date().toISOString(),
            nodeType: nodeData.info?.nodeType || 'default',
            iconUrl: nodeData.info?.iconUrl || '',
            description: nodeData.info?.description || '',
            tags: nodeData.info?.tags || [],
            title: nodeData.info?.title || '',
            inputTypes: nodeData.info?.inputTypes || [],
            outputTypes: nodeData.info?.outputTypes || [],
            createdAt: nodeData.info?.createdAt || new Date().toISOString(),
        },
        auth: {
            authMethod: nodeData.auth?.authMethod || 'none',
            authConfig: nodeData.auth?.authConfig || {
                type: '',
                parameters: {
                    type: '',
                    name: '',
                    in: '',
                }
            },
        },
        methods: nodeData.methods || [],
    };
};

const PipelineEditorContent = () => {
    const navigate = useNavigate();
    const reactFlowWrapper = useRef<HTMLDivElement>(null);
    const { id: pipelineId } = useParams();
    const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { screenToFlowPosition } = useReactFlow();
    const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);
    const [selectedNode, setSelectedNode] = useState<Node<CustomNodeData> | null>(null);
    const [isNodeConfigOpen, setIsNodeConfigOpen] = useState(false);

    const [formData, setFormData] = React.useState<CreatePipelineDto>({
        name: '',
        description: '',
        configuration: {
            nodes: [],
            edges: [],
            settings: {
                autoStart: false,
                retryAttempts: 3,
                timeout: 3600
            }
        }
    });

    const { data: pipeline } = useGetPipeline(pipelineId || '', {
        enabled: !!pipelineId && pipelineId !== 'new'
    });

    const { data: nodeDetails, isLoading: isNodeDetailsLoading } = useGetNode(selectedNode?.data?.nodeId || '');

    const createPipeline = useCreatePipeline({
        onSuccess: () => {
            navigate('/pipelines');
        }
    });

    const updatePipeline = useUpdatePipeline({
        onSuccess: () => {
            navigate('/pipelines');
        }
    });

    // Set form data when pipeline data is loaded
    React.useEffect(() => {
        if (pipeline) {
            setFormData({
                name: pipeline.name,
                description: pipeline.description,
                configuration: pipeline.configuration
            });
        }
    }, [pipeline]);

    const handleSave = async () => {
        if (pipelineId && pipelineId !== 'new') {
            updatePipeline.mutate({ id: pipelineId, data: formData });
        } else {
            createPipeline.mutate(formData);
        }
    };

    const onDeleteNode = useCallback((nodeId: string) => {
        setNodes((nds) => nds.filter((node) => node.id !== nodeId));
        setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));

        // Update pipeline configuration
        setFormData(prev => ({
            ...prev,
            configuration: {
                ...prev.configuration,
                nodes: prev.configuration.nodes.filter((node) => node.id !== nodeId),
                edges: prev.configuration.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
            }
        }));
    }, [setNodes, setEdges]);

    const onConfigureNode = useCallback((nodeId: string) => {
        const node = nodes.find((n) => n.id === nodeId);
        if (node) {
            setSelectedNode(node);
            setIsNodeConfigOpen(true);
        }
    }, [nodes]);

    // Update existing nodes with handlers
    React.useEffect(() => {
        setNodes((nds) =>
            nds.map((node) => ({
                ...node,
                data: {
                    ...node.data,
                    onDelete: onDeleteNode,
                    onConfigure: onConfigureNode,
                },
            }))
        );
    }, [onDeleteNode, onConfigureNode, setNodes]);

    const onConnect = useCallback(
        (connection: Connection) => {
            const sourceNode = nodes.find((node) => node.id === connection.source);
            const targetNode = nodes.find((node) => node.id === connection.target);

            if (sourceNode && targetNode) {
                const isCompatible =
                    sourceNode.data.outputTypes &&
                    targetNode.data.inputTypes &&
                    sourceNode.data.outputTypes.some((outputType: string) =>
                        targetNode.data.inputTypes.includes(outputType)
                    );

                if (isCompatible) {
                    const newEdge = {
                        ...connection,
                        id: `${connection.source}-${connection.target}`,
                        type: 'custom',
                        data: {
                            text: `${sourceNode.data.label} to ${targetNode.data.label}`
                        }
                    } as PipelineEdge;

                    setEdges((eds) => addEdge(newEdge, eds));

                    // Update pipeline configuration
                    setFormData(prev => ({
                        ...prev,
                        configuration: {
                            ...prev.configuration,
                            edges: [...prev.configuration.edges, newEdge]
                        }
                    }));
                } else {
                    setIsErrorModalOpen(true);
                }
            }
        },
        [nodes, setEdges]
    );

    const onDrop = useCallback(
        async (event: React.DragEvent) => {
            event.preventDefault();

            if (!reactFlowWrapper.current) return;

            const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));

            if (typeof nodeData === 'undefined' || !nodeData) {
                return;
            }

            const position = screenToFlowPosition({
                x: event.clientX,
                y: event.clientY,
            });

            const newReactFlowNode: Node<CustomNodeData> = {
                id: getId(),
                type: 'custom',
                position,
                data: {
                    nodeId: nodeData.id,
                    label: nodeData.label || 'New Node',
                    icon: nodeData.icon || <FaFileVideo size={20} />,
                    inputTypes: nodeData.inputTypes || [],
                    outputTypes: nodeData.outputTypes || [],
                    configuration: null,
                }
            };

            const newPipelineNode = convertToPipelineNode(newReactFlowNode);

            // Update the node with handlers before adding it
            const nodeWithHandlers = {
                ...newReactFlowNode,
                data: {
                    ...newReactFlowNode.data,
                    onDelete: onDeleteNode,
                    onConfigure: onConfigureNode,
                }
            };

            setNodes((nds) => nds.concat(nodeWithHandlers));

            // Update pipeline configuration
            setFormData(prev => ({
                ...prev,
                configuration: {
                    ...prev.configuration,
                    nodes: [...prev.configuration.nodes, newPipelineNode]
                }
            }));

            // Automatically open configuration dialog for the new node
            setSelectedNode(nodeWithHandlers);
            setIsNodeConfigOpen(true);
        },
        [screenToFlowPosition, setNodes, onDeleteNode, onConfigureNode]
    );

    const handleNodeConfigClose = useCallback(() => {
        setIsNodeConfigOpen(false);
        setSelectedNode(null);
    }, []);

    const handleNodeConfigSave = useCallback((configuration: any) => {
        if (selectedNode) {
            const updatedNode = {
                ...selectedNode,
                data: {
                    ...selectedNode.data,
                    configuration,
                    label: configuration.method
                        ? `${selectedNode.data.label} (${configuration.method})`
                        : selectedNode.data.label
                }
            };

            setNodes((nds) =>
                nds.map((node) =>
                    node.id === selectedNode.id ? updatedNode : node
                )
            );

            // Update pipeline configuration
            setFormData(prev => ({
                ...prev,
                configuration: {
                    ...prev.configuration,
                    nodes: prev.configuration.nodes.map(node =>
                        node.id === selectedNode.id
                            ? convertToPipelineNode(updatedNode)
                            : node
                    )
                }
            }));
        }
        handleNodeConfigClose();
    }, [selectedNode, setNodes]);

    const convertNodeToReactFlowNode = (apiNode: ApiNode): Node<CustomNodeData> => ({
        id: apiNode.nodeId || getId(),
        type: 'custom',
        position: { x: 0, y: 0 },
        data: {
            nodeId: apiNode.nodeId || '',
            label: apiNode.info.title,
            icon: <FaFileVideo size={20} />,
            inputTypes: apiNode.info.inputTypes || [],
            outputTypes: apiNode.info.outputTypes || [],
            configuration: null,
        },
    });

    return (
        <Box sx={{ width: '100%', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <PipelineToolbar
                onSave={handleSave}
                isLoading={createPipeline.isPending || updatePipeline.isPending}
                pipelineName={formData.name}
                onPipelineNameChange={(value) => setFormData(prev => ({ ...prev, name: value }))}
            />
            <Box sx={{ flex: 1, display: 'flex' }}>
                <Box ref={reactFlowWrapper} sx={{ flex: 1, height: '100%' }}>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        nodeTypes={nodeTypes}
                        edgeTypes={edgeTypes}
                        onDrop={onDrop}
                        onDragOver={(event) => event.preventDefault()}
                        fitView
                    >
                        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                        <Controls />
                        <MiniMap />
                    </ReactFlow>
                </Box>
                <Sidebar />
            </Box>

            <Dialog open={isNodeConfigOpen} onClose={() => setIsNodeConfigOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>Configure Node</DialogTitle>
                <DialogContent>
                    {selectedNode && !isNodeDetailsLoading && nodeDetails && (
                        <NodeConfigurationForm
                            node={selectedNode}
                            nodeDetails={convertApiResponseToNode(nodeDetails) as ApiNode}
                            onCancel={() => setIsNodeConfigOpen(false)}
                            onSave={(updatedNode) => {
                                setNodes((nds) =>
                                    nds.map((n) => (n.id === updatedNode.id ? updatedNode : n))
                                );
                                setIsNodeConfigOpen(false);
                            }}
                        />
                    )}
                </DialogContent>
            </Dialog>

            <Modal
                open={isErrorModalOpen}
                onClose={() => setIsErrorModalOpen(false)}
                aria-labelledby="modal-modal-title"
                aria-describedby="modal-modal-description"
            >
                <Box sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: 400,
                    bgcolor: 'background.paper',
                    boxShadow: 24,
                    p: 4,
                }}>
                    <Typography id="modal-modal-title" variant="h6" component="h2">
                        Connection Error
                    </Typography>
                    <Typography id="modal-modal-description" sx={{ mt: 2 }}>
                        The nodes cannot be connected because their input/output types are not compatible.
                    </Typography>
                </Box>
            </Modal>
        </Box>
    );
};

const PipelineEditorPage = () => (
    <ReactFlowProvider>
        <PipelineEditorContent />
    </ReactFlowProvider>
);

export default PipelineEditorPage; 