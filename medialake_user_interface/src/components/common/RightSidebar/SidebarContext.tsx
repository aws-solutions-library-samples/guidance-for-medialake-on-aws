import React, {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
} from "react";
import { useFeatureFlag } from "@/utils/featureFlags";

// Default width values
export const DEFAULT_WIDTH = 375;
export const COLLAPSED_WIDTH = 24;

interface RightSidebarContextType {
  isExpanded: boolean;
  setIsExpanded: (expanded: boolean) => void;
  openSidebar: () => void;
  closeSidebar: () => void;
  width: number;
  setWidth: (width: number) => void;
  hasSelectedItems: boolean;
  setHasSelectedItems: (hasItems: boolean) => void;
}

const RightSidebarContext = createContext<RightSidebarContextType | undefined>(
  undefined,
);

interface RightSidebarProviderProps {
  children: ReactNode;
}

export const RightSidebarProvider: React.FC<RightSidebarProviderProps> = ({
  children,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasSelectedItems, setHasSelectedItems] = useState(false);

  // Check if multi-select feature is enabled
  const multiSelectFeature = useFeatureFlag(
    "search-multi-select-enabled",
    false,
  );

  const openSidebar = () => setIsExpanded(true);
  const closeSidebar = () => setIsExpanded(false);

  const [width, setWidth] = useState(DEFAULT_WIDTH);

  // Load saved width on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem("rightSidebarWidth");
    if (savedWidth) {
      const parsedWidth = parseInt(savedWidth, 10);
      if (!isNaN(parsedWidth)) {
        setWidth(parsedWidth);
      }
    }
  }, []);

  // Note: Removed automatic sidebar opening when items are selected
  // Users can now manually control sidebar visibility regardless of selection state

  return (
    <RightSidebarContext.Provider
      value={{
        isExpanded,
        setIsExpanded,
        openSidebar,
        closeSidebar,
        width,
        setWidth,
        hasSelectedItems,
        setHasSelectedItems,
      }}
    >
      {children}
    </RightSidebarContext.Provider>
  );
};

export const useRightSidebar = () => {
  const context = useContext(RightSidebarContext);
  if (context === undefined) {
    throw new Error(
      "useRightSidebar must be used within a RightSidebarProvider",
    );
  }
  return context;
};
