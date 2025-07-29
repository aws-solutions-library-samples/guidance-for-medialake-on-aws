export type ValidationRule = {
  type: "min" | "max" | "email" | "url" | "regex";
  value?: number | string;
  message: string;
};

export type FormFieldValidation = {
  type: "string" | "number" | "boolean" | "array";
  rules: ValidationRule[];
};

export type FormFieldOption = {
  label: string;
  value: string;
};

export type FormFieldShowWhen = {
  field: string;
  value: any;
};

export interface FormFieldDefinition {
  name: string;
  type:
    | "text"
    | "email"
    | "select"
    | "multiselect"
    | "switch"
    | "number"
    | "password";
  label: string;
  tooltip?: string;
  required?: boolean;
  multiline?: boolean;
  rows?: number;
  validation?: FormFieldValidation;
  options?: FormFieldOption[];
  defaultValue?: any;
  showWhen?: FormFieldShowWhen;
}

export interface FormDefinition {
  id: string;
  name: string;
  description?: string;
  translationPrefix?: string;
  fields: FormFieldDefinition[];
}
