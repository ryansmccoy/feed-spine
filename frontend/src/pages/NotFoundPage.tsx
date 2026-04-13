import { Link } from 'react-router-dom'
import { Home, AlertCircle } from 'lucide-react'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <AlertCircle className="h-16 w-16 text-gray-400 mb-4" />
      <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
        404
      </h1>
      <p className="text-lg text-gray-600 dark:text-gray-400 mb-6">
        Page not found
      </p>
      <Link
        to="/"
        className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        <Home className="h-4 w-4" />
        Go Home
      </Link>
    </div>
  )
}
