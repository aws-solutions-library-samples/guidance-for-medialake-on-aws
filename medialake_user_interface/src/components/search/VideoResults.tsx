import React from 'react';
import { VideoItem, CardFieldConfig } from '@/types/search/searchResults';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetResults from '@/components/shared/AssetResults';
import { formatFileSize } from '@/utils/fileSize';
import { formatDate } from '@/utils/dateFormat';

interface VideoResultsProps {
    videos: VideoItem[];
    searchMetadata: {
        totalResults: number;
        page: number;
        pageSize: number;
    };
    onPageChange: (page: number) => void;
    searchTerm: string;
}

const defaultCardFields: CardFieldConfig[] = [
    { id: 'name', label: 'Object Name', visible: true },
    { id: 'format', label: 'Format', visible: true },
    { id: 'createDate', label: 'Created Date', visible: true },
    { id: 'fileSize', label: 'File Size', visible: false },
];

const defaultColumns: AssetTableColumn<VideoItem>[] = [
    {
        id: 'name',
        label: 'Object Name',
        visible: true,
        minWidth: 300,
        accessor: (video) => video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
    },
    {
        id: 'format',
        label: 'Format',
        visible: true,
        minWidth: 100,
        accessor: (video) => video.DigitalSourceAsset.MainRepresentation.Format,
    },
    {
        id: 'createDate',
        label: 'Created',
        visible: true,
        minWidth: 160,
        accessor: (video) => video.DigitalSourceAsset.CreateDate,
        format: (value: string) => formatDate(value),
    },
    {
        id: 'fileSize',
        label: 'Size',
        visible: false,
        minWidth: 100,
        accessor: (video) => video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
        format: (value: number) => formatFileSize(value),
    },
];

const sortOptions = [
    { id: 'createDate', label: 'Created Date' },
    { id: 'name', label: 'Object Name' },
    { id: 'format', label: 'Format' },
    { id: 'fileSize', label: 'File Size' },
];

const renderCardField = (fieldId: string, video: VideoItem): string => {
    switch (fieldId) {
        case 'name':
            return video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
        case 'format':
            return video.DigitalSourceAsset.MainRepresentation.Format;
        case 'createDate':
            return formatDate(video.DigitalSourceAsset.CreateDate);
        case 'fileSize':
            return formatFileSize(video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size);
        default:
            return '';
    }
};

const actions = [
    { id: 'rename', label: 'Rename' },
    { id: 'download', label: 'Download' },
    { id: 'share', label: 'Share' },
];

const VideoResults: React.FC<VideoResultsProps> = ({ videos, searchMetadata, onPageChange, searchTerm }) => {
    return (
        <AssetResults
            assets={videos}
            searchMetadata={searchMetadata}
            onPageChange={onPageChange}
            config={{
                assetType: 'Video',
                defaultCardFields,
                defaultColumns,
                sortOptions,
                renderCardField,
                placeholderImage: 'https://placehold.co/300x200?text=Video',
            }}
            searchTerm={searchTerm}
            actions={actions}
        />
    );
};

export default VideoResults;
