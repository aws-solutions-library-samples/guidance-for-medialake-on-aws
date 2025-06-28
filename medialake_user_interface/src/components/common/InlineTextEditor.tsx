import React, {
  useRef,
  useEffect,
  useState,
  useLayoutEffect,
} from 'react';

import { TextField, TextFieldProps } from '@mui/material';

interface InlineTextEditorProps extends Omit<TextFieldProps, 'value' | 'onChange'> {
    initialValue: string;
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onComplete?: (save: boolean) => void;
    isEditing: boolean;
}

export const InlineTextEditor: React.FC<InlineTextEditorProps> = React.memo(({
    initialValue,
    onChange,
    onComplete,
    isEditing,
    ...textFieldProps
}) => {
  const [value, setValue] = useState(initialValue);
  const lastSel = useRef<{ start: number; end: number }>({ start: 0, end: 0 });
  const inputRef = useRef<HTMLInputElement>(null);

  // reset local state when a new cell is edited
  useEffect(() => setValue(initialValue), [initialValue]);

  // track caret on every change
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { selectionStart, selectionEnd, value } = e.target;
    if (selectionStart != null && selectionEnd != null) {
      lastSel.current = { start: selectionStart, end: selectionEnd };
    }
    setValue(value);
    onChange(e);
  };

  // restore caret before paint
  useLayoutEffect(() => {
    const input = inputRef.current;
    const { start, end } = lastSel.current;
    if (input && document.activeElement === input) {
      input.setSelectionRange(start, end);
    }
  }, [value]);

  // handle Enter/Esc
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { onComplete?.(true); e.preventDefault(); }
    if (e.key === 'Escape') { onComplete?.(false); e.preventDefault(); }
  };

  return (
    <TextField
      {...textFieldProps}
      inputRef={inputRef}
      value={value}
      onChange={handleChange}
      onKeyDown={handleKey}
      onClick={(e) => {
        e.stopPropagation();
        textFieldProps.onClick?.(e);
      }}
      autoFocus
      fullWidth
    />
  );
});


InlineTextEditor.displayName = 'InlineTextEditor';