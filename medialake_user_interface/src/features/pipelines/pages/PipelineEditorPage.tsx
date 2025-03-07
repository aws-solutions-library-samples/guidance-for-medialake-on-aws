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
import type { NodesResponse } from '@/shared/nodes/types/nodes.types';
import {
    CustomNode,
    CustomEdge,
    Sidebar,
    NodeConfigurationForm,
    PipelineToolbar,
    JobStatusNode
} from '../components/PipelineEditor';
import type { PipelineToolbarProps } from '../components/PipelineEditor/PipelineToolbar';
import { Node as NodeType, NodeConfiguration, NodeMethod } from '../types';
import { RightSidebarProvider, useRightSidebar } from '@/components/common/RightSidebar/SidebarContext';
import { JOB_STATUS_NODE_TYPE } from '../components/PipelineEditor/jobStatusNodeUtils';

// Define the custom node data type
interface CustomNodeData {
    label: string;
    icon: React.ReactNode;
    inputTypes: string[];
    outputTypes: string[];
    nodeId: string;
    description: string;
    configuration?: any;
    onDelete?: (id: string) => void;
    onConfigure?: (id: string) => void;
    type?: string; // Node type (e.g., 'TRIGGER', 'INTEGRATION', 'FLOW')
}

const nodeTypes = {
    custom: CustomNode,
    jobStatusNode: JobStatusNode
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
        type: node.data.type,
        label: node.data.label,
        icon: {
            props: {
                size: 20
            }
        },
        inputTypes: node.data.inputTypes,
        outputTypes: node.data.outputTypes,
        configuration: node.data.configuration
    },
    positionAbsolute: node.positionAbsolute ? {
        x: node.positionAbsolute.x.toString(),
        y: node.positionAbsolute.y.toString()
    } : undefined,
    selected: node.selected,
    dragging: node.dragging
});

const convertApiResponseToNode = (response: NodesResponse): NodeType | null => {
    console.log('[PipelineEditorPage] convertApiResponseToNode called with:', response);
    if (!response || !response.data || !response.data[0]) {
        console.log('[PipelineEditorPage] Invalid response structure');
        return null;
    }

    const nodeData = response.data[0];
    console.log('[PipelineEditorPage] Node data from response:', nodeData);

    // Create a methods object with the config property
    const methods = nodeData.methods?.reduce((acc, method) => {
        console.log('[PipelineEditorPage] Processing method:', method);

        // Convert parameters to Record format
        const parameters = Array.isArray(method.parameters)
            ? method.parameters.reduce((paramAcc, param) => {
                const parameterData: any = {
                    name: param.name,
                    label: param.label,
                    type: param.schema.type === 'string' ? 'text' : param.schema.type as 'number' | 'boolean' | 'select',
                    required: param.required || false,
                    description: param.description
                };

                // Add options if they exist in the schema
                if (param.schema.options) {
                    parameterData.options = param.schema.options;
                }

                return {
                    ...paramAcc,
                    [param.name]: parameterData
                };
            }, {})
            : {};

        // Extract config from method using type assertion
        // For trigger nodes, the config is different from integration nodes
        const nodeType = nodeData.info?.nodeType;
        let config;

        if (nodeType === 'TRIGGER') {
            // For trigger nodes, use the method name as the operationId
            config = {
                path: '',
                operationId: method.name,
                parameters: (method as any).parameters || [],
                requestMapping: (method as any).requestMapping || null,
                responseMapping: (method as any).responseMapping || null
            };
        } else {
            // For integration nodes, extract from config property
            config = {
                path: (method as any).config?.path || '',
                operationId: (method as any).config?.operationId || '',
                parameters: (method as any).config?.parameters || [],
                requestMapping: (method as any).requestMapping || (method as any).config?.requestMapping || null,
                responseMapping: (method as any).responseMapping || (method as any).config?.responseMapping || null
            };
        }

        console.log('[PipelineEditorPage] Method config:', config);
        console.log('[PipelineEditorPage] Method:', method);

        // If method already exists, merge parameters
        if (acc[method.name]) {
            return {
                ...acc,
                [method.name]: {
                    ...acc[method.name],
                    parameters: { ...acc[method.name].parameters, ...parameters },
                    config: config // Add config property
                }
            };
        }

        // Add new method with config
        return {
            ...acc,
            [method.name]: {
                name: method.name,
                description: method.description || '',
                parameters,
                config: config // Add config property
            }
        };
    }, {} as Record<string, any>);

    const result = {
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
            // outputTypes: nodeData.info?.outputTypes || [],
            outputTypes: (nodeData.info?.outputTypes || []).map(item => String(item)),

            createdAt: nodeData.info?.createdAt || new Date().toISOString(),
        },
        methods: methods
    };

    console.log('[PipelineEditorPage] Converted node:', result);
    return result;
};

