import { useState } from 'react'
import { 
  Database, 
  Server, 
  HardDrive, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  Settings2,
  Info,
  BookOpen,
  Code,
  Folder,
  ChevronRight,
  ExternalLink
} from 'lucide-react'
import { clsx } from 'clsx'
import { useHealth, useStorageStatus, useGlobalStats } from '@/api/hooks'

interface ExampleCategory {
  id: string
  name: string
  description: string
  count: number
  examples: Example[]
}

interface Example {
  name: string
  description: string
  path: string
}

// Example data - this could be fetched from an API endpoint
const exampleCategories: ExampleCategory[] = [
  {
    id: '01_getting_started',
    name: 'Getting Started',
    description: 'FeedSpine basics, multi-feed collection, dedup concepts',
    count: 2,
    examples: [
      { name: '01_quickstart.py', description: 'FeedSpine Quickstart Example', path: 'examples/01_getting_started/01_quickstart.py' },
      { name: '02_multi_feed.py', description: 'FeedSpine Multi-Feed Collection Example', path: 'examples/01_getting_started/02_multi_feed.py' },
    ]
  },
  {
    id: '02_storage',
    name: 'Storage',
    description: 'DuckDB persistence, data type handling, checkpoints',
    count: 2,
    examples: [
      { name: '01_duckdb_storage.py', description: 'FeedSpine with DuckDB Persistent Storage', path: 'examples/02_storage/01_duckdb_storage.py' },
      { name: '02_data_type_storage.py', description: 'FeedSpine Data Type Aware Storage', path: 'examples/02_storage/02_data_type_storage.py' },
    ]
  },
  {
    id: '03_domain_feeds',
    name: 'Domain Feeds',
    description: 'SEC EDGAR daily filings, custom adapters',
    count: 1,
    examples: [
      { name: '01_sec_edgar.py', description: 'FeedSpine SEC EDGAR Filing Monitor', path: 'examples/03_domain_feeds/01_sec_edgar.py' },
    ]
  },
  {
    id: '04_operations',
    name: 'Operations',
    description: 'FeedRun tracking, auto-key generation, smart sync strategies',
    count: 11,
    examples: [
      { name: '01_operational_tracking.py', description: 'FeedSpine Operational Tracking Example', path: 'examples/04_operations/01_operational_tracking.py' },
      { name: '02_auto_key_generation.py', description: 'Auto Key Generation for FeedSpine', path: 'examples/04_operations/02_auto_key_generation.py' },
      { name: '03_smart_sync_strategy.py', description: 'Smart Sync Strategy Pattern', path: 'examples/04_operations/03_smart_sync_strategy.py' },
    ]
  },
  {
    id: '05_earnings',
    name: 'Earnings',
    description: 'Calendar API, CLI, REST, WebSocket, full workflows',
    count: 7,
    examples: []
  },
  {
    id: '06_api',
    name: 'API',
    description: 'REST API interaction examples',
    count: 3,
    examples: []
  },
  {
    id: '07_cli',
    name: 'CLI',
    description: 'Command-line interface examples',
    count: 1,
    examples: []
  },
]

