import { create } from 'zustand'

type Store = {
  theme: 'dark' | 'light'
  scenario: string
  unitId?: string
  commandOpen: boolean
  presenter: boolean
  controlsHidden: boolean
  tourActive: boolean
  tourElapsed: number
  tourExtended: boolean
  setTheme: (theme: 'dark' | 'light') => void
  setScenario: (scenario: string) => void
  setUnitId: (unitId?: string) => void
  setCommandOpen: (value: boolean) => void
  setPresenter: (value: boolean) => void
  setControlsHidden: (value: boolean) => void
  setTourActive: (value: boolean) => void
  setTourElapsed: (value: number | ((previous: number) => number)) => void
  setTourExtended: (value: boolean) => void
}

export const useStore = create<Store>((set) => ({
  theme: 'dark', scenario: 'chennai_municipal', commandOpen: false, presenter: false, controlsHidden: false,
  tourActive: false, tourElapsed: 0, tourExtended: false,
  setTheme: (theme) => set({ theme }), setScenario: (scenario) => set({ scenario }),
  setUnitId: (unitId) => set({ unitId }), setCommandOpen: (commandOpen) => set({ commandOpen }),
  setPresenter: (presenter) => set({ presenter }),
  setControlsHidden: (controlsHidden) => set({ controlsHidden }),
  setTourActive: (tourActive) => set({ tourActive }),
  setTourElapsed: (value) => set((state) => ({ tourElapsed: typeof value === 'function' ? value(state.tourElapsed) : value })),
  setTourExtended: (tourExtended) => set({ tourExtended }),
}))
