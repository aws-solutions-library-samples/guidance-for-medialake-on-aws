import React, { createContext, useContext, useEffect, useState } from "react";

export interface RecentlyViewedItem {
  id: string;
  title: string;
  type: "video" | "image" | "audio";
  timestamp: Date;
  path: string;
  searchTerm: string;
  metadata: {
    duration?: string;
    fileSize?: string;
    dimensions?: string;
    creator?: string;
  };
}

interface RecentlyViewedContextType {
  items: RecentlyViewedItem[];
  addItem: (item: Omit<RecentlyViewedItem, "timestamp">) => void;
  removeItem: (id: string) => void;
  clearAll: () => void;
}

const STORAGE_KEY = "medialake_recently_viewed";
const STORAGE_VERSION = 3; // Increment when making breaking changes to storage format
const MAX_ITEMS = 10;

const RecentlyViewedContext = createContext<
  RecentlyViewedContextType | undefined
>(undefined);

export const RecentlyViewedProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [items, setItems] = useState<RecentlyViewedItem[]>(() => {
    try {
      const version = localStorage.getItem(`${STORAGE_KEY}_version`);
      // Clear storage if version doesn't match
      if (version !== STORAGE_VERSION.toString()) {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.setItem(
          `${STORAGE_KEY}_version`,
          STORAGE_VERSION.toString(),
        );
        return [];
      }

      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert stored timestamps back to Date objects and validate entries
        // Also migrate old paths to new format
        return parsed
          .map((item: any) => {
            // Convert timestamp
            const newItem = {
              ...item,
              timestamp: new Date(item.timestamp),
            };

            // Migrate old paths that use /assets/ to new type-based paths
            if (newItem.path.startsWith("/assets/")) {
              newItem.path = `/${newItem.type}s/${newItem.path.split("/").pop()}`;
            }

            return newItem;
          })
          .filter(
            (item: any) =>
              item.id &&
              item.title &&
              (item.type === "video" ||
                item.type === "image" ||
                item.type === "audio") &&
              item.path,
          )
          .slice(0, MAX_ITEMS);
      }
    } catch (error) {
      console.error("Error loading recently viewed items:", error);
    }
    return [];
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
      localStorage.setItem(
        `${STORAGE_KEY}_version`,
        STORAGE_VERSION.toString(),
      );
    } catch (error) {
      console.error("Error saving recently viewed items:", error);
    }
  }, [items]);

  const addItem = (newItem: Omit<RecentlyViewedItem, "timestamp">) => {
    setItems((currentItems) => {
      // Remove existing item if present
      const filteredItems = currentItems.filter(
        (item) => item.id !== newItem.id,
      );

      // Ensure path uses the correct format
      const path = newItem.path.startsWith("/")
        ? newItem.path
        : `/${newItem.type}s/${newItem.id}`;

      // Add new item at the beginning with current timestamp
      const updatedItems = [
        {
          ...newItem,
          path,
          timestamp: new Date(),
        },
        ...filteredItems,
      ];

      // Limit to MAX_ITEMS
      return updatedItems.slice(0, MAX_ITEMS);
    });
  };

  const removeItem = (id: string) => {
    setItems((currentItems) => currentItems.filter((item) => item.id !== id));
  };

  const clearAll = () => {
    setItems([]);
  };

  return (
    <RecentlyViewedContext.Provider
      value={{ items, addItem, removeItem, clearAll }}
    >
      {children}
    </RecentlyViewedContext.Provider>
  );
};

export const useRecentlyViewed = () => {
  const context = useContext(RecentlyViewedContext);
  if (context === undefined) {
    throw new Error(
      "useRecentlyViewed must be used within a RecentlyViewedProvider",
    );
  }
  return context;
};

// Helper hook for automatically tracking viewed items
export const useTrackRecentlyViewed = (
  item: Omit<RecentlyViewedItem, "timestamp"> | null,
) => {
  const { addItem } = useRecentlyViewed();

  useEffect(() => {
    if (item) {
      addItem(item);
    }
  }, [item?.id]); // Only re-run the effect if the item's id changes
};