const PipelineEditorContent = () => {
    const navigate = useNavigate();
    const reactFlowWrapper = useRef<HTMLDivElement>(null);
    const { id: pipelineId } = useParams();
    const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const { screenToFlowPosition } = useReactFlow();
    const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);
    const [errorType, setErrorType] = useState<'trigger' | 'compatibility'>('compatibility');
    const [selectedNode, setSelectedNode] = useState<Node<CustomNodeData> | null>(null);
    const [isNodeConfigOpen, setIsNodeConfigOpen] = useState(false);
    const { isExpanded } = useRightSidebar();

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

    // Fetch all pipelines when the component mounts


    const { data: pipeline } = useGetPipeline(pipelineId || '', {
        enabled: !!pipelineId && pipelineId !== 'new'
    });

    // Only fetch node details when the dialog is open and we have a selected node
    // Store the nodeId in a ref to prevent unnecessary re-renders
    const nodeIdRef = React.useRef<string>('');

    // Only update the nodeId when the dialog opens or closes
    React.useEffect(() => {
        if (isNodeConfigOpen && selectedNode?.data?.nodeId) {
            nodeIdRef.current = selectedNode.data.nodeId;
        } else if (!isNodeConfigOpen) {
            nodeIdRef.current = '';
        }
    }, [isNodeConfigOpen, selectedNode]);

    const { data: nodeDetails, isLoading: isNodeDetailsLoading } = useGetNode(nodeIdRef.current, {
        enabled: isNodeConfigOpen && !!nodeIdRef.current
    });

    // Memoize the converted node data to prevent unnecessary recalculations
    const convertedNodeData = React.useMemo(() =>
        nodeDetails ? (convertApiResponseToNode(nodeDetails) || {} as NodeType) : ({} as NodeType),
        [nodeDetails]
    );

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
                edges: prev.configuration.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
                settings: prev.configuration.settings || {
                    autoStart: false,
                    retryAttempts: 3,
                    timeout: 3600
                }
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
            const targetNode = nodes.find((node) => node.id === connection.target);

            // Prevent connections to trigger nodes
            if (targetNode?.data.type?.includes('TRIGGER')) {
                setErrorType('trigger');
                setIsErrorModalOpen(true);
                return;
            }

            // DO NOT DELETE - Input/Output validation will be enabled later
            /*
            const sourceNode = nodes.find((node) => node.id === connection.source);
            if (sourceNode && targetNode) {
                const isCompatible =
                    sourceNode.data.outputTypes &&
                    targetNode.data.inputTypes &&
                    sourceNode.data.outputTypes.some((outputType: string) =>
                        targetNode.data.inputTypes.includes(outputType)
                    );

                if (!isCompatible) {
                    setIsErrorModalOpen(true);
                    return;
                }
            }
            */

            const newEdge = {
                ...connection,
                id: `${connection.source}-${connection.target}`,
                type: 'custom',
                data: {
                    text: 'Connected'
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
        },
        [nodes, setEdges]
    );

    const onDrop = useCallback(
        async (event: React.DragEvent) => {
            event.preventDefault();

            if (!reactFlowWrapper.current) return;

            const nodeData = JSON.parse(event.dataTransfer.getData('application/reactflow'));
            console.log(nodeData)
            if (typeof nodeData === 'undefined' || !nodeData) {
                return;
            }

            const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
            const position = screenToFlowPosition({
                x: event.clientX - reactFlowBounds.left,
                y: event.clientY - reactFlowBounds.top,
            });

            // Check if this is our special job status node
            const isJobStatusNode = nodeData.customNodeType === 'jobStatusNode';
            
            const newReactFlowNode: Node<CustomNodeData> = {
                id: getId(),
                type: isJobStatusNode ? 'jobStatusNode' : 'custom',
                position,
                data: {
                    nodeId: nodeData.id,
                    label: nodeData.label || 'New Node',
                    description: nodeData.description || '',
                    icon: nodeData.icon || <FaFileVideo size={20} />,
                    inputTypes: nodeData.inputTypes || [],
                    outputTypes: nodeData.outputTypes || [],
                    type: nodeData.type,
                    configuration: nodeData.methodConfig || {
                        method: '',
                        path: '',
                        parameters: {},
                        operationId: '',
                        requestMapping: '',
                        responseMapping: ''
                    },
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
                    nodes: [...prev.configuration.nodes, newPipelineNode],
                    settings: prev.configuration.settings || {
                        autoStart: false,
                        retryAttempts: 3,
                        timeout: 3600
                    }
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

    const handleNodeConfigSave = useCallback(async (configuration: any) => {
        console.log('[PipelineEditorPage] handleNodeConfigSave called with:', configuration);
        console.log('[PipelineEditorPage] Configuration JSON:', JSON.stringify(configuration));
        try {
            if (selectedNode) {
                console.log('[PipelineEditorPage] Selected node:', selectedNode);
                // Update node in ReactFlow

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

                console.log('[PipelineEditorPage] Updated node:', updatedNode);
                console.log('[PipelineEditorPage] Updated node configuration:', updatedNode.data.configuration);

                // Update ReactFlow state
                setNodes((nds) => {
                    console.log('[PipelineEditorPage] Current nodes:', nds);
                    const updatedNodes = nds.map((node) =>
                        node.id === selectedNode.id ? updatedNode : node
                    );
                    console.log('[PipelineEditorPage] Updated nodes:', updatedNodes);
                    return updatedNodes;
                });
                console.log('[PipelineEditorPage] Nodes updated');

                // Convert to pipeline node format and update form data
                const updatedPipelineNode = convertToPipelineNode(updatedNode);
                console.log('[PipelineEditorPage] Updated pipeline node:', updatedPipelineNode);
                console.log('[PipelineEditorPage] Updated pipeline node data:', updatedPipelineNode.data);

                // Update pipeline configuration in form data
                setFormData(prev => {
                    console.log('[PipelineEditorPage] Previous form data:', prev);
                    const updatedNodes = prev.configuration.nodes.map(node =>
                        node.id === selectedNode.id ? updatedPipelineNode : node
                    );
                    console.log('[PipelineEditorPage] Updated nodes in form data:', updatedNodes);

                    const newFormData = {
                        ...prev,
                        configuration: {
                            ...prev.configuration,
                            nodes: updatedNodes,
                            settings: prev.configuration.settings || {
                                autoStart: false,
                                retryAttempts: 3,
                                timeout: 3600
                            }
                        }
                    };
                    console.log('[PipelineEditorPage] New form data:', newFormData);
                    return newFormData;
                });
                console.log('[PipelineEditorPage] Form data updated');
            }

            // Close the dialog
            console.log('[PipelineEditorPage] Closing node config dialog');
            handleNodeConfigClose();
        } catch (error) {
            console.error('[PipelineEditorPage] Error saving node configuration:', error);
            // Don't close the dialog on error so the user can try again
        }
    }, [selectedNode, setNodes, handleNodeConfigClose]);

    const convertNodeToReactFlowNode = (node: NodeType): Node<CustomNodeData> => ({
        id: node.nodeId || getId(),
        type: 'custom',
        position: { x: 0, y: 0 },
        data: {
            nodeId: node.nodeId || '',
            label: node.info.title,
            description: node.info.description || '',
            icon: <FaFileVideo size={20} />,
            inputTypes: node.info.inputTypes || [],
            outputTypes: node.info.outputTypes || [],
            configuration: null,
        },
    });

    return (
        <Box sx={{
            width: '100vw',
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            margin: 0,
            padding: 0
        }}>
            <PipelineToolbar
                onSave={handleSave}
                isLoading={createPipeline.isPending || updatePipeline.isPending}
                pipelineName={formData.name}
                onPipelineNameChange={(value) => setFormData(prev => ({ ...prev, name: value }))}
            />
            <Box sx={{
                position: 'fixed',
                overflow: 'hidden',
                height: 'calc(100vh - 64px)',
                width: '100%',
                left: 0,
                top: 64,
                right: 0,
                bottom: 0
            }}>
                <Box sx={{
                    position: 'absolute',
                    right: 0,
                    top: 0,
                    bottom: 0,
                    width: isExpanded ? '300px' : '0px',
                    transition: theme => theme.transitions.create(['width'], {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    zIndex: 2
                }}>
                    <Sidebar />
                </Box>
                <Box ref={reactFlowWrapper} sx={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    right: isExpanded ? '300px' : 0,
                    bottom: 0,
                    transition: theme => theme.transitions.create(['right'], {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    zIndex: 1
                }}>
                    <ReactFlow
                        style={{
                            width: '100%',
                            height: '100%',
                            margin: 0,
                            padding: 0,
                            position: 'absolute',
                            left: 0,
                            top: 0,
                            right: 0,
                            bottom: 0
                        }}
                        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
                        minZoom={0.1}
                        maxZoom={4}
                        snapToGrid={true}
                        snapGrid={[16, 16]}
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        nodeTypes={nodeTypes}
                        edgeTypes={edgeTypes}
                        onDrop={onDrop}
                        onDragOver={(event) => event.preventDefault()}
                        fitView={false}
                        connectionRadius={100}
                        connectOnClick={true}
                    >
                        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                        <Controls />
                        <MiniMap />
                    </ReactFlow>
                </Box>
            </Box>

            <Dialog
                open={isNodeConfigOpen}
                onClose={() => setIsNodeConfigOpen(false)}
                maxWidth="sm"
                PaperProps={{
                    sx: {
                        width: '400px'
                    }
                }}
            >
                <DialogTitle>Configure Node</DialogTitle>
                <DialogContent>
                    {selectedNode && !isNodeDetailsLoading && nodeDetails && (
                        <NodeConfigurationForm
                            node={convertedNodeData}
                            configuration={selectedNode.data.configuration}
                            onSubmit={handleNodeConfigSave}
                            onCancel={() => setIsNodeConfigOpen(false)}
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
                        {errorType === 'trigger'
                            ? "Trigger nodes cannot have incoming connections. They can only trigger other nodes."
                            : "The nodes cannot be connected because their input/output types are not compatible."}
                    </Typography>
                </Box>
            </Modal>
        </Box>
    );
};

const PipelineEditorPage = () => (
    <RightSidebarProvider>
        <ReactFlowProvider>
            <PipelineEditorContent />
        </ReactFlowProvider>
    </RightSidebarProvider>
);

export default PipelineEditorPage;
