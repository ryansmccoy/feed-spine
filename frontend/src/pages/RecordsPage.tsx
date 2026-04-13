import { useState } from 'react'
import { Search, Star, StarOff, Eye, EyeOff, Filter, RefreshCw, ExternalLink } from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow, format } from 'date-fns'
import { useRecords, useUpdateRecord, useMarkAllRead } from '@/api/hooks'
import { FeedRecord } from '@/api'

export default function RecordsPage() {
  const [filters, setFilters] = useState({
    search: '',
    is_read: undefined as boolean | undefined,
    is_starred: undefined as boolean | undefined,
    feed_id: undefined as number | undefined,
  })
  const [selectedRecord, setSelectedRecord] = useState<FeedRecord | null>(null)

  const { data: records = [], isLoading, refetch } = useRecords({
    search: filters.search || undefined,
    is_read: filters.is_read,
    is_starred: filters.is_starred,
    feed_id: filters.feed_id,
    limit: 100,
  })
  const updateRecord = useUpdateRecord()
  const markAllRead = useMarkAllRead()

  const handleToggleStar = async (record: FeedRecord) => {
    await updateRecord.mutateAsync({
      id: record.id,
      updates: { is_starred: !record.is_starred },
    })
  }

  const handleToggleRead = async (record: FeedRecord) => {
    await updateRecord.mutateAsync({
      id: record.id,
      updates: { is_read: !record.is_read },
    })
  }

  const handleMarkAllRead = async () => {
    await markAllRead.mutateAsync(filters.feed_id)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 text-gray-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Records
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {records.length} records
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={handleMarkAllRead}
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            <Eye className="h-4 w-4" />
            Mark All Read
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search records..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilters({ ...filters, is_starred: filters.is_starred ? undefined : true })}
            className={clsx(
              'flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              filters.is_starred
                ? 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            )}
          >
            <Star className="h-4 w-4" />
            Starred
          </button>
          <button
            onClick={() => setFilters({ ...filters, is_read: filters.is_read === false ? undefined : false })}
            className={clsx(
              'flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              filters.is_read === false
                ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            )}
          >
            <EyeOff className="h-4 w-4" />
            Unread
          </button>
        </div>
      </div>

      {/* Records List */}
      <div 
        className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-200 dark:divide-gray-700"
        data-testid="article-list"
        role="list"
      >
        {records.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            No records found
          </div>
        ) : (
          records.map((record) => (
            <div
              key={record.id}
              data-testid="article-item"
              role="listitem"
              className={clsx(
                'p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors',
                !record.is_read && 'bg-blue-50/50 dark:bg-blue-900/10'
              )}
              onClick={() => setSelectedRecord(record)}
            >
              <div className="flex items-start gap-4">
                {/* Actions */}
                <div className="flex flex-col gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggleStar(record); }}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      record.is_starred
                        ? 'text-yellow-500 hover:text-yellow-600'
                        : 'text-gray-300 hover:text-gray-400'
                    )}
                    title={record.is_starred ? 'Remove star' : 'Add star'}
                  >
                    {record.is_starred ? <Star className="h-4 w-4 fill-current" /> : <StarOff className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggleRead(record); }}
                    className={clsx(
                      'p-1.5 rounded transition-colors',
                      record.is_read
                        ? 'text-gray-300 hover:text-gray-400'
                        : 'text-blue-500 hover:text-blue-600'
                    )}
                    title={record.is_read ? 'Mark unread' : 'Mark read'}
                  >
                    {record.is_read ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                  </button>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className={clsx(
                      'text-sm font-medium truncate',
                      record.is_read
                        ? 'text-gray-600 dark:text-gray-400'
                        : 'text-gray-900 dark:text-white'
                    )}>
                      {record.title}
                    </h3>
                    {record.link && (
                      <a
                        href={record.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                  {record.description && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                      {record.description}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                    {record.author && <span>{record.author}</span>}
                    {record.published_at && (
                      <span title={format(new Date(record.published_at), 'PPpp')}>
                        {formatDistanceToNow(new Date(record.published_at), { addSuffix: true })}
                      </span>
                    )}
                    {record.form_type && (
                      <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-300">
                        {record.form_type}
                      </span>
                    )}
                    {record.company_name && <span>{record.company_name}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Record Detail Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedRecord(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {selectedRecord.title}
              </h2>
              <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
                {selectedRecord.author && <span>By {selectedRecord.author}</span>}
                {selectedRecord.published_at && (
                  <span>{format(new Date(selectedRecord.published_at), 'PPpp')}</span>
                )}
              </div>
            </div>
            <div className="p-6">
              {selectedRecord.description && (
                <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {selectedRecord.description}
                </p>
              )}
              {selectedRecord.link && (
                <a
                  href={selectedRecord.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 mt-4 text-primary-600 hover:text-primary-700"
                >
                  Open original <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
