import React, { createContext, useContext, useState, ReactNode } from 'react';

interface RightSidebarContextType {
    isExpanded: boolean;
    setIsExpanded: (expanded: boolean) => void;
}

const RightSidebarContext = createContext<RightSidebarContextType | undefined>(undefined);

interface RightSidebarProviderProps {
    children: ReactNode;
}

export const RightSidebarProvider: React.FC<RightSidebarProviderProps> = ({ children }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <RightSidebarContext.Provider value={{ isExpanded, setIsExpanded }}>
            {children}
        </RightSidebarContext.Provider>
    );
};

export const useRightSidebar = () => {
    const context = useContext(RightSidebarContext);
    if (context === undefined) {
        throw new Error('useRightSidebar must be used within a RightSidebarProvider');
    }
    return context;
};
