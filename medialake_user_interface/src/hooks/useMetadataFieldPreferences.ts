import { useState, useEffect, useRef } from "react";
import { useSearchFields } from "@/api/hooks/useSearchFields";

const STORAGE_KEY = "medialake-field-preferences-v1";

function readFromStorage(): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.selectedFields) ? parsed.selectedFields : null;
  } catch {
    return null;
  }
}

function writeToStorage(fields: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ selectedFields: fields }));
}

export function useMetadataFieldPreferences() {
  const { data: fieldsData } = useSearchFields();
  const availableFields = fieldsData?.data?.availableFields || [];

  const [selectedFields, setSelectedFieldsState] = useState<string[] | null>(() =>
    readFromStorage()
  );

  // Sync selected fields with available fields from the API.
  // - First load with empty localStorage: select all available fields
  // - First load with existing localStorage: add any available fields not already present
  //   (handles newly enabled fields in settings)
  const hasSyncedRef = useRef(false);

  useEffect(() => {
    if (availableFields.length === 0 || hasSyncedRef.current) return;
    hasSyncedRef.current = true;

    const availableNames = availableFields.map((f) => f.name);

    if (selectedFields === null) {
      // No localStorage — select all available fields
      setSelectedFieldsState(availableNames);
      writeToStorage(availableNames);
    } else {
      // Has localStorage — add any newly available fields not already in the list
      const currentSet = new Set(selectedFields);
      const newFields = availableNames.filter((name) => !currentSet.has(name));
      if (newFields.length > 0) {
        const updated = [...selectedFields, ...newFields];
        setSelectedFieldsState(updated);
        writeToStorage(updated);
      }
    }
  }, [availableFields, selectedFields]);

  const setSelectedFields = (fields: string[]) => {
    setSelectedFieldsState(fields);
    writeToStorage(fields);
  };

  // Not ready until we have resolved fields (from storage or defaults)
  const isReady = selectedFields !== null;

  return { selectedFields: selectedFields ?? [], setSelectedFields, isReady };
}
