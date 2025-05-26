import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  CardActions,
  Grid,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  InputAdornment,
  Divider,
  Snackbar,
  FormHelperText,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import { useTranslation } from 'react-i18next';
import { PageHeader, PageContent } from '@/components/common/layout';
import { useGetPermissionSets, useCreatePermissionSet, useUpdatePermissionSet, useDeletePermissionSet } from '@/api/hooks/usePermissionSets';
import { PermissionSet, Permission, CreatePermissionSetRequest } from '@/api/types/permissionSet.types';

// Helper function to determine if a permission is allowed or denied
const getPermissionStatus = (permissions: any, action: string, resource: string): 'Allowed' | 'Denied' | 'Not Set' => {
  // Handle permissions as an object with boolean properties
  if (permissions && typeof permissions === 'object' && !Array.isArray(permissions)) {
    // Check if there's a key like "resource.action" (e.g., "asset.view")
    const key = `${resource}.${action}`;
    if (key in permissions) {
      return permissions[key] ? 'Allowed' : 'Denied';
    }
    return 'Not Set';
  }
  
  // Handle permissions as an array of Permission objects
  if (Array.isArray(permissions)) {
    const permission = permissions.find(p => p.action === action && p.resource === resource);
    if (!permission) return 'Not Set';
    return permission.effect === 'Allow' ? 'Allowed' : 'Denied';
  }
  
  return 'Not Set';
};

// Component to display permission status
const PermissionStatus: React.FC<{ status: 'Allowed' | 'Denied' | 'Not Set' }> = ({ status }) => {
  const color = status === 'Allowed' ? 'success' : status === 'Denied' ? 'error' : 'default';
  return <Chip label={status} size="small" color={color} variant="outlined" />;
};

// Permission Set Card Component
const PermissionSetCard: React.FC<{
  permissionSet: PermissionSet;
  onEdit: (permissionSet: PermissionSet) => void;
  onDelete: (permissionSet: PermissionSet) => void;
}> = ({ permissionSet, onEdit, onDelete }) => {
  // Standard actions to display
  const standardActions = ['View', 'Edit', 'Delete', 'Share', 'Download', 'Upload'];
  // Standard resource to display
  const standardResource = 'Asset';

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" component="div" gutterBottom>
          {permissionSet.name}
          {permissionSet.isSystem && (
            <Chip
              label="System"
              size="small"
              color="primary"
              variant="outlined"
              sx={{ ml: 1, verticalAlign: 'middle' }}
            />
          )}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {permissionSet.description}
        </Typography>
        
        <Box mt={2}>
          <Typography variant="subtitle2" gutterBottom>
            Applied To
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {/* Placeholder for applied resources */}
            All resources
          </Typography>
        </Box>
        
        <Box mt={2}>
          <Typography variant="subtitle2" gutterBottom>
            Permission Definitions
          </Typography>
          <Grid container spacing={1}>
            {standardActions.map(action => (
              <Grid item xs={6} key={action}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="body2">{action}</Typography>
                  <PermissionStatus
                    status={getPermissionStatus(permissionSet.permissions, action.toLowerCase(), standardResource.toLowerCase())}
                  />
                </Box>
              </Grid>
            ))}
          </Grid>
        </Box>
      </CardContent>
      <CardActions>
        <Button
          size="small"
          startIcon={<EditIcon />}
          onClick={() => onEdit(permissionSet)}
        >
          Edit Permission Set
        </Button>
        {!permissionSet.isSystem && (
          <Button
            size="small"
            startIcon={<DeleteIcon />}
            onClick={() => onDelete(permissionSet)}
            color="error"
          >
            Delete
          </Button>
        )}
      </CardActions>
    </Card>
  );
};

// Add New Permission Set Card Component
const AddNewPermissionSetCard: React.FC<{
  onClick: () => void;
}> = ({ onClick }) => {
  return (
    <Card 
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        border: '2px dashed #ccc',
        backgroundColor: 'background.paper'
      }}
      onClick={onClick}
    >
      <CardContent sx={{ textAlign: 'center' }}>
        <AddIcon sx={{ fontSize: 40, color: 'primary.main', mb: 2 }} />
        <Typography variant="h6" component="div">
          Add New Permission Set
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Create a custom permission set
        </Typography>
      </CardContent>
    </Card>
  );
};

