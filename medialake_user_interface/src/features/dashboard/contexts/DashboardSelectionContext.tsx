import React, { createContext, useContext, ReactNode } from "react";
import { useAssetSelection } from "@/hooks/useAssetSelection";

// Type for assets in the dashboard
interface DashboardAsset {
  InventoryID: string;
  DigitalSourceAsset?: {
    Type?: string;
    MainRepresentation?: {
      StorageInfo?: {
        PrimaryLocation?: {
          ObjectKey?: {
            Name?: string;
          };
        };
      };
    };
  };
  type?: string;
  name?: string;
  metadata?: {
    name?: string;
    assetType?: string;
  };
}

// Helper functions to extract asset properties
const getAssetId = (asset: DashboardAsset): string => {
  return asset.InventoryID || "";
};

const getAssetName = (asset: DashboardAsset): string => {
  return (
    asset.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name ||
    asset.metadata?.name ||
    asset.name ||
    "Untitled"
  );
};

const getAssetType = (asset: DashboardAsset): string => {
  return asset.DigitalSourceAsset?.Type || asset.metadata?.assetType || asset.type || "Unknown";
};

// Context type
type DashboardSelectionContextType = ReturnType<typeof useAssetSelection<DashboardAsset>>;

const DashboardSelectionContext = createContext<DashboardSelectionContextType | null>(null);

interface DashboardSelectionProviderProps {
  children: ReactNode;
  onDownloadSuccess?: () => void;
}

export const DashboardSelectionProvider: React.FC<DashboardSelectionProviderProps> = ({
  children,
  onDownloadSuccess,
}) => {
  const assetSelection = useAssetSelection<DashboardAsset>({
    getAssetId,
    getAssetName,
    getAssetType,
    onDownloadSuccess,
  });

  return (
    <DashboardSelectionContext.Provider value={assetSelection}>
      {children}
    </DashboardSelectionContext.Provider>
  );
};

export const useDashboardSelection = (): DashboardSelectionContextType | null => {
  const context = useContext(DashboardSelectionContext);
  // Return null if not within provider - widgets can handle this gracefully
  return context;
};

// Strict version that throws if not within provider - use in components that require selection
export const useDashboardSelectionRequired = (): DashboardSelectionContextType => {
  const context = useContext(DashboardSelectionContext);
  if (!context) {
    throw new Error(
      "useDashboardSelectionRequired must be used within a DashboardSelectionProvider"
    );
  }
  return context;
};
