import React, { useMemo, useState, ChangeEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, getFilteredRowModel, getSortedRowModel, getPaginationRowModel, flexRender, ColumnDef, Row } from '@tanstack/react-table';
import {
    Box,
    Typography,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TableSortLabel,
    TextField,
    Button,
    CircularProgress,
    IconButton,
    Tooltip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Grid,
    Card,
    CardContent,
    CardActions,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    SelectChangeEvent,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

interface Tag {
    id: number;
    name: string;
    createdOn: string;
    tagGroup: string;
    searchName: string;
    type?: 'text' | 'image' | 'audio';
}

interface TagGroup {
    id: number;
    name: string;
    description: string;
    createdOn: string;
}

// Mock API calls - replace these with your actual API calls
const fetchTags = async (): Promise<Tag[]> => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return [
        { id: 1, name: 'Animals with people', createdOn: '2024-05-15', tagGroup: 'Animals', searchName: 'Animals with people' },
        { id: 2, name: 'Waterfalls', createdOn: '2024-05-16', tagGroup: 'Outside', searchName: 'waterfalls' },
        { id: 3, name: 'Red coats', createdOn: '2024-05-17', tagGroup: 'Creative Group', searchName: 'people wearing red coats' },
    ];
};

const fetchTagGroups = async (): Promise<TagGroup[]> => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return [
        { id: 1, name: 'Animals', description: 'Tags related to animals doing things', createdOn: '2024-05-10' },
        { id: 2, name: 'Outside', description: 'Outside related tags', createdOn: '2024-05-11' },
        { id: 3, name: 'Creative Group', description: 'Tags for the creative group', createdOn: '2024-05-11' },
    ];
};