// Permission Set Form Dialog Component
const PermissionSetFormDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onSave: (data: CreatePermissionSetRequest) => void;
  permissionSet?: PermissionSet;
}> = ({ open, onClose, onSave, permissionSet }) => {
  const [name, setName] = useState(permissionSet?.name || '');
  const [description, setDescription] = useState(permissionSet?.description || '');
  const [permissions, setPermissions] = useState<Permission[]>(permissionSet?.permissions || []);
  
  // Form validation
  const [nameError, setNameError] = useState('');
  
  // New permission fields
  const [newAction, setNewAction] = useState('');
  const [newResource, setNewResource] = useState('');
  const [newEffect, setNewEffect] = useState<'Allow' | 'Deny'>('Allow');
  
  // Common actions and resources for quick selection
  const commonActions = ['view', 'edit', 'delete', 'share', 'download', 'upload'];
  const commonResources = ['asset', 'collection', 'pipeline', 'node'];

  // Reset form when dialog opens/closes or permission set changes
  React.useEffect(() => {
    if (open) {
      setName(permissionSet?.name || '');
      setDescription(permissionSet?.description || '');
      setPermissions(permissionSet?.permissions || []);
      setNameError('');
      setNewAction('');
      setNewResource('');
      setNewEffect('Allow');
    }
  }, [open, permissionSet]);

  const validateForm = (): boolean => {
    let isValid = true;
    
    if (!name.trim()) {
      setNameError('Name is required');
      isValid = false;
    } else {
      setNameError('');
    }
    
    return isValid;
  };

  const handleAddPermission = () => {
    if (!newAction || !newResource) return;
    
    // Check if permission already exists
    const existingIndex = permissions.findIndex(
      p => p.action === newAction && p.resource === newResource
    );
    
    if (existingIndex >= 0) {
      // Update existing permission
      const updatedPermissions = [...permissions];
      updatedPermissions[existingIndex] = {
        ...updatedPermissions[existingIndex],
        effect: newEffect
      };
      setPermissions(updatedPermissions);
    } else {
      // Add new permission
      setPermissions([
        ...permissions,
        {
          action: newAction,
          resource: newResource,
          effect: newEffect
        }
      ]);
    }
    
    // Reset fields
    setNewAction('');
    setNewResource('');
    setNewEffect('Allow');
  };

  const handleRemovePermission = (index: number) => {
    const updatedPermissions = [...permissions];
    updatedPermissions.splice(index, 1);
    setPermissions(updatedPermissions);
  };

  const handleSave = () => {
    if (!validateForm()) return;
    
    onSave({
      name,
      description,
      permissions
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{permissionSet ? 'Edit Permission Set' : 'Add Permission Set'}</DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            margin="normal"
            required
            error={!!nameError}
            helperText={nameError}
          />
          <TextField
            fullWidth
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            margin="normal"
            multiline
            rows={3}
          />
          
          <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
            Permissions
          </Typography>
          
          <Box sx={{ mb: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Add Permission
            </Typography>
            
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} sm={4}>
                <FormControl fullWidth margin="dense">
                  <InputLabel id="action-label">Action</InputLabel>
                  <Select
                    labelId="action-label"
                    value={newAction}
                    onChange={(e) => setNewAction(e.target.value)}
                    label="Action"
                  >
                    {commonActions.map(action => (
                      <MenuItem key={action} value={action}>{action}</MenuItem>
                    ))}
                    <MenuItem value=""><em>Custom...</em></MenuItem>
                  </Select>
                </FormControl>
                {newAction === '' && (
                  <TextField
                    fullWidth
                    label="Custom Action"
                    margin="dense"
                    onChange={(e) => setNewAction(e.target.value)}
                    placeholder="e.g., approve"
                  />
                )}
              </Grid>
              
              <Grid item xs={12} sm={4}>
                <FormControl fullWidth margin="dense">
                  <InputLabel id="resource-label">Resource</InputLabel>
                  <Select
                    labelId="resource-label"
                    value={newResource}
                    onChange={(e) => setNewResource(e.target.value)}
                    label="Resource"
                  >
                    {commonResources.map(resource => (
                      <MenuItem key={resource} value={resource}>{resource}</MenuItem>
                    ))}
                    <MenuItem value=""><em>Custom...</em></MenuItem>
                  </Select>
                </FormControl>
                {newResource === '' && (
                  <TextField
                    fullWidth
                    label="Custom Resource"
                    margin="dense"
                    onChange={(e) => setNewResource(e.target.value)}
                    placeholder="e.g., workflow"
                  />
                )}
              </Grid>
              
              <Grid item xs={12} sm={2}>
                <FormControl fullWidth margin="dense">
                  <InputLabel id="effect-label">Effect</InputLabel>
                  <Select
                    labelId="effect-label"
                    value={newEffect}
                    onChange={(e) => setNewEffect(e.target.value as 'Allow' | 'Deny')}
                    label="Effect"
                  >
                    <MenuItem value="Allow">Allow</MenuItem>
                    <MenuItem value="Deny">Deny</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={2}>
                <Button
                  variant="contained"
                  onClick={handleAddPermission}
                  disabled={!newAction || !newResource}
                  fullWidth
                  sx={{ mt: 1 }}
                >
                  Add
                </Button>
              </Grid>
            </Grid>
          </Box>
          
          <Typography variant="subtitle1" gutterBottom>
            Current Permissions
          </Typography>
          
          {permissions.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No permissions defined yet. Add permissions using the form above.
            </Typography>
          ) : (
            <List>
              {permissions.map((permission, index) => (
                <ListItem
                  key={index}
                  secondaryAction={
                    <IconButton edge="end" aria-label="delete" onClick={() => handleRemovePermission(index)}>
                      <RemoveCircleOutlineIcon />
                    </IconButton>
                  }
                  sx={{
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    mb: 1,
                    backgroundColor: permission.effect === 'Allow' ? 'rgba(76, 175, 80, 0.08)' : 'rgba(244, 67, 54, 0.08)'
                  }}
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center">
                        <Typography variant="body1">
                          {permission.action} {permission.resource}
                        </Typography>
                        <Chip
                          label={permission.effect}
                          size="small"
                          color={permission.effect === 'Allow' ? 'success' : 'error'}
                          sx={{ ml: 1 }}
                        />
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          {permissionSet ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// Delete Confirmation Dialog
const DeleteConfirmationDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  permissionSet?: PermissionSet;
}> = ({ open, onClose, onConfirm, permissionSet }) => {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Delete Permission Set</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to delete the permission set "{permissionSet?.name}"? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} color="error" variant="contained">
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// Main Permission Sets Page Component
const PermissionSetsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [openPermissionSetForm, setOpenPermissionSetForm] = useState(false);
  const [editingPermissionSet, setEditingPermissionSet] = useState<PermissionSet | undefined>();
  const [deletingPermissionSet, setDeletingPermissionSet] = useState<PermissionSet | undefined>();
  const [openDeleteDialog, setOpenDeleteDialog] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
  }>({
    open: false,
    message: '',
    severity: 'info'
  });

  // API Hooks
  const { data: permissionSets, isLoading, error } = useGetPermissionSets();
  const createPermissionSetMutation = useCreatePermissionSet();
  const updatePermissionSetMutation = useUpdatePermissionSet();
  const deletePermissionSetMutation = useDeletePermissionSet();

  // Filter permission sets based on search term and category
  const filteredPermissionSets = permissionSets?.filter(ps => {
    const matchesSearch = searchTerm === '' ||
      ps.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ps.description.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesCategory = filterCategory === 'all' ||
      (filterCategory === 'system' && ps.isSystem) ||
      (filterCategory === 'custom' && !ps.isSystem);
    
    return matchesSearch && matchesCategory;
  });

  const handleAddPermissionSet = () => {
    setEditingPermissionSet(undefined);
    setOpenPermissionSetForm(true);
  };

  const handleEditPermissionSet = (permissionSet: PermissionSet) => {
    setEditingPermissionSet(permissionSet);
    setOpenPermissionSetForm(true);
  };

  const handleDeletePermissionSet = (permissionSet: PermissionSet) => {
    setDeletingPermissionSet(permissionSet);
    setOpenDeleteDialog(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingPermissionSet) return;
    
    try {
      await deletePermissionSetMutation.mutateAsync(deletingPermissionSet.id);
      setSnackbar({
        open: true,
        message: `Permission set "${deletingPermissionSet.name}" has been deleted.`,
        severity: 'success'
      });
    } catch (err) {
      console.error('Error deleting permission set:', err);
      setSnackbar({
        open: true,
        message: `Failed to delete permission set: ${(err as Error).message}`,
        severity: 'error'
      });
    } finally {
      setOpenDeleteDialog(false);
      setDeletingPermissionSet(undefined);
    }
  };

  const handleSavePermissionSet = async (data: CreatePermissionSetRequest) => {
    try {
      if (editingPermissionSet) {
        await updatePermissionSetMutation.mutateAsync({
          id: editingPermissionSet.id,
          updates: data
        });
        setSnackbar({
          open: true,
          message: `Permission set "${data.name}" has been updated.`,
          severity: 'success'
        });
      } else {
        await createPermissionSetMutation.mutateAsync(data);
        setSnackbar({
          open: true,
          message: `Permission set "${data.name}" has been created.`,
          severity: 'success'
        });
      }
      setOpenPermissionSetForm(false);
    } catch (err) {
      console.error('Error saving permission set:', err);
      setSnackbar({
        open: true,
        message: `Failed to save permission set: ${(err as Error).message}`,
        severity: 'error'
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  return (
    <Box sx={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      flex: 1,
      width: '100%',
      position: 'relative',
      maxWidth: '100%',
      p: 3,
    }}>
      <PageHeader
        title="Resource-Centric Permission Matrix"
        description="Manage permission sets to control access to resources"
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddPermissionSet}
            sx={{
              borderRadius: '8px',
              textTransform: 'none',
              px: 3,
              height: 40
            }}
          >
            Add Permission Set
          </Button>
        }
      />

      {/* Search and Filters */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <TextField
          placeholder="Search permission sets..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          sx={{ flexGrow: 1, minWidth: '200px' }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
        
        <FormControl sx={{ minWidth: '150px' }}>
          <InputLabel id="category-filter-label">Category</InputLabel>
          <Select
            labelId="category-filter-label"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            label="Category"
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="system">System</MenuItem>
            <MenuItem value="custom">Custom</MenuItem>
          </Select>
        </FormControl>
        
        <Button 
          variant="outlined" 
          startIcon={<FilterListIcon />}
          sx={{ height: '56px' }}
        >
          Filters
        </Button>
      </Box>

      <PageContent
        isLoading={isLoading}
        error={error as Error}
      >
        <Grid container spacing={3}>
          {/* Add New Permission Set Card */}
          <Grid item xs={12} sm={6} md={4}>
            <AddNewPermissionSetCard onClick={handleAddPermissionSet} />
          </Grid>
          
          {/* Permission Set Cards */}
          {filteredPermissionSets?.map((permissionSet) => (
            <Grid item xs={12} sm={6} md={4} key={permissionSet.id}>
              <PermissionSetCard
                permissionSet={permissionSet}
                onEdit={handleEditPermissionSet}
                onDelete={handleDeletePermissionSet}
              />
            </Grid>
          ))}
        </Grid>
      </PageContent>

      {/* Permission Set Form Dialog */}
      <PermissionSetFormDialog
        open={openPermissionSetForm}
        onClose={() => setOpenPermissionSetForm(false)}
        onSave={handleSavePermissionSet}
        permissionSet={editingPermissionSet}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        open={openDeleteDialog}
        onClose={() => setOpenDeleteDialog(false)}
        onConfirm={handleConfirmDelete}
        permissionSet={deletingPermissionSet}
      />

      {/* Snackbar for feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default PermissionSetsPage;