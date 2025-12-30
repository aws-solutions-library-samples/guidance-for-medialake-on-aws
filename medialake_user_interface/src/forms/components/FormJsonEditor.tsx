import React from "react";
import { Controller, Control, FieldValues, Path } from "react-hook-form";
import { EventBridgePatternEditor } from "../../components/pipelines/EventBridgePatternEditor";

interface FormJsonEditorProps<T extends FieldValues> {
  name: Path<T>;
  control: Control<T>;
  label?: string;
  required?: boolean;
  tooltip?: string;
  placeholder?: string;
}

export function FormJsonEditor<T extends FieldValues>({ name, control }: FormJsonEditorProps<T>) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => {
        // Parse string value to object for the editor
        const parseValue = (val: any): Record<string, any> => {
          if (!val) return {};
          if (typeof val === "object") return val;
          try {
            return JSON.parse(val);
          } catch {
            return {};
          }
        };

        // Convert object back to string for form storage
        const handleChange = (value: Record<string, any>) => {
          field.onChange(JSON.stringify(value));
        };

        return <EventBridgePatternEditor value={parseValue(field.value)} onChange={handleChange} />;
      }}
    />
  );
}
