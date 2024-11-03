import React from 'react';
import {
    AppBar,
    Toolbar,
    TextField,
    Button,
    Popover,
    Box,
    Typography,
    Grid,
    IconButton,
    FormControlLabel,
    Switch,
} from '@mui/material';
import { Search as SearchIcon, FilterList as FilterListIcon, Close as CloseIcon, Send as SendIcon, Logout as LogoutIcon } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useTopBar } from './components/TopBar/hooks/useTopBar';

function TopBar() {
    const {
        searchQuery,
        filterAnchorEl,
        filterOptions,
        setFilterOptions,
        chatVisible,
        handleSearchChange,
        handleFilterClick,
        handleFilterClose,
        handleSearchSubmit,
        handleLogout,
        handleChatToggle,
        handleDateChange
    } = useTopBar();

    return (
        <>
            <AppBar position="fixed">
                <Toolbar>
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', maxWidth: 1200, mx: 'auto' }}>
                        <Button
                            variant="contained"
                            startIcon={<FilterListIcon />}
                            onClick={handleFilterClick}
                            sx={{ mr: 2 }}
                        >
                            Filter
                        </Button>
                        <TextField
                            label="Search"
                            variant="outlined"
                            size="small"
                            value={searchQuery}
                            onChange={handleSearchChange}
                            onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                    handleSearchSubmit();
                                }
                            }}
                            sx={{ flexGrow: 1, mr: 2, bgcolor: 'background.paper' }}
                        />
                        <Button
                            variant="contained"
                            startIcon={<SearchIcon />}
                            onClick={handleSearchSubmit}
                            sx={{ mr: 2 }}
                        >
                            Search
                        </Button>
                        <IconButton
                            color="inherit"
                            onClick={handleLogout}
                            sx={{ ml: 'auto' }}
                        >
                            <LogoutIcon />
                        </IconButton>
                    </Box>
                </Toolbar>
            </AppBar>
            <Popover
                anchorEl={filterAnchorEl}
                open={Boolean(filterAnchorEl)}
                onClose={handleFilterClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'left',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'left',
                }}
                PaperProps={{
                    style: {
                        maxHeight: '70vh',
                        width: '100%',
                        maxWidth: 600,
                    },
                }}
            >
                <Box sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Filters</Typography>
                        <IconButton onClick={handleFilterClose} size="small">
                            <CloseIcon />
                        </IconButton>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={filterOptions.creationDate?.enabled}
                                    onChange={(event) =>
                                        setFilterOptions((prevState) => ({
                                            ...prevState,
                                            creationDate: { ...prevState.creationDate, enabled: event.target.checked },
                                        }))
                                    }
                                    name="creation-date-toggle"
                                />
                            }
                            label="Creation Date"
                        />
                        {filterOptions.creationDate?.enabled && (
                            <Grid container spacing={2} sx={{ mt: 1 }}>
                                <Grid item xs={12} sm={6}>
                                    <LocalizationProvider dateAdapter={AdapterDateFns}>
                                        <DatePicker
                                            label="After"
                                            value={filterOptions.creationDate.after}
                                            onChange={handleDateChange('after')}
                                        />
                                    </LocalizationProvider>
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <LocalizationProvider dateAdapter={AdapterDateFns}>
                                        <DatePicker
                                            label="Before"
                                            value={filterOptions.creationDate.before}
                                            onChange={handleDateChange('before')}
                                        />
                                    </LocalizationProvider>
                                </Grid>
                            </Grid>
                        )}
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <Button variant="contained" onClick={handleSearchSubmit}>
                            Apply Filters
                        </Button>
                    </Box>
                </Box>
            </Popover>
        </>
    );
}

export default TopBar;
