import { Outlet, Link, useLocation } from 'react-router-dom'
import { Home, Rss, BarChart2, RefreshCw, FileText, Settings, Newspaper } from 'lucide-react'
import { clsx } from 'clsx'
import { useHealth } from '@/api/hooks'

export default function Layout() {
  const location = useLocation()
  const { data: health, refetch } = useHealth()

  const navigation = [
    { name: 'Today', href: '/today', icon: Home },
    { name: 'Feeds', href: '/feeds', icon: Rss },
    { name: 'Newsfeed', href: '/newsfeed', icon: Newspaper },
    { name: 'Records', href: '/records', icon: FileText },
    { name: 'Stats', href: '/stats', icon: BarChart2 },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <Rss className="h-8 w-8 text-primary-600" />
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                FeedSpine
              </h1>
            </div>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={clsx(
                      'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>

            {/* Status */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => refetch()}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Refresh"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
              {health?.status === 'healthy' && (
                <div className="flex items-center gap-2 text-sm">
                  <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-gray-600 dark:text-gray-300">Online</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
