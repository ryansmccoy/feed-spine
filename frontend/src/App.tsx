import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import TodayView from './pages/TodayView'
import FeedsPage from './pages/FeedsPage'
import StatsPage from './pages/StatsPage'
import RecordsPage from './pages/RecordsPage'
import SettingsPage from './pages/SettingsPage'
import NotFoundPage from './pages/NotFoundPage'
import { NewsfeedPage } from './pages/newsfeed'
import Layout from './components/Layout'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/today" replace />} />
          <Route path="today" element={<TodayView />} />
          <Route path="feeds" element={<FeedsPage />} />
          <Route path="newsfeed" element={<NewsfeedPage />} />
          <Route path="records" element={<RecordsPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
