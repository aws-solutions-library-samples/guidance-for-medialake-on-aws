import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

// Helper function to check if a language is RTL
export const isRTL = (language: string): boolean => {
  return ["ar", "he"].includes(language);
};

type Direction = "ltr" | "rtl";

interface DirectionContextType {
  direction: Direction;
  setDirection: (direction: Direction) => void;
  toggleDirection: () => void;
}

const DirectionContext = createContext<DirectionContextType | undefined>(
  undefined,
);

interface DirectionProviderProps {
  children: ReactNode;
}

export const DirectionProvider: React.FC<DirectionProviderProps> = ({
  children,
}) => {
  const { i18n } = useTranslation();
  const [direction, setDirection] = useState<Direction>(
    isRTL(i18n.language) ? "rtl" : "ltr",
  );

  // Update direction when language changes
  useEffect(() => {
    const handleLanguageChange = () => {
      const newDirection = isRTL(i18n.language) ? "rtl" : "ltr";
      console.log(
        "DirectionContext: Language changed to",
        i18n.language,
        "Setting direction to",
        newDirection,
      );
      setDirection(newDirection);

      // Update HTML dir attribute
      document.documentElement.setAttribute("dir", newDirection);
      document.documentElement.setAttribute("lang", i18n.language);
      console.log(
        "DirectionContext: Updated HTML dir attribute to",
        newDirection,
      );
    };

    // Set initial direction
    handleLanguageChange();

    // Listen for language changes
    i18n.on("languageChanged", handleLanguageChange);

    return () => {
      i18n.off("languageChanged", handleLanguageChange);
    };
  }, [i18n]);

  const toggleDirection = () => {
    const newDirection = direction === "ltr" ? "rtl" : "ltr";
    setDirection(newDirection);
    document.documentElement.setAttribute("dir", newDirection);
  };

  return (
    <DirectionContext.Provider
      value={{ direction, setDirection, toggleDirection }}
    >
      {children}
    </DirectionContext.Provider>
  );
};

export const useDirection = (): DirectionContextType => {
  const context = useContext(DirectionContext);
  if (context === undefined) {
    throw new Error("useDirection must be used within a DirectionProvider");
  }
  return context;
};
