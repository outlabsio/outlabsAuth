import { useState } from "react";

interface UseDrawerStateReturn<T> {
  isOpen: boolean;
  mode: "create" | "edit";
  selectedItem: T | null;
  open: () => void;
  close: () => void;
  openCreate: () => void;
  openEdit: (item: T) => void;
}

export function useDrawerState<T = unknown>(): UseDrawerStateReturn<T> {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [selectedItem, setSelectedItem] = useState<T | null>(null);

  const open = () => setIsOpen(true);
  const close = () => setIsOpen(false);

  const openCreate = () => {
    setMode("create");
    setSelectedItem(null);
    setIsOpen(true);
  };

  const openEdit = (item: T) => {
    setMode("edit");
    setSelectedItem(item);
    setIsOpen(true);
  };

  return {
    isOpen,
    mode,
    selectedItem,
    open,
    close,
    openCreate,
    openEdit,
  };
}