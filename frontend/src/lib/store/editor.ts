"use client";
import { create } from "zustand";

interface EditorState {
  pageId: string | null;
  pageVersion: number | null;
  isDirty: boolean;
  setBaseline: (pageId: string, version: number) => void;
  markDirty: () => void;
  reset: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  pageId: null,
  pageVersion: null,
  isDirty: false,
  setBaseline: (pageId, pageVersion) => set({ pageId, pageVersion, isDirty: false }),
  markDirty: () => set({ isDirty: true }),
  reset: () => set({ pageId: null, pageVersion: null, isDirty: false }),
}));
