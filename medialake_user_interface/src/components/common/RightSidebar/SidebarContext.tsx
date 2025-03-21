import React, { createContext, useContext, useState, ReactNode } from 'react';

interface RightSidebarContextType {
    isExpanded: boolean;
    setIsExpanded: (expanded: boolean) => void;
    currentWidth: number;
    setCurrentWidth: (width: number) => void;
}

const RightSidebarContext = createContext<RightSidebarContextType>({
    isExpanded: true,
    setIsExpanded: () => {},
    currentWidth: 375,
    setCurrentWidth: () => {},
});

interface RightSidebarProviderProps {
    children: ReactNode;
}

export const RightSidebarProvider: React.FC<RightSidebarProviderProps> = ({ children }) => {
    const [isExpanded, setIsExpanded] = useState(true);
    const [currentWidth, setCurrentWidth] = useState(375);

    return (
        <RightSidebarContext.Provider value={{ isExpanded, setIsExpanded, currentWidth, setCurrentWidth }}>
            {children}
        </RightSidebarContext.Provider>
    );
};

export const useRightSidebar = () => useContext(RightSidebarContext);
