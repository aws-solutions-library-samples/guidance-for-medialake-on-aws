import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

// MUI Components
import {
    Box,
    Typography,
    Grid,
    Drawer,
    Paper,
    CircularProgress,
    Button,
    Divider,
    IconButton,
    Stack,
    TextField,
    Menu,
    MenuItem,
} from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import type { MenuProps } from '@mui/material/Menu';
import Chip from '@mui/joy/Chip';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
// MUI Icons
import ArrowForwardIosSharpIcon from '@mui/icons-material/ArrowForwardIosSharp';
import MuiAccordion, { AccordionProps } from '@mui/material/Accordion';
import MuiAccordionSummary, {
    AccordionSummaryProps,
} from '@mui/material/AccordionSummary';
import MuiAccordionDetails from '@mui/material/AccordionDetails';
import EditIcon from '@mui/icons-material/Edit';
import ArchiveIcon from '@mui/icons-material/Archive';
import FileCopyIcon from '@mui/icons-material/FileCopy';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

// Custom components and hooks
import { ImageViewer } from '../components/common/ImageViewer';
import { useAsset } from '../api/hooks/useAssets';



interface Pipeline {
    id: string;
    name: string;
    description: string;
    icon: string;
    estimatedTime: string;
}

const Accordion = styled((props: AccordionProps) => (
    <MuiAccordion disableGutters elevation={0} square {...props} />
))(({ theme }) => ({
    border: `1px solid ${theme.palette.divider}`,
    '&:not(:last-child)': {
        borderBottom: 0,
    },
    '&::before': {
        display: 'none',
    },
}));

const AccordionSummary = styled((props: AccordionSummaryProps) => (
    <MuiAccordionSummary
        expandIcon={<ArrowForwardIosSharpIcon sx={{ fontSize: '0.9rem' }} />}
        {...props}
    />
))(({ theme }) => ({
    backgroundColor: 'rgba(0, 0, 0, .03)',
    flexDirection: 'row-reverse',
    '& .MuiAccordionSummary-expandIconWrapper.Mui-expanded': {
        transform: 'rotate(90deg)',
    },
    '& .MuiAccordionSummary-content': {
        marginLeft: theme.spacing(1),
    },
    ...theme.applyStyles('dark', {
        backgroundColor: 'rgba(255, 255, 255, .05)',
    }),
}));

const AccordionDetails = styled(MuiAccordionDetails)(({ theme }) => ({
    padding: theme.spacing(2),
    borderTop: '1px solid rgba(0, 0, 0, .125)',
}));

const StyledMenu = styled((props: MenuProps) => (
    <Menu
        elevation={0}
        anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
        }}
        transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
        }}
        {...props}
    />
))(({ theme }) => ({
    '& .MuiPaper-root': {
        borderRadius: 6,
        marginTop: theme.spacing(1),
        minWidth: 180,
        color: 'rgb(55, 65, 81)',
        boxShadow:
            'rgb(255, 255, 255) 0px 0px 0px 0px, rgba(0, 0, 0, 0.05) 0px 0px 0px 1px, rgba(0, 0, 0, 0.1) 0px 10px 15px -3px, rgba(0, 0, 0, 0.05) 0px 4px 6px -2px',
        '& .MuiMenu-list': {
            padding: '4px 0',
        },
        '& .MuiMenuItem-root': {
            '& .MuiSvgIcon-root': {
                fontSize: 18,
                color: theme.palette.text.secondary,
                marginRight: theme.spacing(1.5),
            },
            '&:active': {
                backgroundColor: alpha(
                    theme.palette.primary.main,
                    theme.palette.action.selectedOpacity,
                ),
            },
        },
        ...theme.applyStyles('dark', {
            color: theme.palette.grey[300],
        }),
    },
}));

const ImageDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();

    const [expanded, setExpanded] = React.useState<string | false>('panel1');

    const handleChange =
        (panel: string) => (event: React.SyntheticEvent, newExpanded: boolean) => {
            setExpanded(newExpanded ? panel : false);
        };


    const [derivedRepresentations] = useState(() => {
        if (!assetData?.data) return [];
        return [
            {
                id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
                src: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: 'Original',
                description: 'Original high resolution version',
            },
            ...assetData.data.asset.DerivedRepresentations.map(rep => ({
                id: rep.ID,
                src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: rep.Purpose.charAt(0).toUpperCase() + rep.Purpose.slice(1),
                description: `${rep.Purpose} version`,
            }))
        ];
    });
    const [availablePipelines] = useState([
        { id: 'p1', name: 'Image Enhancement', description: 'Enhance image quality and colors', icon: ':art:', estimatedTime: '2-3 minutes' },
        { id: 'p2', name: 'Object Detection', description: 'Detect and label objects in the image', icon: ':mag:', estimatedTime: '1-2 minutes' }
    ]);
    const handlePipelineExecution = (pipelineId: string) => {
        console.log(`Executing pipeline: ${pipelineId}`);
    };

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);
    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }
    if (error || !assetData) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="h5" color="error">
                    {error ? 'Error loading asset details' : 'Asset not found'}
                </Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }
    const getProxyUrl = () => {
        if (assetData?.data?.asset?.DerivedRepresentations) {
            const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
            if (proxyRep) {
                return proxyRep.URL;
            }
        }
        return assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Path;
    };

    const proxyUrl = getProxyUrl();
    return (
        <Box sx={{ flexGrow: 1, p: 3, maxWidth: '1600px', margin: '0 auto' }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 3 }}>
                Back to Search Results
            </Button>
            <Grid container spacing={3} sx={{ flexGrow: 1 }}>
                {/* Left Panel - Inventory/Manifestation */}
                <Grid item xs={2} sx={{ display: 'flex', flexDirection: 'column' }}>
                    <Paper elevation={3} sx={{ p: 2, display: 'flex', flexDirection: 'column', height: '100%' }}>
                        <Typography variant="h6">Representations</Typography>
                        <Box sx={{ flexGrow: 1, overflowY: 'auto', mt: 2 }}>
                            {derivedRepresentations.map((rep) => (
                                <Button
                                    key={rep.id}
                                    variant="outlined"
                                    fullWidth
                                    sx={{ mb: 1 }}
                                >
                                    {rep.type}
                                </Button>
                            ))}
                        </Box>
                    </Paper>
                </Grid>
                {/* Main Image Section with Status above */}
                <Grid item xs={8}>
                    {/* Status Section */}
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Stack direction="row"

                            sx={{
                                justifyContent: "space-between",
                                alignItems: "baseline",
                            }}
                        >

                            <Typography variant="h6">Status: Active</Typography>
                            {/* Add a status display or control here */}
                            <div>
                                <Button
                                    id="demo-customized-button"
                                    aria-controls={open ? 'demo-customized-menu' : undefined}
                                    aria-haspopup="true"
                                    aria-expanded={open ? 'true' : undefined}
                                    variant="outlined"
                                    disableElevation
                                    onClick={handleClick}
                                    endIcon={<KeyboardArrowDownIcon />}
                                >
                                    Pipelines
                                </Button>
                                <StyledMenu
                                    id="demo-customized-menu"
                                    MenuListProps={{
                                        'aria-labelledby': 'demo-customized-button',
                                    }}
                                    anchorEl={anchorEl}
                                    open={open}
                                    onClose={handleClose}
                                >
                                    {availablePipelines.map(pipeline => (


                                        <MenuItem key={pipeline.id} sx={{
                                            justifyContent: "space-between",
                                            alignItems: "baseline",
                                        }} disableRipple>
                                            {/* <EditIcon /> */}
                                            {pipeline.name}<Button onClick={() => handlePipelineExecution(pipeline.id)}>Run</Button>
                                        </MenuItem>
                                    ))}


                                </StyledMenu>
                            </div>

                        </Stack>
                    </Paper>
                    {/* Image Viewer */}
                    <Paper elevation={3} sx={{ p: 2, mt: 2, position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                        <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                        {/* <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', position: 'absolute', top: '50%' }}>
                            <IconButton><ArrowBackIcon /></IconButton>
                            <IconButton><PlayArrowIcon /></IconButton>
                        </Box> */}
                    </Paper>
                </Grid>
                {/* Right Panel - Pipelines and Comments */}
                <Grid item xs={2} sx={{ display: 'flex', flexDirection: 'column' }}>
                    <Paper elevation={3} sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
                        <Typography variant="h6" sx={{ mb: 2 }}>Comments</Typography>
                        <Stack
                            sx={{
                                flexGrow: 1,
                                height: '100%',
                            }}
                            spacing={2}
                        >
                            <Box sx={{ overflowY: 'auto', flexGrow: 1 }}>
                                <Stack spacing={2}>
                                    <Chip
                                        color="primary"
                                        onClick={function () { }}
                                        size="sm"
                                        variant="soft"
                                    >9:46 AM: Crop to center</Chip>
                                    <Chip
                                        color="success"
                                        onClick={function () { }}

                                        size="sm"
                                        variant="soft"
                                    >10:46 AM: Remove bg</Chip>
                                    <Chip
                                        color="primary"
                                        onClick={function () { }}
                                        size="sm"
                                        variant="soft"
                                    >11:46 AM: Send to publisher</Chip>

                                </Stack>
                            </Box>

                            <TextField
                                multiline
                                fullWidth
                                rows={4}
                                maxRows={4}
                                placeholder="Add comments"
                                sx={{
                                    '& .MuiInputBase-root': {
                                        maxHeight: 'calc(8em + 32px)', // Approximation for 4 rows
                                        overflowY: 'auto'
                                    }
                                }}
                            />
                        </Stack>
                    </Paper>
                </Grid>
                {/* Metadata and Activity Log */}
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Metadata</Typography>
                        <Divider sx={{ my: 1 }} />

                        <Accordion expanded={expanded === 'panel1'} onChange={handleChange('panel1')}>
                            <AccordionSummary aria-controls="panel1d-content" id="panel1d-header">
                                <Typography>EXIF</Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Typography>
                                    <Stack direction="row">
                                        <Typography variant="body2">Color Space: XXXX</Typography>
                                    </Stack>
                                </Typography>
                            </AccordionDetails>
                        </Accordion>

                    </Paper>
                </Grid>
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Activity Log</Typography>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="body2">User A did this</Typography>
                        <Typography variant="body2">Pipeline C did this...</Typography>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};
export default ImageDetailPage;