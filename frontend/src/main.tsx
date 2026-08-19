import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { Announcer } from './components/Announcer'
import './theme.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* One polite live region wraps everything: work that finishes on its own
        schedule has to say so out loud, not only redraw. */}
    <Announcer>
      <App />
    </Announcer>
  </StrictMode>,
)
