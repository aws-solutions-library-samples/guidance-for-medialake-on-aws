import { useState } from "react";

export const useErrorModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const showError = (message: string) => {
    setErrorMessage(message);
    setIsOpen(true);
  };

  const hideError = () => {
    setIsOpen(false);
    setErrorMessage("");
  };

  return {
    isOpen,
    errorMessage,
    showError,
    hideError,
  };
};
