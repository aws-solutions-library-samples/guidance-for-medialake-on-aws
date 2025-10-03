import React, {
  useRef,
  useEffect,
  useState,
  useLayoutEffect,
  useCallback,
} from "react";
import { TextField, TextFieldProps } from "@mui/material";

interface InlineTextEditorProps extends Omit<TextFieldProps, "value"> {
  /** Called once when editing finishes (onBlur or Enter) */
  onChangeCommit: (newValue: string) => void;
  onComplete?: (save: boolean, value?: string) => void;
  isEditing: boolean;
  /** New prop: unique cell ID so we know when we're entering a different cell */
  editingCellId: string;
  initialValue: string;
  /** Ref to check if commit should be prevented */
  preventCommitRef?: React.MutableRefObject<boolean>;
  /** Ref to expose commit function to parent */
  commitRef?: React.MutableRefObject<(() => void) | null>;
}

export const InlineTextEditor: React.FC<InlineTextEditorProps> = React.memo(
  ({
    initialValue,
    onChangeCommit,
    onComplete,
    isEditing,
    editingCellId,
    preventCommitRef,
    commitRef,
    ...textFieldProps
  }) => {
    const [value, setValue] = useState(initialValue);
    const lastSel = useRef<{ start: number; end: number }>({
      start: 0,
      end: 0,
    });
    const inputRef = useRef<HTMLInputElement>(null);
    const prevEditId = useRef(editingCellId);

    // ▶️ only reset when *starting* to edit a new cell
    useEffect(() => {
      if (editingCellId !== prevEditId.current) {
        setValue(initialValue);
        prevEditId.current = editingCellId;
      }
    }, [editingCellId, initialValue]);

    // ✏️ keep text locally—do NOT call parent on each keystroke
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const { selectionStart, selectionEnd, value: v } = e.target;
      lastSel.current = { start: selectionStart!, end: selectionEnd! };
      setValue(v);
    };

    // 🔑 commit on blur or Enter
    const commit = useCallback(() => {
      // Check if commit should be prevented (e.g., when Cancel button is clicked)
      if (preventCommitRef?.current) {
        // Reset the flag after a small delay to ensure it doesn't interfere with subsequent operations
        setTimeout(() => {
          if (preventCommitRef) {
            preventCommitRef.current = false;
          }
        }, 100);
        return;
      }

      onChangeCommit(value);
      onComplete?.(true, value); // Pass the value directly to avoid state timing issues
    }, [value, onChangeCommit, onComplete, preventCommitRef]);

    const cancel = useCallback(() => {
      onComplete?.(false, undefined);
    }, [onComplete]);
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        commit();
        e.preventDefault();
      }
      if (e.key === "Escape") {
        cancel();
        e.preventDefault();
      }
    };

    // Handle blur - only cancel, don't commit automatically
    const handleBlur = () => {
      // Check if commit should be prevented (e.g., when Cancel button is clicked)
      if (preventCommitRef?.current) {
        // Reset the flag after a small delay to ensure it doesn't interfere with subsequent operations
        setTimeout(() => {
          if (preventCommitRef) {
            preventCommitRef.current = false;
          }
        }, 100);
        return;
      }

      // On blur, cancel the edit instead of committing
      cancel();
    };

    // 🔄 restore caret position
    useLayoutEffect(() => {
      const input = inputRef.current;
      if (input === document.activeElement) {
        input.setSelectionRange(lastSel.current.start, lastSel.current.end);
      }
    }, [value]);

    // Expose commit function to parent via ref
    useEffect(() => {
      if (commitRef) {
        commitRef.current = commit;
      }
      return () => {
        if (commitRef) {
          commitRef.current = null;
        }
      };
    }, [commit, commitRef]);

    return (
      <TextField
        {...textFieldProps}
        inputRef={inputRef}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        autoFocus
        fullWidth
      />
    );
  },
);

InlineTextEditor.displayName = "InlineTextEditor";
