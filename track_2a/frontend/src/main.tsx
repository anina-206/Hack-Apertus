import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Roboto comes with the app (no request to Google): one variable font file per script, only Latin is loaded
import '@fontsource-variable/roboto/wght.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
