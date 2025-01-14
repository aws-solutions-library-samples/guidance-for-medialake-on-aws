import React from 'react';
import { ImageItem, CardFieldConfig } from '../../types/search/searchResults';
import { type AssetTableColumn } from '../../types/shared/assetComponents';
import AssetResults from '../shared/AssetResults';
import { formatFileSize } from '../../utils/fileSize';

interface ImageResultsProps {
    images: ImageItem[];
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
    { id: 'createDate', label: 'Created Date', visible: true },
    { id: 'fileSize', label: 'File Size', visible: false },
];

const defaultColumns: AssetTableColumn<ImageItem>[] = [
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
    { id: 'fileSize', label: 'File Size' },
];

const renderCardField = (fieldId: string, image: ImageItem): string => {
    switch (fieldId) {
        case 'name':
            return image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
        case 'format':
            return image.DigitalSourceAsset.MainRepresentation.Format;
        case 'createDate':
            return new Date(image.DigitalSourceAsset.CreateDate).toLocaleDateString();
        case 'fileSize':
            return formatFileSize(image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size);
        default:
            return '';
    }
};

const ImageResults: React.FC<ImageResultsProps> = ({ images, searchMetadata, onPageChange }) => {
    return (
        <AssetResults
            assets={images}
            searchMetadata={searchMetadata}
            onPageChange={onPageChange}
            config={{
                assetType: 'Image',
                defaultCardFields,
                defaultColumns,
                sortOptions,
                renderCardField,
                placeholderImage: 'https://placehold.co/300x200',
            }}
        />
    );
};

export default ImageResults;
