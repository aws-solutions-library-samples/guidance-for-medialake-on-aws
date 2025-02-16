import React from 'react';
import { Box } from '@mui/material';
import { type ImageItem, type VideoItem, type AudioItem } from '@/types/search/searchResults';
import ImageResults from './ImageResults';
import VideoResults from './VideoResults';
import AudioResults from './AudioResults';

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
    DigitalSourceAsset: {
        Type: string;
    };
};

interface UnifiedAssetResultsProps {
    results: AssetItem[];
    searchMetadata: {
        totalResults: number;
        page: number;
        pageSize: number;
    };
    onPageChange: (page: number) => void;
    searchTerm: string;
    groupByType: boolean;
}

const UnifiedAssetResults: React.FC<UnifiedAssetResultsProps> = ({
    results,
    searchMetadata,
    onPageChange,
    searchTerm,
    groupByType
}) => {
    // Split results by type if grouping is enabled
    const imageResults = results.filter(item => item.DigitalSourceAsset.Type === 'Image') as ImageItem[];
    const videoResults = results.filter(item => item.DigitalSourceAsset.Type === 'Video') as VideoItem[];
    const audioResults = results.filter(item => item.DigitalSourceAsset.Type === 'Audio') as AudioItem[];

    if (groupByType) {
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {imageResults.length > 0 && (
                    <Box sx={{ 
                        '& .MuiPaper-root': {
                            bgcolor: 'transparent',
                            boxShadow: 'none',
                            p: 0
                        }
                    }}>
                        <ImageResults
                            images={imageResults}
                            searchMetadata={searchMetadata}
                            onPageChange={onPageChange}
                            searchTerm={searchTerm}
                        />
                    </Box>
                )}
                {videoResults.length > 0 && (
                    <Box sx={{ 
                        '& .MuiPaper-root': {
                            bgcolor: 'transparent',
                            boxShadow: 'none',
                            p: 0
                        }
                    }}>
                        <VideoResults
                            videos={videoResults}
                            searchMetadata={searchMetadata}
                            onPageChange={onPageChange}
                            searchTerm={searchTerm}
                        />
                    </Box>
                )}
                {audioResults.length > 0 && (
                    <Box sx={{ 
                        '& .MuiPaper-root': {
                            bgcolor: 'transparent',
                            boxShadow: 'none',
                            p: 0
                        }
                    }}>
                        <AudioResults
                            audios={audioResults}
                            searchMetadata={searchMetadata}
                            onPageChange={onPageChange}
                            searchTerm={searchTerm}
                        />
                    </Box>
                )}
            </Box>
        );
    }

    // When grouping is disabled, show all results in a single section
    // We'll use ImageResults as the base since it has the same card structure
    // Note: We need to cast the results to ImageItem[] since we're using ImageResults component
    return (
        <Box sx={{ 
            '& .MuiPaper-root': {
                bgcolor: 'transparent',
                boxShadow: 'none',
                p: 0
            }
        }}>
            <ImageResults
                images={results as ImageItem[]}
                searchMetadata={searchMetadata}
                onPageChange={onPageChange}
                searchTerm={searchTerm}
            />
        </Box>
    );
};

export default UnifiedAssetResults;