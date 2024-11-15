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
          {/* <Routes>
            <Route path="/" element={<Home />} errorElement={<ErrorBoundary />} />
            <Route path="/search" element={<SearchPage />} errorElement={<ErrorBoundary />} />
            <Route path="/settings/*" element={<SettingsPage />} errorElement={<ErrorBoundary />} />
            <Route path="/pipelines" element={<PipelinesPage />} errorElement={<ErrorBoundary />} />
            <Route
              path="/pipeline-editor"
              element={<PipelineEditorPage />}
              errorElement={<ErrorBoundary />}
            />
            <Route
              path="/pipeline-editor/:id"
              element={<PipelineEditorPage />}
              errorElement={<ErrorBoundary />}
            />
            <Route path="/executions" element={<ExecutionsPage />} errorElement={<ErrorBoundary />} />
            <Route path="/tags" element={<TagsPage />} errorElement={<ErrorBoundary />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} errorElement={<ErrorBoundary />} />
            <Route path="/images/:id" element={<ImageDetailPage />} errorElement={<ErrorBoundary />} />
            <Route path="*" element={<Navigate to="/" replace />} errorElement={<ErrorBoundary />} />
          </Routes> */}
        </Box>
      </Box>
    </Router>
  );
}

export default App;
