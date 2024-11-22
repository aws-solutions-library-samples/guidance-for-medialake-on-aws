import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import TopBar from './TopBar';
import Sidebar from './Sidebar';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import ExecutionsPage from './pages/ExecutionsPage';
import Home from './pages/Home';
import SearchPage from './pages/SearchPage';
import TagsPage from './pages/TagsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import ImageDetailPage from './pages/ImageDetailPage';
import SettingsPage from './pages/SettingsPage';
import UserManagement from './pages/settings/UserManagement';
import { useAuth } from "./common/hooks/auth-context";
import ErrorBoundary from './components/ErrorBoundary';

function App() {
  const { refreshSession } = useAuth();

  return (
    <Router>
      <Box sx={{ display: 'flex' }}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <TopBar />
        </LocalizationProvider>
        <Sidebar />
        <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/users" element={<UserManagement />} />
            <Route path="/executions" element={<ExecutionsPage />} />
            <Route path="/tags" element={<TagsPage />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} />
            <Route path="/images/:id" element={<ImageDetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Box>
      </Box>
    </Router>
  );
}

export default App;
