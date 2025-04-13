import React, { useRef, ChangeEvent, useState } from 'react';
import { ensureCorrectTypes } from '../../types';
import { Stack, Button, Tooltip, FormControlLabel, Box, CircularProgress, Backdrop } from '@mui/material';
import { IconSwitch } from '@/components/common';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import ToggleOffIcon from '@mui/icons-material/ToggleOff';
import DeleteIcon from '@mui/icons-material/Delete';
import { useNavigate } from 'react-router-dom';
import { PipelineNameInput } from './';
import { useSidebar } from '@/contexts/SidebarContext';
import { useRightSidebar, COLLAPSED_WIDTH } from '@/components/common/RightSidebar/SidebarContext';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ButtonGroup from '@mui/material/ButtonGroup';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Grow from '@mui/material/Grow';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
import { FaFileVideo } from 'react-icons/fa';
import type { Node, Edge, ReactFlowInstance } from 'reactflow';
import { IntegrationValidationService } from '../../services/integrationValidation.service';
import IntegrationValidationDialog from '../../components/IntegrationValidationDialog';
import type { InvalidNodeInfo, IntegrationMapping } from '../../services/integrationValidation.service';
import type { Integration } from '@/features/settings/integrations/types/integrations.types';
import { drawerWidth, collapsedDrawerWidth } from '@/constants';

export interface PipelineToolbarProps {
  onSave: () => Promise<void>;
  isLoading: boolean;
  pipelineName: string;
  onPipelineNameChange: (value: string) => void;
  reactFlowInstance: ReactFlowInstance | null;
  // New props to update the flow state
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  active: boolean; // New prop for pipeline active state
  onActiveChange: (active: boolean) => void; // New prop for handling active state changes
  // Add prop for updating formData with imported pipeline
  updateFormData?: (nodes: Node[], edges: Edge[]) => void;
  // Add prop for deleting pipeline
  onDelete?: () => void;
  // Add prop for pipeline status
  status?: string;
}

