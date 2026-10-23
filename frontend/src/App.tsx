import { createBrowserRouter, NavLink, Outlet, RouterProvider } from 'react-router'
import PersonaSwitcher from './components/PersonaSwitcher'
import Appointments from './pages/Appointments'
import Home from './pages/Home'
import NextSteps from './pages/NextSteps'
import PersonaProvider from './components/PersonaProvider'

/** App shell: header with persona switcher, page content, bottom nav. */
function Layout() {
  return (
    <div className="shell">
      <header className="header">
        <strong>EmCare</strong>
        <PersonaSwitcher />
      </header>
      <main className="content">
        <Outlet />
      </main>
      <nav className="bottom-nav">
        <NavLink to="/" end>Home</NavLink>
        <NavLink to="/appointments">Appointments</NavLink>
        <NavLink to="/next-steps">Next steps</NavLink>
      </nav>
    </div>
  )
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/appointments', element: <Appointments /> },
      { path: '/next-steps', element: <NextSteps /> },
    ],
  },
])

/** Root component. */
export default function App() {
  return (
    <PersonaProvider>
      <RouterProvider router={router} />
    </PersonaProvider>
  )
}
