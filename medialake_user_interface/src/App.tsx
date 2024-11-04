import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { Box } from '@mui/material';
import TopBar from './TopBar';
import Sidebar from './Sidebar';
import SettingsComponent from './SettingsComponent';
import PipelinesPage from './PipelinesPage';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import ExecutionStatusPage from './ExecutionStatusPage';
import Home from './pages/Home';
import SearchResults from './components/SearchResults';
import TagsPage from './TagsPage';
import ReviewQueue from './reviewQueue'; // New import for ReviewQueue component
import NewPipelinePage from './NewPipelinePage';
import ImageDetailPage from './ImageDetailPage'; // New import for ImageDetailPage
import { useAuth } from "./common/hooks/auth-context";

function App() {
  const [selectedImage, setSelectedImage] = useState(null);
  const { refreshSession } = useAuth();

  const handleImageSelect = (image) => {
    setSelectedImage(image);
  };

  return (
    <Router>
      <Box sx={{ display: 'flex' }}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <TopBar />
        </LocalizationProvider>
        <Sidebar />
        <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<SearchResults onImageSelect={handleImageSelect} />} />
            <Route path="/settings" element={<SettingsComponent />} />
            <Route path="/pipelines" element={<PipelinesPage />} />
            <Route path="/pipelines/new" element={<NewPipelinePage />} />
            <Route path="/pipelines/edit/:id" element={<NewPipelinePage />} />            <Route path="/execution-status" element={<ExecutionStatusPage />} />
            <Route path="/tags" element={<TagsPage />} />
            <Route path="/review-queue" element={<ReviewQueue />} /> {/* New route for ReviewQueue */}
            <Route path="/image-detail" element={<ImageDetailPage image={selectedImage} />} />
          </Routes>
        </Box>
      </Box>
    </Router>
  );
}

export default App;
