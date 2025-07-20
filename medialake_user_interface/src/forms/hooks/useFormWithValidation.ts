import {
  useForm,
  UseFormProps,
  FieldValues,
  DefaultValues,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

export type FormConfig<T extends FieldValues> = {
  defaultValues?: DefaultValues<T>;
  validationSchema?: z.Schema<T>;
  mode?: UseFormProps["mode"];
  reValidateMode?: UseFormProps["reValidateMode"];
  translationPrefix?: string;
};

export const useFormWithValidation = <T extends FieldValues>(
  config: FormConfig<T>,
) => {
  const {
    defaultValues,
    validationSchema,
    mode = "onBlur",
    reValidateMode = "onChange",
    translationPrefix,
  } = config;
  const { t } = useTranslation();

  // Create a custom resolver that translates error messages
  const resolver = validationSchema
    ? zodResolver(validationSchema, {
        errorMap: (error, ctx) => {
          const message = error.message;
          // If we have a translation prefix, try to find a translated message
          if (translationPrefix) {
            const fieldPath = (ctx as any).data ? Object.keys(ctx.data)[0] : "";
            const errorType = error.code.toLowerCase();
            const translationKey = `${translationPrefix}.errors.${fieldPath}.${errorType}`;
            const translatedMessage = t(translationKey, {
              defaultValue: message,
            });

            return { message: translatedMessage };
          }
          return { message };
        },
      })
    : undefined;

  const methods = useForm<T>({
    defaultValues,
    resolver,
    mode,
    reValidateMode,
  });

  return {
    ...methods,
    isValid: methods.formState.isValid,
    isDirty: methods.formState.isDirty,
    errors: methods.formState.errors,
  };
};

// Common Zod validators with i18n support
export const createCommonValidators = (t: (key: string) => string) => ({
  email: () => z.string().email(t("validation.invalid_email")),
  required: (message: string) => z.string().min(1, message),
  min: (n: number, message: string) => z.string().min(n, message),
  max: (n: number, message: string) => z.string().max(n, message),
  numeric: (message: string) => z.string().regex(/^\d+$/, message),
  phone: (message: string) => z.string().regex(/^\+?[\d\s-]+$/, message),
  url: (message: string) => z.string().url(message),
  password: (messages: {
    min?: string;
    uppercase?: string;
    lowercase?: string;
    number?: string;
    special?: string;
  }) =>
    z
      .string()
      .min(8, messages.min || "Password must be at least 8 characters")
      .regex(/[A-Z]/, messages.uppercase || "Must contain uppercase letter")
      .regex(/[a-z]/, messages.lowercase || "Must contain lowercase letter")
      .regex(/[0-9]/, messages.number || "Must contain number")
      .regex(
        /[^A-Za-z0-9]/,
        messages.special || "Must contain special character",
      ),
});