const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
  onSave,
  isLoading,
  pipelineName,
  onPipelineNameChange,
  reactFlowInstance,
  setNodes,
  setEdges,
  active,
  onActiveChange,
  updateFormData,
  onDelete,
  status,
}) => {
  const navigate = useNavigate();
  const { isCollapsed: isLeftSidebarCollapsed } = useSidebar();
  const { isExpanded: isRightSidebarExpanded, width } = useRightSidebar();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // State for integration validation
  const [validationDialogOpen, setValidationDialogOpen] = useState(false);
  const [invalidNodes, setInvalidNodes] = useState<InvalidNodeInfo[]>([]);
  const [availableIntegrations, setAvailableIntegrations] = useState<Integration[]>([]);
  const [importedFlow, setImportedFlow] = useState<any>(null);
  const [isImporting, setIsImporting] = useState(false);

  const handleCancel = () => {
    navigate('/pipelines');
  };

  const commonStyles = {
    backdropFilter: 'blur(8px)',
    bgcolor: (theme: any) => `${theme.palette.background.paper}CC`,
    '&:hover': {
      bgcolor: (theme: any) => `${theme.palette.background.paper}EE`,
    },
  };

  // Load a flow from a JSON file.
  const handleLoadFlow = (event: ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    const files = event.target.files;
    if (files && files.length > 0) {
      setIsImporting(true);
      
      // Extract the file name without extension to use as pipeline name
      const fileName = files[0].name;
      const pipelineNameFromFile = fileName.endsWith('.json')
        ? fileName.slice(0, -5) // Remove .json extension
        : fileName;
      
      // Update the pipeline name
      onPipelineNameChange(pipelineNameFromFile);
      
      fileReader.readAsText(files[0], 'UTF-8');
      fileReader.onload = async (e) => {
        try {
          const flow = JSON.parse(e.target?.result as string);
          if (flow) {
            // Store the imported flow temporarily
            setImportedFlow(flow);
            
            // Check if the flow uses the nodes/edges structure
            if (flow.nodes && flow.edges) {
              // Fix edges first to ensure proper connections
              const fixedEdges = flow.edges.map((edge: any) => {
                // Ensure edge has data field
                if (!edge.data) {
                  edge.data = { text: '' };
                }
                
                // Find the source node for this edge
                const sourceNode = flow.nodes.find((n: any) => n.id === edge.source);
                
                // Find the target node for this edge
                const targetNode = flow.nodes.find((n: any) => n.id === edge.target);
                
                // Fix Map node connections
                if (sourceNode && sourceNode.data && sourceNode.data.id === 'map') {
                  console.log('[PipelineToolbar] Fixing edge for Map node:', edge.id);
                  
                  if (targetNode) {
                    // Check if this is a connection to a Success node
                    if (targetNode.data && targetNode.data.id === 'success') {
                      // This should be the "Next" connection
                      edge.sourceHandle = 'Next';
                      console.log('[PipelineToolbar] Set sourceHandle to "Next" for edge to Success node');
                    } else {
                      // This should be the "Processor" connection
                      edge.sourceHandle = 'Processor';
                      console.log('[PipelineToolbar] Set sourceHandle to "Processor" for edge to processor node');
                    }
                  }
                }
                
                // Ensure all edges have proper targetHandle values
                if (!edge.targetHandle && targetNode) {
                  // Default to 'input-any' or the first available input type
                  if (targetNode.data && targetNode.data.inputTypes && targetNode.data.inputTypes.length > 0) {
                    const inputType = typeof targetNode.data.inputTypes[0] === 'string'
                      ? targetNode.data.inputTypes[0]
                      : 'any';
                    edge.targetHandle = `input-${inputType}`;
                    console.log(`[PipelineToolbar] Set targetHandle to "${edge.targetHandle}" for edge ${edge.id}`);
                  } else {
                    edge.targetHandle = 'input-any';
                    console.log(`[PipelineToolbar] Set default targetHandle to "input-any" for edge ${edge.id}`);
                  }
                }
                
                // Ensure all edges have proper sourceHandle values if not already set
                if (!edge.sourceHandle && sourceNode && sourceNode.data && sourceNode.data.outputTypes && sourceNode.data.outputTypes.length > 0) {
                  // Use the first available output type or a default value
                  try {
                    const outputType = sourceNode.data.outputTypes[0];
                    if (typeof outputType === 'string') {
                      edge.sourceHandle = outputType;
                    } else if (typeof outputType === 'object' && outputType !== null) {
                      // Try to access name property safely
                      const name = (outputType as any).name;
                      if (name) {
                        edge.sourceHandle = String(name);
                      } else {
                        // Default to first output type as string or 'default'
                        edge.sourceHandle = 'default';
                      }
                    } else {
                      edge.sourceHandle = 'default';
                    }
                    console.log(`[PipelineToolbar] Set sourceHandle to "${edge.sourceHandle}" for edge ${edge.id}`);
                  } catch (error) {
                    // Fallback to default if any error occurs
                    edge.sourceHandle = 'default';
                    console.log(`[PipelineToolbar] Set default sourceHandle for edge ${edge.id}`);
                  }
                }
                
                return edge;
              });
              
              // Now fix the nodes
              const fixedNodes = flow.nodes.map((node: any) => {
                // Fix Map node configuration
                if (node.data && node.data.id === 'map' && node.data.type === 'FLOW') {
                  console.log('[PipelineToolbar] Fixing Map node for import:', node.id);
                  
                  // Ensure the Map node has the correct configuration
                  if (!node.data.configuration) {
                    node.data.configuration = {};
                  }
                  
                  if (!node.data.configuration.parameters) {
                    node.data.configuration.parameters = {};
                  }
                  
                  // Set the ItemsPath to the correct value
                  node.data.configuration.parameters.ItemsPath = '$.payload.externalTaskStatus';
                  
                  // Set the ConcurrencyLimit if not already set
                  if (!node.data.configuration.parameters.ConcurrencyLimit) {
                    node.data.configuration.parameters.ConcurrencyLimit = 1;
                  } else if (typeof node.data.configuration.parameters.ConcurrencyLimit === 'string') {
                    // Convert string to number if it's a string
                    node.data.configuration.parameters.ConcurrencyLimit = parseInt(node.data.configuration.parameters.ConcurrencyLimit, 10);
                  }
                }
                
                // Ensure all numeric values are saved as numbers
                if (node.data && node.data.configuration) {
                  // Apply the ensureCorrectTypes function to ensure numeric values remain as numbers
                  node.data.configuration = ensureCorrectTypes(node.data.configuration);
                }
                
                return {
                  ...node,
                  data: {
                    ...node.data,
                    // Check if the icon is an object (serialized React element)
                    icon:
                      node.data.icon &&
                      typeof node.data.icon === 'object' &&
                      node.data.icon.props
                        ? <FaFileVideo size={20} />
                        : node.data.icon,
                  },
                };
              });
              
              // Validate integration IDs
              try {
                console.log('[PipelineToolbar] Validating integration IDs...');
                const validationResult = await IntegrationValidationService.validateIntegrationIds(fixedNodes);
                
                if (validationResult.isValid) {
                  console.log('[PipelineToolbar] All integration IDs are valid');
                  // All integration IDs are valid, proceed with import
                  setNodes(fixedNodes);
                  setEdges(fixedEdges);
                  
                  // Update form data
                  if (updateFormData) {
                    updateFormData(fixedNodes, fixedEdges);
                  }
                  
                  // Update viewport if available
                  if (flow.viewport && reactFlowInstance) {
                    const { x = 0, y = 0, zoom = 1 } = flow.viewport;
                    reactFlowInstance.setViewport({ x, y, zoom });
                  }
                } else {
                  console.log('[PipelineToolbar] Invalid integration IDs found:', validationResult.invalidNodes);
                  // Some integration IDs are invalid, show validation dialog
                  setInvalidNodes(validationResult.invalidNodes);
                  setAvailableIntegrations(validationResult.availableIntegrations);
                  setValidationDialogOpen(true);
                }
              } catch (validationError) {
                console.error('[PipelineToolbar] Error validating integration IDs:', validationError);
                // Proceed with import without validation
                setNodes(fixedNodes);
                setEdges(fixedEdges);
                
                if (updateFormData) {
                  updateFormData(fixedNodes, fixedEdges);
                }
                
                // Update viewport if available
                if (flow.viewport && reactFlowInstance) {
                  const { x = 0, y = 0, zoom = 1 } = flow.viewport;
                  reactFlowInstance.setViewport({ x, y, zoom });
                }
              }
            }
            // Alternatively, if the flow uses an "elements" array, split it into nodes and edges.
            else if (flow.elements) {
              const nodes = flow.elements.filter(
                (el: any) => !('source' in el && 'target' in el)
              );
              const edges = flow.elements.filter(
                (el: any) => 'source' in el && 'target' in el
              );
              // Fix edges first
              const fixedEdges = edges.map((edge: any) => {
                // Ensure edge has data field
                if (!edge.data) {
                  edge.data = { text: '' };
                }
                
                // Find the source node for this edge
                const sourceNode = nodes.find((n: any) => n.id === edge.source);
                
                // Find the target node for this edge
                const targetNode = nodes.find((n: any) => n.id === edge.target);
                
                // Check if the source node is a Map node
                if (sourceNode && sourceNode.data && sourceNode.data.id === 'map') {
                  console.log('[PipelineToolbar] Fixing edge for Map node (elements format):', edge.id);
                  
                  if (targetNode) {
                    // Check if this is a connection to a Success node
                    if (targetNode.data && targetNode.data.id === 'success') {
                      // This should be the "Next" connection
                      edge.sourceHandle = 'Next';
                      console.log('[PipelineToolbar] Set sourceHandle to "Next" for edge to Success node');
                    } else {
                      // This should be the "Processor" connection
                      edge.sourceHandle = 'Processor';
                      console.log('[PipelineToolbar] Set sourceHandle to "Processor" for edge to processor node');
                    }
                  }
                }
                
                // Ensure all edges have proper targetHandle values
                if (!edge.targetHandle && targetNode) {
                  // Default to 'input-any' or the first available input type
                  if (targetNode.data && targetNode.data.inputTypes && targetNode.data.inputTypes.length > 0) {
                    const inputType = typeof targetNode.data.inputTypes[0] === 'string'
                      ? targetNode.data.inputTypes[0]
                      : 'any';
                    edge.targetHandle = `input-${inputType}`;
                    console.log(`[PipelineToolbar] Set targetHandle to "${edge.targetHandle}" for edge ${edge.id}`);
                  } else {
                    edge.targetHandle = 'input-any';
                    console.log(`[PipelineToolbar] Set default targetHandle to "input-any" for edge ${edge.id}`);
                  }
                }
                
                // Ensure all edges have proper sourceHandle values if not already set
                if (!edge.sourceHandle && sourceNode && sourceNode.data && sourceNode.data.outputTypes && sourceNode.data.outputTypes.length > 0) {
                  // Use the first available output type or a default value
                  try {
                    const outputType = sourceNode.data.outputTypes[0];
                    if (typeof outputType === 'string') {
                      edge.sourceHandle = outputType;
                    } else if (typeof outputType === 'object' && outputType !== null) {
                      // Try to access name property safely
                      const name = (outputType as any).name;
                      if (name) {
                        edge.sourceHandle = String(name);
                      } else {
                        // Default to first output type as string or 'default'
                        edge.sourceHandle = 'default';
                      }
                    } else {
                      edge.sourceHandle = 'default';
                    }
                    console.log(`[PipelineToolbar] Set sourceHandle to "${edge.sourceHandle}" for edge ${edge.id}`);
                  } catch (error) {
                    // Fallback to default if any error occurs
                    edge.sourceHandle = 'default';
                    console.log(`[PipelineToolbar] Set default sourceHandle for edge ${edge.id}`);
                  }
                }
                
                return edge;
              });
              
              // Now fix the nodes
              const fixedNodes = nodes.map((node: any) => {
                // Fix Map node configuration
                if (node.data && node.data.id === 'map' && node.data.type === 'FLOW') {
                  console.log('[PipelineToolbar] Fixing Map node for import (elements format):', node.id);
                  
                  // Ensure the Map node has the correct configuration
                  if (!node.data.configuration) {
                    node.data.configuration = {};
                  }
                  
                  if (!node.data.configuration.parameters) {
                    node.data.configuration.parameters = {};
                  }
                  
                  // Set the ItemsPath to the correct value
                  node.data.configuration.parameters.ItemsPath = '$.payload.externalTaskStatus';
                  
                  // Set the ConcurrencyLimit if not already set
                  if (!node.data.configuration.parameters.ConcurrencyLimit) {
                    node.data.configuration.parameters.ConcurrencyLimit = 1;
                  } else if (typeof node.data.configuration.parameters.ConcurrencyLimit === 'string') {
                    // Convert string to number if it's a string
                    node.data.configuration.parameters.ConcurrencyLimit = parseInt(node.data.configuration.parameters.ConcurrencyLimit, 10);
                  }
                }
                
                // Ensure all numeric values are saved as numbers
                if (node.data && node.data.configuration) {
                  // Apply the ensureCorrectTypes function to ensure numeric values remain as numbers
                  node.data.configuration = ensureCorrectTypes(node.data.configuration);
                }
                
                return {
                  ...node,
                  data: {
                    ...node.data,
                    icon:
                      node.data.icon &&
                      typeof node.data.icon === 'object' &&
                      node.data.icon.props
                        ? <FaFileVideo size={20} />
                        : node.data.icon,
                  },
                };
              });
              
              // Validate integration IDs
              try {
                console.log('[PipelineToolbar] Validating integration IDs for elements format...');
                const validationResult = await IntegrationValidationService.validateIntegrationIds(fixedNodes);
                
                if (validationResult.isValid) {
                  console.log('[PipelineToolbar] All integration IDs are valid (elements format)');
                  // All integration IDs are valid, proceed with import
                  setNodes(fixedNodes);
                  setEdges(fixedEdges);
                  
                  // Update form data
                  if (updateFormData) {
                    updateFormData(fixedNodes, fixedEdges);
                  }
                } else {
                  console.log('[PipelineToolbar] Invalid integration IDs found (elements format):', validationResult.invalidNodes);
                  // Some integration IDs are invalid, show validation dialog
                  setInvalidNodes(validationResult.invalidNodes);
                  setAvailableIntegrations(validationResult.availableIntegrations);
                  setValidationDialogOpen(true);
                }
              } catch (validationError) {
                console.error('[PipelineToolbar] Error validating integration IDs (elements format):', validationError);
                // Proceed with import without validation
                setNodes(fixedNodes);
                setEdges(fixedEdges);
                
                if (updateFormData) {
                  updateFormData(fixedNodes, fixedEdges);
                }
              }
            }
            
            // Update viewport if available
            if (flow.viewport && reactFlowInstance) {
              const { x = 0, y = 0, zoom = 1 } = flow.viewport;
              reactFlowInstance.setViewport({ x, y, zoom });
            }
          }
        } catch (error) {
          console.error('Error parsing flow JSON', error);
        } finally {
          setIsImporting(false);
        }
      };
    }
  };
  
  // Handle validation dialog confirmation
  const handleValidationConfirm = (mappings: IntegrationMapping[]) => {
    if (importedFlow) {
      setIsImporting(true);
      console.log('[PipelineToolbar] Applying integration mappings:', mappings);
      
      if (importedFlow.nodes) {
        // Update nodes with new integration IDs
        const updatedPipelineNodes = IntegrationValidationService.mapInvalidIntegrationIds(
          importedFlow.nodes,
          mappings
        );
        
        // Fix edges first to ensure proper connections
        const fixedEdges = importedFlow.edges.map((edge: any) => {
          // Ensure edge has data field
          if (!edge.data) {
            edge.data = { text: '' };
          }
          
          // Find the source node for this edge
          const sourceNode = updatedPipelineNodes.find((n: any) => n.id === edge.source);
          
          // Find the target node for this edge
          const targetNode = updatedPipelineNodes.find((n: any) => n.id === edge.target);
          
          // Check if the source node is a Map node
          if (sourceNode && sourceNode.data && sourceNode.data.id === 'map') {
            console.log('[PipelineToolbar] Fixing edge for Map node in validation confirm:', edge.id);
            
            if (targetNode) {
              // Check if this is a connection to a Success node
              if (targetNode.data && targetNode.data.id === 'success') {
                // This should be the "Next" connection
                edge.sourceHandle = 'Next';
                console.log('[PipelineToolbar] Set sourceHandle to "Next" for edge to Success node');
              } else {
                // This should be the "Processor" connection
                edge.sourceHandle = 'Processor';
                console.log('[PipelineToolbar] Set sourceHandle to "Processor" for edge to processor node');
              }
            }
          }
          
          // Ensure all edges have proper targetHandle values
          if (!edge.targetHandle && targetNode) {
            // Default to 'input-any' or the first available input type
            if (targetNode.data && targetNode.data.inputTypes && targetNode.data.inputTypes.length > 0) {
              const inputType = typeof targetNode.data.inputTypes[0] === 'string'
                ? targetNode.data.inputTypes[0]
                : 'any';
              edge.targetHandle = `input-${inputType}`;
              console.log(`[PipelineToolbar] Set targetHandle to "${edge.targetHandle}" for edge ${edge.id}`);
            } else {
              edge.targetHandle = 'input-any';
              console.log(`[PipelineToolbar] Set default targetHandle to "input-any" for edge ${edge.id}`);
            }
          }
          
          // Ensure all edges have proper sourceHandle values if not already set
          if (!edge.sourceHandle && sourceNode && sourceNode.data && sourceNode.data.outputTypes && sourceNode.data.outputTypes.length > 0) {
            // Use the first available output type or a default value
            try {
              const outputType = sourceNode.data.outputTypes[0];
              if (typeof outputType === 'string') {
                edge.sourceHandle = outputType;
              } else if (typeof outputType === 'object' && outputType !== null) {
                // Try to access name property safely
                const name = (outputType as any).name;
                if (name) {
                  edge.sourceHandle = String(name);
                } else {
                  // Default to first output type as string or 'default'
                  edge.sourceHandle = 'default';
                }
              } else {
                edge.sourceHandle = 'default';
              }
              console.log(`[PipelineToolbar] Set sourceHandle to "${edge.sourceHandle}" for edge ${edge.id}`);
            } catch (error) {
              // Fallback to default if any error occurs
              edge.sourceHandle = 'default';
              console.log(`[PipelineToolbar] Set default sourceHandle for edge ${edge.id}`);
            }
          }
          
          return edge;
        });
        
        // Convert PipelineNode[] to Node[] for ReactFlow
        const updatedReactFlowNodes = updatedPipelineNodes.map((node: any) => {
          // Fix Map node configuration
          if (node.data && node.data.id === 'map' && node.data.type === 'FLOW') {
            console.log('[PipelineToolbar] Fixing Map node for validation confirm:', node.id);
            
            // Ensure the Map node has the correct configuration
            if (!node.data.configuration) {
              node.data.configuration = {};
            }
            
            if (!node.data.configuration.parameters) {
              node.data.configuration.parameters = {};
            }
            
            // Set the ItemsPath to the correct value
            node.data.configuration.parameters.ItemsPath = '$.payload.externalTaskStatus';
            
            // Set the ConcurrencyLimit if not already set
            if (!node.data.configuration.parameters.ConcurrencyLimit) {
              node.data.configuration.parameters.ConcurrencyLimit = 1;
            } else if (typeof node.data.configuration.parameters.ConcurrencyLimit === 'string') {
              // Convert string to number if it's a string
              node.data.configuration.parameters.ConcurrencyLimit = parseInt(node.data.configuration.parameters.ConcurrencyLimit, 10);
            }
          }
          
          // Ensure all numeric values are saved as numbers
          if (node.data && node.data.configuration) {
            // Apply the ensureCorrectTypes function to ensure numeric values remain as numbers
            node.data.configuration = ensureCorrectTypes(node.data.configuration);
          }
          
          return {
            ...node,
            data: {
              ...node.data,
              // Fix the icon property to ensure it's properly rendered
              icon: node.data.icon && typeof node.data.icon === 'object' && node.data.icon.props
                ? <FaFileVideo size={20} />
                : node.data.icon
            },
            position: {
              x: typeof node.position.x === 'string' ? parseFloat(node.position.x) : node.position.x,
              y: typeof node.position.y === 'string' ? parseFloat(node.position.y) : node.position.y
            },
            // Convert other string numbers to actual numbers if needed
            ...(node.positionAbsolute && {
              positionAbsolute: {
                x: typeof node.positionAbsolute.x === 'string' ? parseFloat(node.positionAbsolute.x) : node.positionAbsolute.x,
                y: typeof node.positionAbsolute.y === 'string' ? parseFloat(node.positionAbsolute.y) : node.positionAbsolute.y
              }
            })
          };
        });
        
        // Apply the updated nodes
        setNodes(updatedReactFlowNodes);
        setEdges(fixedEdges);
        
        // Update form data
        if (updateFormData) {
          updateFormData(updatedReactFlowNodes, fixedEdges);
        }
        
        // Update viewport if available
        if (importedFlow.viewport && reactFlowInstance) {
          const { x = 0, y = 0, zoom = 1 } = importedFlow.viewport;
          reactFlowInstance.setViewport({ x, y, zoom });
        }
      } else if (importedFlow.elements) {
        // Handle elements format
        const nodes = importedFlow.elements.filter(
          (el: any) => !('source' in el && 'target' in el)
        );
        const edges = importedFlow.elements.filter(
          (el: any) => 'source' in el && 'target' in el
        );
        
        // Update nodes with new integration IDs
        const updatedPipelineNodes = IntegrationValidationService.mapInvalidIntegrationIds(
          nodes,
          mappings
        );
        
        // Fix edges first to ensure proper connections
        const fixedEdges = edges.map((edge: any) => {
          // Ensure edge has data field
          if (!edge.data) {
            edge.data = { text: '' };
          }
          
          // Fix Map node connections
          // Find the source node for this edge
          const sourceNode = updatedPipelineNodes.find((n: any) => n.id === edge.source);
          
          // Check if the source node is a Map node
          if (sourceNode && sourceNode.data && sourceNode.data.id === 'map') {
            console.log('[PipelineToolbar] Fixing edge for Map node in validation confirm (elements format):', edge.id);
            
            // Find the target node
            const targetNode = updatedPipelineNodes.find((n: any) => n.id === edge.target);
            
            if (targetNode) {
              // Check if this is a connection to a Success node
              if (targetNode.data && targetNode.data.id === 'success') {
                // This should be the "Next" connection
                edge.sourceHandle = 'Next';
                console.log('[PipelineToolbar] Set sourceHandle to "Next" for edge to Success node');
              } else {
                // This should be the "Processor" connection
                edge.sourceHandle = 'Processor';
                console.log('[PipelineToolbar] Set sourceHandle to "Processor" for edge to processor node');
              }
            }
          }
          
          return edge;
        });
        
        // Convert PipelineNode[] to Node[] for ReactFlow
        const updatedReactFlowNodes = updatedPipelineNodes.map((node: any) => {
          // Fix Map node configuration
          if (node.data && node.data.id === 'map' && node.data.type === 'FLOW') {
            console.log('[PipelineToolbar] Fixing Map node for validation confirm (elements format):', node.id);
            
            // Ensure the Map node has the correct configuration
            if (!node.data.configuration) {
              node.data.configuration = {};
            }
            
            if (!node.data.configuration.parameters) {
              node.data.configuration.parameters = {};
            }
            
            // Set the ItemsPath to the correct value
            node.data.configuration.parameters.ItemsPath = '$.payload.externalTaskStatus';
            
            // Set the ConcurrencyLimit if not already set
            if (!node.data.configuration.parameters.ConcurrencyLimit) {
              node.data.configuration.parameters.ConcurrencyLimit = 1;
            } else if (typeof node.data.configuration.parameters.ConcurrencyLimit === 'string') {
              // Convert string to number if it's a string
              node.data.configuration.parameters.ConcurrencyLimit = parseInt(node.data.configuration.parameters.ConcurrencyLimit, 10);
            }
          }
          
          // Ensure all numeric values are saved as numbers
          if (node.data && node.data.configuration) {
            // Apply the ensureCorrectTypes function to ensure numeric values remain as numbers
            node.data.configuration = ensureCorrectTypes(node.data.configuration);
          }
          
          return {
            ...node,
            data: {
              ...node.data,
              // Fix the icon property to ensure it's properly rendered
              icon: node.data.icon && typeof node.data.icon === 'object' && node.data.icon.props
                ? <FaFileVideo size={20} />
                : node.data.icon
            },
            position: {
              x: typeof node.position.x === 'string' ? parseFloat(node.position.x) : node.position.x,
              y: typeof node.position.y === 'string' ? parseFloat(node.position.y) : node.position.y
            },
            // Convert other string numbers to actual numbers if needed
            ...(node.positionAbsolute && {
              positionAbsolute: {
                x: typeof node.positionAbsolute.x === 'string' ? parseFloat(node.positionAbsolute.x) : node.positionAbsolute.x,
                y: typeof node.positionAbsolute.y === 'string' ? parseFloat(node.positionAbsolute.y) : node.positionAbsolute.y
              }
            })
          };
        });
        
        // Apply the updated nodes
        setNodes(updatedReactFlowNodes);
        setEdges(fixedEdges);
        
        // Update form data
        if (updateFormData) {
          updateFormData(updatedReactFlowNodes, fixedEdges);
        }
      }
    }
    
    // Close the dialog
    setValidationDialogOpen(false);
    
    // End the importing state
    setIsImporting(false);
  };

  // Export the current flow as a JSON file.
  const onExport = (): void => {
    if (reactFlowInstance) {
      // Get the flow object from ReactFlow
      const flow = reactFlowInstance.toObject();
      
      // Normalize and validate the flow object to ensure it's compatible with the backend
      const fixedFlow = normalizeFlowConnections(flow);
      
      // Convert to JSON and download
      const flowJson = JSON.stringify(fixedFlow, null, 2);
      const blob = new Blob([flowJson], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // Use the pipeline name for the file name, or default to 'flow' if empty
      const fileName = pipelineName.trim() ? `${pipelineName}.json` : 'flow.json';
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    }
  };
  
  // Normalize and validate the flow object to ensure it's compatible with the backend
  const normalizeFlowConnections = (flow: any): any => {
    // Create a deep copy of the flow to avoid modifying the original
    const fixedFlow = JSON.parse(JSON.stringify(flow));
    
    // Fix Map nodes and their connections
    if (fixedFlow.nodes && fixedFlow.edges) {
      // Fix Map nodes and ensure correct types for all nodes
      fixedFlow.nodes.forEach((node: any) => {
        // Check if this is a Map node
        if (node.data && node.data.id === 'map' && node.data.type === 'FLOW') {
          console.log('Fixing Map node for export:', node.id);
          
          // Ensure the Map node has the correct configuration
          if (!node.data.configuration) {
            node.data.configuration = {};
          }
          
          if (!node.data.configuration.parameters) {
            node.data.configuration.parameters = {};
          }
          
          // Set the ItemsPath to the correct value
          node.data.configuration.parameters.ItemsPath = '$.payload.externalTaskStatus';
          
          // Set the ConcurrencyLimit if not already set
          if (!node.data.configuration.parameters.ConcurrencyLimit) {
            node.data.configuration.parameters.ConcurrencyLimit = 1;
          } else if (typeof node.data.configuration.parameters.ConcurrencyLimit === 'string') {
            // Convert string to number if it's a string
            node.data.configuration.parameters.ConcurrencyLimit = parseInt(node.data.configuration.parameters.ConcurrencyLimit, 10);
          }
        }
        
        // Ensure all numeric values are saved as numbers for all nodes
        if (node.data && node.data.configuration) {
          // Apply the ensureCorrectTypes function to ensure numeric values remain as numbers
          node.data.configuration = ensureCorrectTypes(node.data.configuration);
        }
      });
      
      // Fix edge connections for all nodes
      fixedFlow.edges.forEach((edge: any) => {
        // Find the source node for this edge
        const sourceNode = fixedFlow.nodes.find((n: any) => n.id === edge.source);
        
        // Find the target node for this edge
        const targetNode = fixedFlow.nodes.find((n: any) => n.id === edge.target);
        
        // Ensure edge has data field
        if (!edge.data) {
          edge.data = { text: '' };
        }
        
        // Check if the source node is a Map node
        if (sourceNode && sourceNode.data && sourceNode.data.id === 'map') {
          console.log('Fixing edge for Map node:', edge.id);
          
          if (targetNode) {
            // Check if this is a connection to a Success node
            if (targetNode.data && targetNode.data.id === 'success') {
              // This should be the "Next" connection
              edge.sourceHandle = 'Next';
              console.log('Set sourceHandle to "Next" for edge to Success node');
            } else {
              // This should be the "Processor" connection
              edge.sourceHandle = 'Processor';
              console.log('Set sourceHandle to "Processor" for edge to processor node');
            }
          }
        }
        
        // Ensure all edges have proper targetHandle values
        if (!edge.targetHandle && targetNode) {
          // Default to 'input-any' or the first available input type
          if (targetNode.data && targetNode.data.inputTypes && targetNode.data.inputTypes.length > 0) {
            const inputType = typeof targetNode.data.inputTypes[0] === 'string'
              ? targetNode.data.inputTypes[0]
              : 'any';
            edge.targetHandle = `input-${inputType}`;
            console.log(`Set targetHandle to "${edge.targetHandle}" for edge ${edge.id}`);
          } else {
            edge.targetHandle = 'input-any';
            console.log(`Set default targetHandle to "input-any" for edge ${edge.id}`);
          }
        }
        
        // Ensure all edges have proper sourceHandle values if not already set
        if (!edge.sourceHandle && sourceNode && sourceNode.data && sourceNode.data.outputTypes && sourceNode.data.outputTypes.length > 0) {
          // Use the first available output type or a default value
          try {
            const outputType = sourceNode.data.outputTypes[0];
            if (typeof outputType === 'string') {
              edge.sourceHandle = outputType;
            } else if (typeof outputType === 'object' && outputType !== null) {
              // Try to access name property safely
              const name = (outputType as any).name;
              if (name) {
                edge.sourceHandle = String(name);
              } else {
                // Default to first output type as string or 'default'
                edge.sourceHandle = 'default';
              }
            } else {
              edge.sourceHandle = 'default';
            }
            console.log(`Set sourceHandle to "${edge.sourceHandle}" for edge ${edge.id}`);
          } catch (error) {
            // Fallback to default if any error occurs
            edge.sourceHandle = 'default';
            console.log(`Set default sourceHandle for edge ${edge.id}`);
          }
        }
        
        // Special handling for Audio Splitter node to ensure it's properly connected to the Map node
        if (sourceNode && sourceNode.data && sourceNode.data.id === 'audio_splitter' &&
            targetNode && targetNode.data && targetNode.data.id === 'map') {
          console.log('Ensuring Audio Splitter to Map connection is properly set up');
          
          // Make sure the Audio Splitter has the correct sourceHandle
          if (!edge.sourceHandle) {
            edge.sourceHandle = 'audio';
            console.log('Set sourceHandle to "audio" for Audio Splitter node');
          }
          
          // Make sure the Map node has the correct targetHandle
          if (!edge.targetHandle) {
            edge.targetHandle = 'input-any';
            console.log('Set targetHandle to "input-any" for Map node');
          }
        }
      });
    }
    
    // Add settings if not present
    if (!fixedFlow.settings) {
      fixedFlow.settings = {
        autoStart: false,
        retryAttempts: 3,
        timeout: 3600
      };
    }
    
    // Add name, description, and active if not present
    if (!fixedFlow.name && pipelineName) {
      fixedFlow.name = pipelineName;
    }
    
    if (!fixedFlow.description) {
      fixedFlow.description = '';
    }
    
    if (fixedFlow.active === undefined) {
      fixedFlow.active = active;
    }
    
    return fixedFlow;
  };

  // Import/Export dropdown functionality
  const [importExportOpen, setImportExportOpen] = React.useState(false);
  const importExportRef = React.useRef<HTMLDivElement>(null);

  const handleImportExportToggle = () => {
    setImportExportOpen((prevOpen) => !prevOpen);
  };

  const handleImportExportClose = (event: Event) => {
    if (
      importExportRef.current &&
      importExportRef.current.contains(event.target as HTMLElement)
    ) {
      return;
    }
    setImportExportOpen(false);
  };

  const handleImport = () => {
    fileInputRef.current?.click();
    setImportExportOpen(false);
  };
  
  // Reset file input value when importing is done
  React.useEffect(() => {
    if (!isImporting && fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [isImporting]);

  const handleExport = () => {
    onExport();
    setImportExportOpen(false);
  };

  return (
    <>
      {/* Loading Backdrop */}
      <Backdrop
        sx={{
          color: '#fff',
          zIndex: (theme) => theme.zIndex.drawer + 1,
          flexDirection: 'column',
          gap: 2
        }}
        open={isImporting}
      >
        <CircularProgress color="inherit" />
        <Box sx={{ typography: 'body1', fontWeight: 'medium' }}>
          Importing Pipeline...
        </Box>
      </Backdrop>
      
      {/* Container to calculate available space */}
      <Box
        sx={{
          position: 'fixed',
          zIndex: 1100,
          left: (isLeftSidebarCollapsed ? collapsedDrawerWidth : drawerWidth) + 16,
          right: (isRightSidebarExpanded ? width : COLLAPSED_WIDTH) + 16,
          top: '72px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        {/* Left side - Pipeline Name, Save and Cancel */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              '& .MuiInputBase-root': {
                bgcolor: 'transparent',
                '& input': {
                  ...commonStyles,
                  px: 2,
                  py: 1,
                  borderRadius: '4px',
                },
              },
              maxWidth: {
                // Responsive width based on available space
                xs: '200px',
                sm: '250px',
                md: '300px',
              },
            }}
          >
            <PipelineNameInput
              value={pipelineName}
              onChange={onPipelineNameChange}
            />
          </Box>
          
          {/* Save Button */}
          <Button
            variant="contained"
            color="primary"
            onClick={onSave}
            disabled={isLoading || !pipelineName.trim()}
          >
            {isLoading ? 'Saving...' : 'Save'}
          </Button>
          
          {/* Cancel Button */}
          <Button
            variant="outlined"
            color="inherit"
            onClick={handleCancel}
          >
            Cancel
          </Button>
        </Box>
        
        {/* Center - Status and Active Switch */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Show status chip if status is provided and not DEPLOYED */}
          {status && status !== 'DEPLOYED' && (
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                px: 1.5,
                py: 0.5,
                borderRadius: '16px',
                fontSize: '0.75rem',
                fontWeight: 'medium',
                lineHeight: '1',
                backgroundColor: status === 'FAILED' ? 'error.light' :
                                 status === 'CREATING' ? 'info.light' :
                                 status === 'PENDING' ? 'warning.light' : 'grey.300',
                color: status === 'FAILED' ? 'error.dark' :
                       status === 'CREATING' ? 'info.dark' :
                       status === 'PENDING' ? 'warning.dark' : 'grey.800',
              }}
            >
              {status}
            </Box>
          )}
          
          {/* Active/Inactive Toggle */}
          <FormControlLabel
            control={
              <IconSwitch
                checked={active}
                onChange={(e) => onActiveChange(e.target.checked)}
                color="primary"
                onIcon={<ToggleOnIcon fontSize="large" />}
                offIcon={<ToggleOffIcon fontSize="large" />}
                onColor="#2e7d32"
                offColor="#757575"
                trackOnColor="#b2ebf2"
                trackOffColor="#cfd8dc"
              />
            }
            label={active ? "Active" : "Inactive"}
          />
        </Box>

        {/* Right side - Import and Delete */}
        <Stack
          direction="row"
          spacing={2}
          sx={{
            '& .MuiButton-root': commonStyles,
          }}
        >
          {/* Hidden file input for import */}
          <input
            type="file"
            accept="application/json"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleLoadFlow}
          />

          {/* Import/Export ButtonGroup */}
          <ButtonGroup
            variant="outlined"
            ref={importExportRef}
            aria-label="Pipeline file operations"
          >
            <Button
              color="inherit"
              onClick={handleImport}
              startIcon={<FileUploadIcon />}
            >
              Import
            </Button>
            <Button
              size="small"
              color="inherit"
              aria-controls={importExportOpen ? 'import-export-menu' : undefined}
              aria-expanded={importExportOpen ? 'true' : undefined}
              aria-label="select import/export action"
              aria-haspopup="menu"
              onClick={handleImportExportToggle}
            >
              <ArrowDropDownIcon />
            </Button>
          </ButtonGroup>

          {/* Import/Export Dropdown */}
          <Popper
            sx={{ zIndex: 1200 }}
            open={importExportOpen}
            anchorEl={importExportRef.current}
            role={undefined}
            transition
            disablePortal
          >
            {({ TransitionProps, placement }) => (
              <Grow
                {...TransitionProps}
                style={{
                  transformOrigin:
                    placement === 'bottom' ? 'center top' : 'center bottom',
                }}
              >
                <Paper>
                  <ClickAwayListener onClickAway={handleImportExportClose}>
                    <MenuList id="import-export-menu" autoFocusItem>
                      <MenuItem onClick={handleExport}>
                        <FileDownloadIcon sx={{ mr: 1 }} /> Export Pipeline
                      </MenuItem>
                    </MenuList>
                  </ClickAwayListener>
                </Paper>
              </Grow>
            )}
          </Popper>


          {/* Delete Button - Only show if onDelete is provided */}
          {onDelete && (
            <Button
              variant="contained"
              onClick={onDelete}
              startIcon={<DeleteIcon />}
              sx={{
                backgroundColor: 'error.main',
                color: 'white',
                '&:hover': {
                  backgroundColor: 'error.dark',
                },
                '&.MuiButton-root': {
                  bgcolor: 'error.main',
                }
              }}
            >
              Delete
            </Button>
          )}
        </Stack>
      </Box>
      
      {/* Integration Validation Dialog */}
      <IntegrationValidationDialog
        open={validationDialogOpen}
        invalidNodes={invalidNodes}
        availableIntegrations={availableIntegrations}
        onClose={() => setValidationDialogOpen(false)}
        onConfirm={handleValidationConfirm}
      />
    </>
  );
};

export default PipelineToolbar;
