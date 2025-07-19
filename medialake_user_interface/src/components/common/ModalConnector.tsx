import React, { createContext, useContext, useState, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
} from "@mui/material";

interface ModalContextType {
  showModal: (content: ReactNode, options?: ModalOptions) => void;
  hideModal: () => void;
}

interface ModalOptions {
  title?: string;
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
}

interface ModalProviderProps {
  children: ReactNode;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export const ModalProvider: React.FC<ModalProviderProps> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [modalContent, setModalContent] = useState<ReactNode | null>(null);
  const [modalOptions, setModalOptions] = useState<ModalOptions>({});
  const { t } = useTranslation();

  const showModal = (content: ReactNode, options: ModalOptions = {}) => {
    setModalContent(content);
    setModalOptions(options);
    setIsOpen(true);
  };

  const hideModal = () => {
    setIsOpen(false);
    setModalContent(null);
    setModalOptions({});
  };

  return (
    <ModalContext.Provider value={{ showModal, hideModal }}>
      {children}
      <Dialog
        open={isOpen}
        onClose={hideModal}
        maxWidth="sm"
        PaperProps={{
          sx: {
            width: "400px", // Set fixed width for configuration modal
            margin: 2,
          },
        }}
      >
        {modalOptions.title && <DialogTitle>{modalOptions.title}</DialogTitle>}
        <DialogContent>
          <Box sx={{ py: 1 }}>{modalContent}</Box>
        </DialogContent>
        <DialogActions>
          {modalOptions.onCancel && (
            <Button
              onClick={() => {
                modalOptions.onCancel?.();
                hideModal();
              }}
              variant="outlined"
            >
              {modalOptions.cancelText || t("common.cancel")}
            </Button>
          )}
          {modalOptions.onConfirm && (
            <Button
              onClick={() => {
                modalOptions.onConfirm?.();
                hideModal();
              }}
              variant="contained"
              color="primary"
            >
              {modalOptions.confirmText || t("common.save")}
            </Button>
          )}
          {!modalOptions.onConfirm && !modalOptions.onCancel && (
            <Button onClick={hideModal} variant="contained" color="primary">
              {t("common.close")}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </ModalContext.Provider>
  );
};

export const useModal = () => {
  const context = useContext(ModalContext);
  if (context === undefined) {
    throw new Error("useModal must be used within a ModalProvider");
  }
  return context;
};

export default ModalProvider;
