import React from 'react';
import { ImageItem, CardFieldConfig } from '../../types/search/searchResults';
import { type AssetTableColumn } from '../../types/shared/assetComponents';
import AssetResults from '../shared/AssetResults';
import { formatFileSize } from '../../utils/fileSize';
import { formatDate } from '../../utils/dateFormat';

interface ImageResultsProps {
    images: ImageItem[];
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

const defaultColumns: AssetTableColumn<ImageItem>[] = [
    {
        id: 'name',
        label: 'Object Name',
        visible: true,
        minWidth: 300,
        accessor: (image) => image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
    },
    {
        id: 'format',
        label: 'Format',
        visible: true,
        minWidth: 100,
        accessor: (image) => image.DigitalSourceAsset.MainRepresentation.Format,
    },
    {
        id: 'createDate',
        label: 'Created',
        visible: true,
        minWidth: 160,
        accessor: (image) => image.DigitalSourceAsset.CreateDate,
        format: (value: string) => formatDate(value),
    },
    {
        id: 'fileSize',
        label: 'Size',
        visible: false,
        minWidth: 100,
        accessor: (image) => image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
        format: (value: number) => formatFileSize(value),
    },
];

const sortOptions = [
    { id: 'createDate', label: 'Created Date' },
    { id: 'name', label: 'Object Name' },
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
            return formatDate(image.DigitalSourceAsset.CreateDate);
        case 'fileSize':
            return formatFileSize(image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size);
        default:
            return '';
    }
};

const ImageResults: React.FC<ImageResultsProps> = ({ images, searchMetadata, onPageChange, searchTerm }) => {
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
                placeholderImage: 'https://via.placeholder.com/400x300',
            }}
            searchTerm={searchTerm}
        />
    );
};

export default ImageResults;