const createTag = async (newTag: Omit<Tag, 'id'>): Promise<void> => {
    console.log('Creating tag:', newTag);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const updateTag = async (updatedTag: Tag): Promise<void> => {
    console.log('Updating tag:', updatedTag);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const deleteTag = async (tagId: number): Promise<void> => {
    console.log('Deleting tag with ID:', tagId);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const createTagGroup = async (newTagGroup: Omit<TagGroup, 'id'>): Promise<void> => {
    console.log('Creating tag group:', newTagGroup);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const updateTagGroup = async (updatedTagGroup: TagGroup): Promise<void> => {
    console.log('Updating tag group:', updatedTagGroup);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const deleteTagGroup = async (tagGroupId: number): Promise<void> => {
    console.log('Deleting tag group with ID:', tagGroupId);
    await new Promise(resolve => setTimeout(resolve, 1000));
};

const TagsPage: React.FC = () => {
    const queryClient = useQueryClient();
    const { data: tags, isLoading: isLoadingTags } = useQuery<Tag[], Error>({
        queryKey: ['tags'],
        queryFn: fetchTags,
    });
    const { data: tagGroups, isLoading: isLoadingTagGroups } = useQuery<TagGroup[], Error>({
        queryKey: ['tagGroups'],
        queryFn: fetchTagGroups,
    });

    const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
    const [selectedTagGroup, setSelectedTagGroup] = useState<TagGroup | null>(null);
    const [isTagDialogOpen, setIsTagDialogOpen] = useState(false);
    const [isTagGroupDialogOpen, setIsTagGroupDialogOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const createTagMutation = useMutation({
        mutationFn: createTag,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tags'] });
            setIsTagDialogOpen(false);
        },
    });

    const updateTagMutation = useMutation({
        mutationFn: updateTag,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tags'] });
            setIsTagDialogOpen(false);
        },
    });

    const deleteTagMutation = useMutation({
        mutationFn: deleteTag,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tags'] });
        },
    });

    const createTagGroupMutation = useMutation({
        mutationFn: createTagGroup,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tagGroups'] });
            setIsTagGroupDialogOpen(false);
        },
        onError: (error: Error) => {
            console.error('Error creating tag group:', error);
        },
    });

    const updateTagGroupMutation = useMutation({
        mutationFn: updateTagGroup,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tagGroups'] });
            setIsTagGroupDialogOpen(false);
        },
    });

    const deleteTagGroupMutation = useMutation({
        mutationFn: deleteTagGroup,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tagGroups'] });
        },
    });

    const handleCreateTag = (newTag: Omit<Tag, 'id'>) => {
        createTagMutation.mutate(newTag);
    };

    const handleUpdateTag = (updatedTag: Tag) => {
        updateTagMutation.mutate(updatedTag);
    };

    const handleDeleteTag = (tagId: number) => {
        deleteTagMutation.mutate(tagId);
    };

    const handleCreateTagGroup = (newTagGroup: Omit<TagGroup, 'id'>) => {
        createTagGroupMutation.mutate(newTagGroup);
    };

    const handleUpdateTagGroup = (updatedTagGroup: TagGroup) => {
        updateTagGroupMutation.mutate(updatedTagGroup);
    };

    const handleDeleteTagGroup = (tagGroupId: number) => {
        deleteTagGroupMutation.mutate(tagGroupId);
    };

    const openTagDialog = (tag: Tag | null) => {
        setSelectedTag(tag);
        setIsTagDialogOpen(true);
    };

    const closeTagDialog = () => {
        setSelectedTag(null);
        setIsTagDialogOpen(false);
    };

    const openTagGroupDialog = (tagGroup: TagGroup | null) => {
        setSelectedTagGroup(tagGroup);
        setIsTagGroupDialogOpen(true);
    };

    const closeTagGroupDialog = () => {
        setSelectedTagGroup(null);
        setIsTagGroupDialogOpen(false);
    };

    const columns = useMemo<ColumnDef<Tag>[]>(
        () => [
            {
                header: 'Name',
                accessorKey: 'name',
            },
            {
                header: 'Created On',
                accessorKey: 'createdOn',
            },
            {
                header: 'Tag Group',
                accessorKey: 'tagGroup',
            },
            {
                header: 'Search Name',
                accessorKey: 'searchName',
            },
            {
                header: 'Type',
                accessorKey: 'type',
            },
            {
                header: 'Actions',
                cell: ({ row }: { row: Row<Tag> }) => (
                    <>
                        <Tooltip title="Edit Tag">
                            <IconButton onClick={() => openTagDialog(row.original)} size="small">
                                <EditIcon />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Tag">
                            <IconButton onClick={() => handleDeleteTag(row.original.id)} size="small">
                                <DeleteIcon />
                            </IconButton>
                        </Tooltip>
                    </>
                ),
            },
        ],
        [handleDeleteTag]
    );

    const table = useReactTable({
        data: tags || [],
        columns,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
    });

    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        if (event.target.files) {
            setSelectedFile(event.target.files[0]);
        }
    };

    const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
    };

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        if (event.dataTransfer.files) {
            setSelectedFile(event.dataTransfer.files[0]);
        }
    };

    if (isLoadingTags || isLoadingTagGroups) return <CircularProgress />;

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Tag Groups
            </Typography>
            <Grid container spacing={2} sx={{ mb: 4 }}>
                {tagGroups?.map((tagGroup) => (
                    <Grid item xs={12} sm={6} md={3} key={tagGroup.id}>
                        <Card>
                            <CardContent>
                                <Typography variant="h6">{tagGroup.name}</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {tagGroup.description}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Created On: {tagGroup.createdOn}
                                </Typography>
                            </CardContent>
                            <CardActions>
                                <Button size="small" onClick={() => openTagGroupDialog(tagGroup)}>Edit</Button>
                                <Button size="small" onClick={() => handleDeleteTagGroup(tagGroup.id)}>Delete</Button>
                            </CardActions>
                        </Card>
                    </Grid>
                ))}
                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Add New Tag Group</Typography>
                        </CardContent>
                        <CardActions>
                            <Button size="small" onClick={() => openTagGroupDialog(null)}>Create</Button>
                        </CardActions>
                    </Card>
                </Grid>
            </Grid>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Tags
                </Typography>
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<AddIcon />}
                    onClick={() => openTagDialog(null)}
                >
                    Add New Tag
                </Button>
            </Box>
            <Box sx={{ width: '80%', margin: '0 auto' }}>
                <TextField
                    label="Filter Tags"
                    variant="outlined"
                    fullWidth
                    onChange={(e) => {
                        table.getColumn('name')?.setFilterValue(e.target.value);
                        table.getColumn('tagGroup')?.setFilterValue(e.target.value);
                        table.getColumn('searchName')?.setFilterValue(e.target.value);
                    }}
                    sx={{ mb: 2 }}
                />
                <TableContainer component={Paper}>
                    <Table sx={{ minWidth: 650 }} aria-label="tags table">
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <TableCell key={header.id}>
                                            {header.isPlaceholder ? null : (
                                                <TableSortLabel
                                                    active={header.column.getIsSorted() !== false}
                                                    direction={header.column.getIsSorted() === 'desc' ? 'desc' : 'asc'}
                                                    onClick={header.column.getToggleSortingHandler()}
                                                >
                                                    {flexRender(
                                                        header.column.columnDef.header,
                                                        header.getContext()
                                                    )}
                                                </TableSortLabel>
                                            )}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableHead>
                        <TableBody>
                            {table.getRowModel().rows.map(row => (
                                <TableRow key={row.id}>
                                    {row.getVisibleCells().map(cell => (
                                        <TableCell key={cell.id}>
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                        <Button onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
                        <Button onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
                    </Box>
                    <Typography>
                        Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                    </Typography>
                    <select
                        value={table.getState().pagination.pageSize}
                        onChange={e => table.setPageSize(Number(e.target.value))}
                    >
                        {[10, 25, 50].map(pageSize => (
                            <option key={pageSize} value={pageSize}>
                                Show {pageSize}
                            </option>
                        ))}
                    </select>
                </Box>
            </Box>
            {/* Tag Dialog */}
            <Dialog open={isTagDialogOpen} onClose={closeTagDialog} maxWidth="sm" fullWidth>
                <DialogTitle>{selectedTag ? 'Edit Tag' : 'Create Tag'}</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        variant="outlined"
                        size="small"
                        label="Name"
                        fullWidth
                        value={selectedTag?.name || ''}
                        onChange={(e) => setSelectedTag({ ...selectedTag, name: e.target.value })}
                    />
                    <FormControl fullWidth margin="dense">
                        <InputLabel id="tag-group-label">Tag Group</InputLabel>
                        <Select
                            labelId="tag-group-label"
                            value={selectedTag?.tagGroup || ''}
                            onChange={(e) => setSelectedTag({ ...selectedTag, tagGroup: e.target.value })}
                            label="Tag Group"
                        >
                            {tagGroups?.map((group) => (
                                <MenuItem key={group.id} value={group.name}>{group.name}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <FormControl fullWidth margin="dense">
                        <InputLabel id="tag-type-label">Tag Type</InputLabel>
                        <Select
                            labelId="tag-type-label"
                            value={selectedTag?.type || 'text'}
                            onChange={(e) => setSelectedTag({ ...selectedTag, type: e.target.value as 'text' | 'image' | 'audio' })}
                            label="Tag Type"
                        >
                            <MenuItem value="text">Text</MenuItem>
                            <MenuItem value="image">Image</MenuItem>
                            <MenuItem value="audio">Audio</MenuItem>
                        </Select>
                    </FormControl>
                    {selectedTag?.type === 'text' && (
                        <TextField
                            variant="outlined"
                            size="small"
                            label="Search Name"
                            fullWidth
                            value={selectedTag?.searchName || ''}
                            onChange={(e) => setSelectedTag({ ...selectedTag, searchName: e.target.value })}
                        />
                    )}
                    {(selectedTag?.type === 'image' || selectedTag?.type === 'audio') && (
                        <Box
                            sx={{
                                mt: 2,
                                p: 2,
                                border: '2px dashed #ccc',
                                borderRadius: 2,
                                textAlign: 'center',
                                cursor: 'pointer',
                            }}
                            onDragOver={handleDragOver}
                            onDrop={handleDrop}
                        >
                            <input
                                type="file"
                                accept={selectedTag?.type === 'image' ? 'image/*' : 'audio/*'}
                                style={{ display: 'none' }}
                                id="file-input"
                                onChange={handleFileChange}
                            />
                            <label htmlFor="file-input">
                                <Button
                                    variant="contained"
                                    component="span"
                                    startIcon={<CloudUploadIcon />}
                                >
                                    Choose File
                                </Button>
                            </label>
                            <Typography variant="body2" sx={{ mt: 1 }}>
                                {selectedFile ? `Selected file: ${selectedFile.name}` : 'Drag and drop a file here or click to select'}
                            </Typography>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={closeTagDialog}>Cancel</Button>
                    <Button onClick={() => {
                        if (selectedTag?.id) {
                            handleUpdateTag(selectedTag);
                        } else {
                            handleCreateTag({
                                ...selectedTag,
                                createdOn: new Date().toISOString().split('T')[0],
                            } as Omit<Tag, 'id'>);
                        }
                    }}>
                        {selectedTag?.id ? 'Update' : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Tag Group Dialog */}
            <Dialog open={isTagGroupDialogOpen} onClose={closeTagGroupDialog}>
                <DialogTitle>{selectedTagGroup ? 'Edit Tag Group' : 'Create Tag Group'}</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        label="Name"
                        fullWidth
                        value={selectedTagGroup?.name || ''}
                        onChange={(e) => setSelectedTagGroup({ ...selectedTagGroup, name: e.target.value })}
                    />
                    <TextField
                        label="Description"
                        fullWidth
                        multiline
                        rows={4}
                        value={selectedTagGroup?.description || ''}
                        onChange={(e) => setSelectedTagGroup({ ...selectedTagGroup, description: e.target.value })}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={closeTagGroupDialog}>Cancel</Button>
                    <Button onClick={() => {
                        if (selectedTagGroup?.id) {
                            handleUpdateTagGroup(selectedTagGroup);
                        } else {
                            handleCreateTagGroup({
                                ...selectedTagGroup,
                                createdOn: new Date().toISOString().split('T')[0],
                            } as Omit<TagGroup, 'id'>);
                        }
                    }}>
                        {selectedTagGroup?.id ? 'Update' : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default TagsPage;