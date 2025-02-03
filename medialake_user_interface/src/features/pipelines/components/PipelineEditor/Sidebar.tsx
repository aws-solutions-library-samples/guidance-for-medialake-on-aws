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

interface NodeSection {
    title: string;
    types: string[];
    nodes: Array<{node: NodeType; methodName: string; method: any}>;
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

    const sections = useMemo(() => {
        if (!nodesResponse?.data) return [];

        const groupedNodes: NodeSection[] = [
            { title: 'Triggers', types: ['TRIGGER'], nodes: [] },
            { title: 'Integrations', types: ['API', 'INTEGRATION'], nodes: [] },
            { title: 'Flow', types: ['FLOW'], nodes: [] }
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
