import React from 'react';
import { AudioItem, CardFieldConfig } from '@/types/search/searchResults';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetResults from '@/components/shared/AssetResults';
import { formatFileSize } from '@/utils/fileSize';
import { formatDate } from '@/utils/dateFormat';

interface AudioResultsProps {
    audios: AudioItem[];
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

const defaultColumns: AssetTableColumn<AudioItem>[] = [
    {
        id: 'name',
        label: 'Object Name',
        visible: true,
        minWidth: 300,
        accessor: (audio) => audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
    },
    {
        id: 'format',
        label: 'Format',
        visible: true,
        minWidth: 100,
        accessor: (audio) => audio.DigitalSourceAsset.MainRepresentation.Format,
    },
    {
        id: 'createDate',
        label: 'Created',
        visible: true,
        minWidth: 160,
        accessor: (audio) => audio.DigitalSourceAsset.CreateDate,
        format: (value: string) => formatDate(value),
    },
    {
        id: 'fileSize',
        label: 'Size',
        visible: false,
        minWidth: 100,
        accessor: (audio) => audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
        format: (value: number) => formatFileSize(value),
    },
];

const sortOptions = [
    { id: 'createDate', label: 'Created Date' },
    { id: 'name', label: 'Object Name' },
    { id: 'format', label: 'Format' },
    { id: 'fileSize', label: 'File Size' },
];

const renderCardField = (fieldId: string, audio: AudioItem): string => {
    switch (fieldId) {
        case 'name':
            return audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
        case 'format':
            return audio.DigitalSourceAsset.MainRepresentation.Format;
        case 'createDate':
            return formatDate(audio.DigitalSourceAsset.CreateDate);
        case 'fileSize':
            return formatFileSize(audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size);
        default:
            return '';
    }
};

const actions = [
    { id: 'rename', label: 'Rename' },
    { id: 'download', label: 'Download' },
    { id: 'share', label: 'Share' },
];

const AudioResults: React.FC<AudioResultsProps> = ({ audios, searchMetadata, onPageChange, searchTerm }) => {
    return (
        <AssetResults
            assets={audios}
            searchMetadata={searchMetadata}
            onPageChange={onPageChange}
            config={{
                assetType: 'Audio',
                defaultCardFields,
                defaultColumns,
                sortOptions,
                renderCardField,
                placeholderImage: 'https://placehold.co/300x200?text=Audio',
            }}
            searchTerm={searchTerm}
            actions={actions}
        />
    );
};

export default AudioResults;
