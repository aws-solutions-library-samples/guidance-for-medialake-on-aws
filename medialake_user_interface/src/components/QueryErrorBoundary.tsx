import React from "react";
import { useQueryErrorResetBoundary } from "@tanstack/react-query";
import { ErrorBoundary } from "react-error-boundary";
import { useTranslation } from "react-i18next";

export const QueryErrorBoundary: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { reset } = useQueryErrorResetBoundary();
  const { t } = useTranslation();

  return (
    <ErrorBoundary
      onReset={reset}
      fallbackRender={({ error, resetErrorBoundary }) => (
        <div>
          <h2>{t("errors.somethingWentWrong", "Something went wrong!")}</h2>
          <pre>{error.message}</pre>
          <button onClick={resetErrorBoundary}>{t("errors.tryAgain", "Try Again")}</button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
};
