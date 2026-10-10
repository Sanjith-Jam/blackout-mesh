import { create } from 'zustand'

interface AppState {
  isConnected: boolean
  isStale: boolean
  activeTab: string
  setConnected: (val: boolean) => void
  setStale: (val: boolean) => void
  setActiveTab: (val: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  isConnected: false,
  isStale: true,
  activeTab: "overview",
  setConnected: (val) => set({ isConnected: val }),
  setStale: (val) => set({ isStale: val }),
  setActiveTab: (val) => set({ activeTab: val })
}))
