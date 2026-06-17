import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useSearchFields } from "@/api/hooks/useSearchFields";

const STORAGE_KEY = "medialake-field-preferences-v2";

interface StoredPrefs {
  selectedFields: string[];
  deselectedFields: string[];
}

const EMPTY_PREFS: StoredPrefs = { selectedFields: [], deselectedFields: [] };

function readFromStorage(): StoredPrefs | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      // Migrate from v1 if present
      const v1 = localStorage.getItem("medialake-field-preferences-v1");
      if (v1) {
        const parsed = JSON.parse(v1);
        if (Array.isArray(parsed?.selectedFields)) {
          const migrated: StoredPrefs = {
            selectedFields: parsed.selectedFields,
            deselectedFields: [],
          };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
          return migrated;
        }
      }
      return null;
    }
    const parsed = JSON.parse(raw);
    return {
      selectedFields: Array.isArray(parsed?.selectedFields) ? parsed.selectedFields : [],
      deselectedFields: Array.isArray(parsed?.deselectedFields) ? parsed.deselectedFields : [],
    };
  } catch {
    return null;
  }
}

function writeToStorage(prefs: StoredPrefs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

export function useMetadataFieldPreferences() {
  const { data: fieldsData } = useSearchFields();

  // Stable reference — only changes when the actual data changes
  const availableFields = fieldsData?.data?.availableFields;

  const [prefs, setPrefs] = useState<StoredPrefs | null>(() => readFromStorage());

  // Use ref to read current prefs inside the effect without it being a dependency
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;

  const lastAvailableRef = useRef<string | null>(null);

  // Sync with available fields — only runs when availableFields actually changes
  useEffect(() => {
    if (!availableFields || availableFields.length === 0) return;

    const availableKey = availableFields
      .map((f) => f.name)
      .sort()
      .join("\0");
    if (availableKey === lastAvailableRef.current) return;
    lastAvailableRef.current = availableKey;

    const currentPrefs = prefsRef.current;
    const availableNames = availableFields.map((f) => f.name);
    const availableSet = new Set(availableNames);

    if (currentPrefs === null) {
      const newPrefs: StoredPrefs = { selectedFields: availableNames, deselectedFields: [] };
      setPrefs(newPrefs);
      writeToStorage(newPrefs);
    } else {
      const deselectedSet = new Set(currentPrefs.deselectedFields);
      const currentSet = new Set(currentPrefs.selectedFields);

      const kept = currentPrefs.selectedFields.filter((f) => availableSet.has(f));
      const newFields = availableNames.filter(
        (name) => !currentSet.has(name) && !deselectedSet.has(name)
      );
      const cleanedDeselected = currentPrefs.deselectedFields.filter((f) => availableSet.has(f));
      const updatedSelected = [...kept, ...newFields];

      // Only update if something actually changed
      const selectedChanged =
        updatedSelected.length !== currentPrefs.selectedFields.length ||
        updatedSelected.some((f, i) => f !== currentPrefs.selectedFields[i]);
      const deselectedChanged = cleanedDeselected.length !== currentPrefs.deselectedFields.length;

      if (selectedChanged || deselectedChanged) {
        const newPrefs: StoredPrefs = {
          selectedFields: updatedSelected,
          deselectedFields: cleanedDeselected,
        };
        setPrefs(newPrefs);
        writeToStorage(newPrefs);
      }
    }
  }, [availableFields]); // Only depends on availableFields, NOT prefs

  const setSelectedFields = useCallback((fields: string[]) => {
    setPrefs((prev) => {
      const currentSelected = prev?.selectedFields ?? [];
      const newlyDeselected = currentSelected.filter((f) => !fields.includes(f));
      const newlySelected = fields.filter((f) => !currentSelected.includes(f));

      const prevDeselected = new Set(prev?.deselectedFields ?? []);
      for (const f of newlyDeselected) prevDeselected.add(f);
      for (const f of newlySelected) prevDeselected.delete(f);

      const newPrefs: StoredPrefs = {
        selectedFields: fields,
        deselectedFields: [...prevDeselected],
      };
      writeToStorage(newPrefs);
      return newPrefs;
    });
  }, []); // Stable — no dependencies, uses functional setState

  const isReady = prefs !== null;

  // Stable array reference — only changes when the actual field list changes
  const selectedFields = useMemo(
    () => prefs?.selectedFields ?? [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [prefs?.selectedFields?.join("\0")]
  );

  return { selectedFields, setSelectedFields, isReady };
}
