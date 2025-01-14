import React, { useState, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import AssetSidebar from '../components/asset/AssetSidebar';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import AssetImage from '../components/asset/AssetImage';
import AssetMetadataTabs from '../components/asset/AssetMetadataTabs';

const ImageDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const searchTerm = searchParams.get('searchTerm') || '';
    const { isExpanded } = useRightSidebar();

    const formatFileSize = (size: number) => {
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    };

    const representations = useMemo(() => {
        if (!assetData?.data?.asset) return [];

        const formatFileSize = (size: number) => {
            if (size < 1024) return `${size} B`;
            if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
            return `${(size / (1024 * 1024)).toFixed(1)} MB`;
        };

        const mainRep = assetData.data.asset.DigitalSourceAsset.MainRepresentation;
        const mainSize = mainRep.StorageInfo.PrimaryLocation.FileInfo.Size;

        const allRepresentations = [
            {
                id: mainRep.ID,
                src: mainRep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: mainRep.Purpose,
                format: mainRep.Format,
                fileSize: formatFileSize(mainSize),
                description: `${mainRep.Format} file - ${formatFileSize(mainSize)}`,
            },
            ...assetData.data.asset.DerivedRepresentations.map(rep => {
                const size = rep.StorageInfo.PrimaryLocation.FileInfo.Size;
                let description = `${rep.Format} file - ${formatFileSize(size)}`;

                if (rep.ImageSpec?.Resolution) {
                    description += ` - ${rep.ImageSpec.Resolution.Width}x${rep.ImageSpec.Resolution.Height}`;
                }

                return {
                    id: rep.ID,
                    src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                    type: rep.Purpose,
                    format: rep.Format,
                    fileSize: formatFileSize(size),
                    description,
                };
            })
        ];

        return allRepresentations;
    }, [assetData]);

    const metadataFields = useMemo(() => {
        if (!assetData?.data?.asset) return {
            summary: [],
            descriptive: [],
            technical: []
        };

        const { asset } = assetData.data;
        const mainRep = asset.DigitalSourceAsset.MainRepresentation;
        const customMetadata = asset.Metadata.CustomMetadata as any;

        const formatFileSize = (size: number) => {
            if (size < 1024) return `${size} B`;
            if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
            return `${(size / (1024 * 1024)).toFixed(1)} MB`;
        };

        // Get image dimensions from either ihdr or ifd0
        const dimensions = (() => {
            if (customMetadata?.ihdr) {
                return {
                    width: customMetadata.ihdr['Image Width'],
                    height: customMetadata.ihdr['Image Height']
                };
            } else if (customMetadata?.ifd0) {
                return {
                    width: customMetadata.ifd0['Image Width'],
                    height: customMetadata.ifd0['Image Height']
                };
            }
            return null;
        })();

        const summary = [
            { label: 'Type', value: asset.DigitalSourceAsset.Type },
            { label: 'Format', value: mainRep.Format },
            { label: 'File Size', value: formatFileSize(mainRep.StorageInfo.PrimaryLocation.FileInfo.Size) }
        ];

        if (dimensions) {
            summary.push({ label: 'Dimensions', value: `${dimensions.width} × ${dimensions.height}` });
        }

        const technical = [
            { label: 'Content Type', value: (asset.Metadata as any).Embedded?.S3.ContentType },
            { label: 'Last Modified', value: new Date((asset.Metadata as any).Embedded?.S3.LastModified).toLocaleString() }
        ];

        // Add IHDR metadata if available
        if (customMetadata?.ihdr) {
            technical.push(
                { label: 'Color Type', value: customMetadata.ihdr['Color Type'] },
                { label: 'Bit Depth', value: customMetadata.ihdr['Bit Depth'] },
                { label: 'Compression', value: customMetadata.ihdr['Compression'] },
                { label: 'Filter', value: customMetadata.ihdr['Filter'] },
                { label: 'Interlace', value: customMetadata.ihdr['Interlace'] }
            );
        }

        // Add IFD0 metadata if available
        if (customMetadata?.ifd0) {
            technical.push(
                { label: 'Compression', value: customMetadata.ifd0['Compression'] },
                { label: 'Orientation', value: customMetadata.ifd0['Orientation'] },
                { label: 'Samples Per Pixel', value: customMetadata.ifd0['Samples Per Pixel'] },
                {
                    label: 'Bits Per Sample', value: Array.isArray(customMetadata.ifd0['Bits Per Sample'])
                        ? customMetadata.ifd0['Bits Per Sample'].join(', ')
                        : typeof customMetadata.ifd0['Bits Per Sample'] === 'object'
                            ? Object.values(customMetadata.ifd0['Bits Per Sample']).join(', ')
                            : customMetadata.ifd0['Bits Per Sample']
                }
            );
        }

        // Add storage information
        technical.push(
            { label: 'Storage Type', value: mainRep.StorageInfo.PrimaryLocation.StorageType },
            { label: 'Storage Status', value: mainRep.StorageInfo.PrimaryLocation.Status },
            { label: 'Storage Bucket', value: mainRep.StorageInfo.PrimaryLocation.Bucket },
            { label: 'Hash Algorithm', value: mainRep.StorageInfo.PrimaryLocation.FileInfo.Hash?.Algorithm || 'N/A' },
            { label: 'Hash Value', value: mainRep.StorageInfo.PrimaryLocation.FileInfo.Hash?.Value || 'N/A' }
        );

        return {
            summary,
            descriptive: [
                { label: 'Created Date', value: new Date(asset.DigitalSourceAsset.CreateDate).toLocaleString() },
                { label: 'File Path', value: mainRep.StorageInfo.PrimaryLocation.ObjectKey.FullPath }
            ],
            technical
        };
    }, [assetData]);

    const activityLog = useMemo(() => {
        if (!assetData?.data?.asset) return [];

        const { asset } = assetData.data;
        return [
            {
                user: "System",
                action: "Asset Created",
                timestamp: new Date(asset.DigitalSourceAsset.CreateDate).toLocaleString()
            }
        ];
    }, [assetData]);

    // Track this asset in recently viewed
    useTrackRecentlyViewed(
        assetData ? {
            id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            title: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "image" | "video",
            path: `/assets/${id}`,
            metadata: {
                fileSize: formatFileSize(assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size),
                dimensions: assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution
                    ? `${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Width}x${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Height}`
                    : undefined
            }
        } : null
    );

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error || !assetData) {
        return (
            <Box sx={{ p: 3 }}>
                <div>Error loading asset data</div>
            </Box>
        );
    }

    const proxyUrl = (() => {
        const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
        return proxyRep?.URL || assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath;
    })();

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            height: '100vh',
            maxWidth: isExpanded ? 'calc(100% - 300px)' : 'calc(100% - 8px)',
            transition: theme => theme.transitions.create(['max-width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Header section */}
            <BreadcrumbNavigation
                searchTerm={searchTerm}
                currentResult={48}
                totalResults={156}
                onBack={() => navigate(-1)}
                onPrevious={() => navigate(-1)}
                onNext={() => navigate(1)}
            />
            <Box sx={{ px: 3, pt: 2, bgcolor: 'background.default' }}>
                <AssetHeader />
            </Box>

            {/* Scrollable content */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                overflow: 'auto',
                gap: 3,
                px: 3,
                pb: 3
            }}>
                {/* Fixed image section */}
                <Box sx={{
                    position: 'sticky',
                    top: 120,
                    zIndex: 1100,
                    bgcolor: 'background.default',
                    pt: 2
                }}>
                    <AssetImage
                        src={proxyUrl}
                        alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
                    />
                </Box>

                {/* Scrollable metadata section */}
                <Box sx={{ flex: 1 }}>
                    <AssetMetadataTabs
                        summary={metadataFields.summary}
                        descriptive={metadataFields.descriptive}
                        technical={metadataFields.technical}
                        activityLog={activityLog}
                    />
                </Box>
            </Box>

            <AssetSidebar versions={representations} />
        </Box>
    );
};

const ImageDetailPage: React.FC = () => {
    return (
        <RecentlyViewedProvider>
            <RightSidebarProvider>
                <ImageDetailContent />
            </RightSidebarProvider>
        </RecentlyViewedProvider>
    );
};

export default ImageDetailPage;