export default function SettingsPage() {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  
  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useHealth()
  const { data: storage, isLoading: storageLoading, refetch: refetchStorage } = useStorageStatus()
  const { data: stats, isLoading: statsLoading } = useGlobalStats()

  const isLoading = healthLoading || storageLoading || statsLoading

  const handleRefresh = () => {
    refetchHealth()
    refetchStorage()
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Settings2 className="h-6 w-6" />
            Settings & Info
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            System status, database info, and examples
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-50"
        >
          <RefreshCw className={clsx("h-4 w-4", isLoading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* System Status */}
      <section>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Server className="h-5 w-5" />
          System Status
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Health Card */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">API Status</span>
              {health?.status === 'healthy' ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-500" />
              )}
            </div>
            <p className={clsx(
              "text-xl font-bold",
              health?.status === 'healthy' ? 'text-green-600' : 'text-red-600'
            )}>
              {health?.status || 'Unknown'}
            </p>
          </div>

          {/* Stats Card */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Records</span>
              <HardDrive className="h-5 w-5 text-gray-400" />
            </div>
            <p className="text-xl font-bold text-gray-900 dark:text-white">
              {stats?.total_records?.toLocaleString() ?? '—'}
            </p>
          </div>

          {/* Feeds Card */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Feeds</span>
              <Info className="h-5 w-5 text-gray-400" />
            </div>
            <p className="text-xl font-bold text-gray-900 dark:text-white">
              {stats?.total_feeds?.toLocaleString() ?? '—'}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {stats?.feeds_enabled ?? 0} enabled / {stats?.feeds_disabled ?? 0} disabled
            </p>
          </div>
        </div>
      </section>

      {/* Database Info */}
      <section>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Database className="h-5 w-5" />
          Database Configuration
        </h3>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          {storageLoading ? (
            <div className="p-8 flex items-center justify-center">
              <RefreshCw className="h-6 w-6 text-gray-400 animate-spin" />
            </div>
          ) : storage ? (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Backend Type</span>
                  <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">
                    {storage.backend_type}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Connection Status</span>
                  <p className={clsx(
                    "mt-1 text-sm font-medium",
                    storage.connection_status === 'connected' ? "text-green-600" : "text-red-600"
                  )}>
                    {storage.connection_status}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Records</span>
                  <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">
                    {storage.total_records?.toLocaleString()}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Database File</span>
                  <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white truncate" title={storage.database_file}>
                    {storage.database_file || 'In-Memory'}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              Unable to load storage info
            </div>
          )}
        </div>
      </section>

      {/* Examples */}
      <section>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <BookOpen className="h-5 w-5" />
          Code Examples
          <span className="text-sm font-normal text-gray-500 ml-2">(27 examples across 7 categories)</span>
        </h3>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden divide-y divide-gray-200 dark:divide-gray-700">
          {exampleCategories.map((category) => (
            <div key={category.id}>
              <button
                onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <Folder className="h-5 w-5 text-yellow-500" />
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white">{category.name}</span>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{category.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500 px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                    {category.count} examples
                  </span>
                  <ChevronRight className={clsx(
                    "h-5 w-5 text-gray-400 transition-transform",
                    expandedCategory === category.id && "rotate-90"
                  )} />
                </div>
              </button>
              
              {expandedCategory === category.id && category.examples.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-700/30 border-t border-gray-200 dark:border-gray-700">
                  {category.examples.map((example) => (
                    <div key={example.name} className="flex items-center gap-3 px-4 py-3 pl-12 border-b border-gray-100 dark:border-gray-600 last:border-0">
                      <Code className="h-4 w-4 text-gray-400" />
                      <div className="flex-1 min-w-0">
                        <span className="font-mono text-sm text-primary-600 dark:text-primary-400">{example.name}</span>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{example.description}</p>
                      </div>
                      <span className="text-xs text-gray-400 font-mono">{example.path}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        
        <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <h4 className="font-medium text-blue-800 dark:text-blue-300 flex items-center gap-2">
            <Info className="h-4 w-4" />
            Running Examples
          </h4>
          <div className="mt-2 text-sm text-blue-700 dark:text-blue-400">
            <code className="bg-blue-100 dark:bg-blue-900/50 px-2 py-1 rounded font-mono text-xs">
              python examples/run_all.py
            </code>
            <span className="ml-2">— Run all examples in isolated subprocesses</span>
          </div>
          <div className="mt-1 text-sm text-blue-700 dark:text-blue-400">
            <code className="bg-blue-100 dark:bg-blue-900/50 px-2 py-1 rounded font-mono text-xs">
              python examples/01_getting_started/01_quickstart.py
            </code>
            <span className="ml-2">— Run a single example</span>
          </div>
        </div>
      </section>

      {/* API Documentation Link */}
      <section>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <ExternalLink className="h-5 w-5" />
          Resources
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 transition-colors"
          >
            <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
              <BookOpen className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <span className="font-medium text-gray-900 dark:text-white">API Docs</span>
              <p className="text-sm text-gray-500">Interactive Swagger UI</p>
            </div>
          </a>
          
          <a
            href="/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 transition-colors"
          >
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <Code className="h-5 w-5 text-orange-600" />
            </div>
            <div>
              <span className="font-medium text-gray-900 dark:text-white">ReDoc</span>
              <p className="text-sm text-gray-500">Alternative API reference</p>
            </div>
          </a>
          
          <a
            href="/openapi.json"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 transition-colors"
          >
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <Server className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <span className="font-medium text-gray-900 dark:text-white">OpenAPI</span>
              <p className="text-sm text-gray-500">JSON specification</p>
            </div>
          </a>
        </div>
      </section>
    </div>
  )
}
