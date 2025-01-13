import React, { createContext, useContext, useEffect, useState } from 'react';

export interface RecentlyViewedItem {
    id: string;
    title: string;
    type: 'video' | 'image';
    timestamp: Date;
    path: string;
    metadata: {
        duration?: string;
        fileSize?: string;
        dimensions?: string;
        creator?: string;
    };
}

interface RecentlyViewedContextType {
    items: RecentlyViewedItem[];
    addItem: (item: Omit<RecentlyViewedItem, 'timestamp'>) => void;
    removeItem: (id: string) => void;
    clearAll: () => void;
}

const STORAGE_KEY = 'medialake_recently_viewed';
const MAX_ITEMS = 10;

const RecentlyViewedContext = createContext<RecentlyViewedContextType | undefined>(undefined);

export const RecentlyViewedProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [items, setItems] = useState<RecentlyViewedItem[]>(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                // Convert stored timestamps back to Date objects and validate entries
                return parsed
                    .map((item: any) => ({
                        ...item,
                        timestamp: new Date(item.timestamp)
                    }))
                    .filter((item: any) =>
                        item.id &&
                        item.title &&
                        (item.type === 'video' || item.type === 'image') &&
                        item.path
                    )
                    .slice(0, MAX_ITEMS);
            }
        } catch (error) {
            console.error('Error loading recently viewed items:', error);
        }
        return [];
    });

    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
        } catch (error) {
            console.error('Error saving recently viewed items:', error);
        }
    }, [items]);

    const addItem = (newItem: Omit<RecentlyViewedItem, 'timestamp'>) => {
        setItems(currentItems => {
            // Remove existing item if present
            const filteredItems = currentItems.filter(item => item.id !== newItem.id);

            // Add new item at the beginning with current timestamp
            const updatedItems = [
                {
                    ...newItem,
                    timestamp: new Date()
                },
                ...filteredItems
            ];

            // Limit to MAX_ITEMS
            return updatedItems.slice(0, MAX_ITEMS);
        });
    };

    const removeItem = (id: string) => {
        setItems(currentItems => currentItems.filter(item => item.id !== id));
    };

    const clearAll = () => {
        setItems([]);
    };

    return (
        <RecentlyViewedContext.Provider value={{ items, addItem, removeItem, clearAll }}>
            {children}
        </RecentlyViewedContext.Provider>
    );
};

export const useRecentlyViewed = () => {
    const context = useContext(RecentlyViewedContext);
    if (context === undefined) {
        throw new Error('useRecentlyViewed must be used within a RecentlyViewedProvider');
    }
    return context;
};

// Helper hook for automatically tracking viewed items
export const useTrackRecentlyViewed = (item: Omit<RecentlyViewedItem, 'timestamp'> | null) => {
    const { addItem } = useRecentlyViewed();

    useEffect(() => {
        if (item) {
            addItem(item);
        }
    }, [item, addItem]);
};
