import React, { useState, useMemo } from 'react';
import {
    Box,
    Typography,
    Paper,
    CircularProgress,
    TextField,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Divider
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useGetUnconfiguredNodeMethods } from '@/shared/nodes/api/nodesController';
import { Node as NodeType } from '@/shared/nodes/types/nodes.types';
import { RightSidebar } from '@/components/common/RightSidebar/RightSidebar';
import { createJobStatusNodeData } from './jobStatusNodeUtils';

interface NodeSection {
    title: string;
    types: string[];
    nodes: Array<{ node: NodeType; methodName: string; method: any }>;
}

const SidebarContent: React.FC = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedSections, setExpandedSections] = useState<string[]>(['TRIGGER']);
    const { data: nodesResponse, isLoading, error } = useGetUnconfiguredNodeMethods();

    const handleSectionToggle = (sectionId: string) => {
        setExpandedSections(prev => {
            if (prev.includes(sectionId)) {
                return prev.filter(type => type !== sectionId);
            }
            return [...prev, sectionId];
        });
    };

    const onDragStart = (event: React.DragEvent, node: NodeType, methodName: string) => {
        console.log('[Sidebar] onDragStart for node:', node.nodeId, 'method:', methodName);
        console.log('[Sidebar] Node methods:', node.methods);

        // For trigger nodes, we need to use "trigger" as the method name
        let actualMethodName = methodName;
        if (node.info.nodeType === 'TRIGGER') {
            actualMethodName = 'trigger';
            console.log('[Sidebar] Using "trigger" as method name for trigger node');
        } else if (node.info.nodeType === 'INTEGRATION') {
            // For integration nodes, we need to use the actual method name (post, get, etc.)
            // The methodName parameter might be an index, so we need to get the actual method name
            if (Array.isArray(node.methods)) {
                const methodObj = node.methods[parseInt(methodName)] as any;
                if (methodObj && methodObj.name) {
                    actualMethodName = methodObj.name;
                    console.log('[Sidebar] Using method name from array:', actualMethodName);
                }
            } else if (typeof node.methods === 'object') {
                // If methods is an object, the keys might be the method names
                // But we need to check if the value has a name property
                const methodObj = node.methods[methodName] as any;
                if (methodObj && methodObj.name) {
                    actualMethodName = methodObj.name;
                    console.log('[Sidebar] Using method name from object:', actualMethodName);
                }
            }
        }

        // Find the method in the methods array or object
        let method;
        if (Array.isArray(node.methods)) {
            method = node.methods.find((m: any) => m.name === actualMethodName);
            if (!method && !isNaN(parseInt(methodName))) {
                // If method not found by name but methodName is a number, use it as an index
                method = node.methods[parseInt(methodName)];
            }
        } else if (typeof node.methods === 'object') {
            method = node.methods[methodName];
            if (!method) {
                // Try to find by name in the object values
                const methods = Object.values(node.methods);
                method = methods.find((m: any) => m.name === actualMethodName);
            }
        }

        // Use type assertion to access the config property
        const methodWithConfig = method as any;
        console.log('[Sidebar] Method found:', methodWithConfig);

        // Set methodConfig based on node type
        let methodConfig;
        if (node.info.nodeType === 'TRIGGER') {
            // For trigger nodes, use the method name as the method
            // and get parameters from the config.parameters array
            methodConfig = {
                method: actualMethodName,
                parameters: methodWithConfig?.config?.parameters?.reduce((acc: any, param: any) => {
                    acc[param.name] = ''; // Initialize with empty values
                    return acc;
                }, {}) || {},
                requestMapping: null,
                responseMapping: null,
                path: '',
                operationId: '',
            };
            console.log('[Sidebar] Trigger node methodConfig:', methodConfig);
        } else {
            // For integration nodes, use the method name (post, get, etc.)
            methodConfig = {
                method: actualMethodName,
                parameters: methodWithConfig?.config?.parameters || {},
                requestMapping: methodWithConfig?.config?.requestMapping,
                responseMapping: methodWithConfig?.config?.responseMapping,
                path: methodWithConfig?.config?.path,
                operationId: methodWithConfig?.config?.operationId,
            };
            console.log('[Sidebar] Integration node methodConfig:', methodConfig);
        }

        const nodeData = {
            id: node.nodeId,
            type: node.info.nodeType,
            label: node.info.title,
            description: method?.description || node.info.description,
            inputTypes: node.info.inputTypes || [],
            outputTypes: node.info.outputTypes || [],
            methods: node.methods || {},
            icon: node.info.iconUrl,
            selectedMethod: actualMethodName,
            methodConfig: methodConfig,
        };

        console.log('[Sidebar] Node data for drag:', nodeData);

        event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeData));
        event.dataTransfer.effectAllowed = 'move';
    };

    // Handler for dragging the custom job status node
    const onDragStartJobStatus = (event: React.DragEvent) => {
        const nodeData = createJobStatusNodeData();
        event.dataTransfer.setData('application/reactflow', JSON.stringify({
            ...nodeData,
            customNodeType: 'jobStatusNode' // This helps identify it as a special node type
        }));
        event.dataTransfer.effectAllowed = 'move';
    };

    const sections = useMemo(() => {
        if (!nodesResponse?.data) return [];

        const groupedNodes: NodeSection[] = [
            { title: 'Triggers', types: ['TRIGGER'], nodes: [] },
            { title: 'Integrations', types: ['INTEGRATION'], nodes: [] },
            { title: 'Flow', types: ['FLOW'], nodes: [] },
            { title: 'Utilities', types: ['UTILITY'], nodes: [] }
        ];

        nodesResponse.data.forEach((node) => {
            if (node.methods) {
                Object.entries(node.methods).forEach(([methodName, method]) => {
                    const nodeType = node.info.nodeType;
                    const section = groupedNodes.find(s =>
                        s.types.some(type => nodeType.includes(type))
                    );

                    if (section) {
                        section.nodes.push({ node, methodName, method });
                    }
                });
            }
        });

        return groupedNodes;
    }, [nodesResponse?.data]);


    const filteredSections = useMemo(() => {
        return sections.map(section => ({
            ...section,
            nodes: section.nodes.filter(({ node, method }) => {
                const searchLower = searchQuery.toLowerCase();
                return (
                    node.info.title.toLowerCase().includes(searchLower) ||
                    (method.description || node.info.description).toLowerCase().includes(searchLower)
                );
            })
        }));
    }, [sections, searchQuery]);

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
        <Box sx={{ pt: 2 }}>
            <Box sx={{ px: 2, mb: 2 }}>
                <Typography
                    variant="h6"
                    gutterBottom
                    sx={{ textAlign: 'center', mb: 2 }}
                >
                    Available Nodes
                </Typography>

                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search nodes..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </Box>

            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                '& .MuiAccordion-root + .MuiAccordion-root': {
                    mt: -1
                }
            }}>
                {filteredSections.map((section) => (
                    <Accordion
                        key={section.types[0]}
                        expanded={expandedSections.includes(section.types[0])}
                        onChange={() => handleSectionToggle(section.types[0])}
                        disableGutters
                        sx={{
                            '&.MuiAccordion-root': {
                                boxShadow: 'none',
                                '&:before': {
                                    display: 'none',
                                },
                                width: '100%',
                                margin: 0
                            }
                        }}
                    >
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon sx={{ fontSize: '0.9rem' }} />}
                            sx={{
                                minHeight: '36px',
                                py: 0,
                                px: 2,
                                backgroundColor: 'background.default',
                                borderBottom: '1px solid',
                                borderColor: 'divider',
                                width: '100%',
                                margin: 0,
                                '& .MuiAccordionSummary-content': {
                                    margin: '6px 0',
                                }
                            }}
                        >
                            <Typography
                                sx={{
                                    fontWeight: 500,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.1em',
                                    fontSize: '0.75rem',
                                    color: 'text.secondary'
                                }}
                            >
                                {section.title}
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ p: 2 }}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                {/* If this is the Utilities section, add our custom Job Status node */}
                                {section.types[0] === 'UTILITY' && (
                                    <Paper
                                        elevation={2}
                                        onDragStart={onDragStartJobStatus}
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
                                                Check Job Status
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            Checks the status of a job and routes based on completion status
                                        </Typography>
                                    </Paper>
                                )}
                                
                                {/* Render existing nodes */}
                                {section.nodes.map(({ node, methodName, method }) => (
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
                                    </Paper>
                                ))}
                            </Box>
                        </AccordionDetails>
                    </Accordion>
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
