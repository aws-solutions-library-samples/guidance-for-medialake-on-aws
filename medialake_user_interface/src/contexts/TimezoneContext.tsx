import React, { createContext, useContext, useState, useEffect } from 'react';

interface TimezoneContextType {
    timezone: string;
    setTimezone: (timezone: string) => void;
}

const TimezoneContext = createContext<TimezoneContextType | undefined>(undefined);

export const TimezoneProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Initialize with browser's timezone but allow override
    const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);

    useEffect(() => {
        // Could load saved timezone preference from user settings here
        const savedTimezone = localStorage.getItem('userTimezone');
        if (savedTimezone) {
            setTimezone(savedTimezone);
        }
    }, []);

    const value = {
        timezone,
        setTimezone: (newTimezone: string) => {
            setTimezone(newTimezone);
            localStorage.setItem('userTimezone', newTimezone);
        },
    };

    return (
        <TimezoneContext.Provider value={value}>
            {children}
        </TimezoneContext.Provider>
    );
};

export const useTimezone = () => {
    const context = useContext(TimezoneContext);
    if (context === undefined) {
        throw new Error('useTimezone must be used within a TimezoneProvider');
    }
    return context;
};
