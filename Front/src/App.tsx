import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
import HomePage from '@/pages/HomePage'
import FieldCopilotPage from '@/pages/FieldCopilotPage'
import LinesPage from '@/pages/LinesPage'
import BreedingPassportPage from '@/pages/BreedingPassportPage'
import HiddenGemsPage from '@/pages/HiddenGemsPage'
import BuildCohortPage from '@/pages/BuildCohortPage'
import ModelIntelligencePage from '@/pages/ModelIntelligencePage'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/copilot" element={<FieldCopilotPage />} />
          <Route path="/lines" element={<LinesPage />} />
          <Route path="/lines/:id" element={<BreedingPassportPage />} />
          <Route path="/gems" element={<HiddenGemsPage />} />
          <Route path="/cohort" element={<BuildCohortPage />} />
          <Route path="/intelligence" element={<ModelIntelligencePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
