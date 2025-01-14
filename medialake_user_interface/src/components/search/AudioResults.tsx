import React from 'react';
import { AudioItem, CardFieldConfig } from '../../types/search/searchResults';
import { type AssetTableColumn } from '../../types/shared/assetComponents';
import AssetResults from '../shared/AssetResults';
import { formatFileSize } from '../../utils/fileSize';
import { formatDuration } from '../../utils/duration';

interface AudioResultsProps {
    audios: AudioItem[];
    searchMetadata: {
        totalResults: number;
        page: number;
        pageSize: number;
    };
    onPageChange: (page: number) => void;
}

const defaultCardFields: CardFieldConfig[] = [
    { id: 'name', label: 'Name', visible: true },
    { id: 'format', label: 'Format', visible: true },
    { id: 'duration', label: 'Duration', visible: true },
    { id: 'createDate', label: 'Created Date', visible: true },
    { id: 'fileSize', label: 'File Size', visible: false },
    { id: 'bitRate', label: 'Bit Rate', visible: false },
    { id: 'channels', label: 'Channels', visible: false },
];

const defaultColumns: AssetTableColumn<AudioItem>[] = [
    {
        id: 'name',
        label: 'Name',
        visible: true,
        minWidth: 200,
    },
    {
        id: 'format',
        label: 'Format',
        visible: true,
        minWidth: 100,
    },
    {
        id: 'duration',
        label: 'Duration',
        visible: true,
        minWidth: 100,
        format: (value: number) => formatDuration(value),
    },
    {
        id: 'bitRate',
        label: 'Bit Rate',
        visible: true,
        minWidth: 120,
        format: (value: number) => `${Math.round(value / 1000)} kbps`,
    },
    {
        id: 'channels',
        label: 'Channels',
        visible: true,
        minWidth: 100,
    },
    {
        id: 'createDate',
        label: 'Created',
        visible: true,
        minWidth: 120,
        format: (value: string) => new Date(value).toLocaleDateString(),
    },
    {
        id: 'fileSize',
        label: 'Size',
        visible: false,
        minWidth: 100,
        format: (value: number) => formatFileSize(value),
    },
];

const sortOptions = [
    { id: 'createDate', label: 'Created Date' },
    { id: 'name', label: 'Name' },
    { id: 'format', label: 'Format' },
    { id: 'duration', label: 'Duration' },
    { id: 'fileSize', label: 'File Size' },
    { id: 'bitRate', label: 'Bit Rate' },
];

const renderCardField = (fieldId: string, audio: AudioItem): string => {
    switch (fieldId) {
        case 'name':
            return audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
        case 'format':
            return audio.DigitalSourceAsset.MainRepresentation.Format;
        case 'duration':
            return formatDuration(audio.DigitalSourceAsset.MainRepresentation.TechnicalMetadata.Duration);
        case 'bitRate':
            return `${Math.round(audio.DigitalSourceAsset.MainRepresentation.TechnicalMetadata.BitRate / 1000)} kbps`;
        case 'channels':
            return `${audio.DigitalSourceAsset.MainRepresentation.TechnicalMetadata.Channels} ch`;
        case 'createDate':
            return new Date(audio.DigitalSourceAsset.CreateDate).toLocaleDateString();
        case 'fileSize':
            return formatFileSize(audio.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size);
        default:
            return '';
    }
};

const AudioResults: React.FC<AudioResultsProps> = ({ audios, searchMetadata, onPageChange }) => {
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
                placeholderImage: 'https://placehold.co/300x200',
            }}
        />
    );
};

export default AudioResults;
