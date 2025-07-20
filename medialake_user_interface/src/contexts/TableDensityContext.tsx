import React, { createContext, useContext, useState } from "react";

type TableDensityMode = "compact" | "normal";

interface TableDensityContextType {
  mode: TableDensityMode;
  toggleMode: () => void;
}

const TableDensityContext = createContext<TableDensityContextType | undefined>(
  undefined,
);

export const TableDensityProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [mode, setMode] = useState<TableDensityMode>("compact");

  const toggleMode = () => {
    setMode((prevMode) => (prevMode === "compact" ? "normal" : "compact"));
  };

  return (
    <TableDensityContext.Provider value={{ mode, toggleMode }}>
      {children}
    </TableDensityContext.Provider>
  );
};

export const useTableDensity = () => {
  const context = useContext(TableDensityContext);
  if (context === undefined) {
    throw new Error(
      "useTableDensity must be used within a TableDensityProvider",
    );
  }
  return context;
};
