import { useState} from 'react'
import {
  Clock,
  Star,
  ExternalLink,
  RefreshCw,
  ChevronRight,
  Sparkles,
  Rss,
} from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow, format, isToday, isYesterday, startOfDay } from 'date-fns'
import { useRecords, useUpdateRecord, useFeedStats, useCollectFeed } from '@/api/hooks'
import { FeedRecord, enrichRecord } from '@/api'

// Time grouping helper
function getTimeGroup(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = diffMs / (1000 * 60 * 60)

  if (diffHours < 1) return 'Last Hour'
  if (diffHours < 4) return 'Last 4 Hours'
  if (isToday(date)) return 'Today'
  if (isYesterday(date)) return 'Yesterday'
  return format(date, 'EEEE, MMM d')
}

// Group records by time
function groupRecordsByTime(records: FeedRecord[]): Map<string, FeedRecord[]> {
  const groups = new Map<string, FeedRecord[]>()
  
  for (const record of records) {
    const group = getTimeGroup(record.published_at || record.first_seen_at)
    if (!groups.has(group)) {
      groups.set(group, [])
    }
    groups.get(group)!.push(record)
  }
  
  return groups
}

// Article list item component
function ArticleListItem({
  record,
  onSelect,
  onToggleStar,
}: {
  record: FeedRecord
  onSelect: () => void
  onToggleStar: () => void
}) {
  const enriched = enrichRecord(record)
  const publishedDate = new Date(record.published_at || record.first_seen_at)

  return (
    <div
      onClick={onSelect}
      className={clsx(
        'group flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-colors',
        'hover:bg-gray-50 dark:hover:bg-gray-800/50',
        record.is_read && 'opacity-60'
      )}
    >
      {/* Feed Icon */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
        <Rss className="h-4 w-4 text-primary-600 dark:text-primary-400" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <h4
            className={clsx(
              'text-sm leading-snug',
              record.is_read
                ? 'text-gray-500 dark:text-gray-400'
                : 'font-medium text-gray-900 dark:text-white'
            )}
          >
            {record.title}
          </h4>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleStar()
            }}
            className={clsx(
              'flex-shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity',
              record.is_starred
                ? 'text-yellow-500 opacity-100'
                : 'text-gray-300 hover:text-yellow-500'
            )}
          >
            <Star className={clsx('h-4 w-4', record.is_starred && 'fill-current')} />
          </button>
        </div>

        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500 dark:text-gray-400">
          <span>Feed {record.feed_id}</span>
          {enriched.form_type && (
            <>
              <span>•</span>
              <span className="font-medium text-primary-600 dark:text-primary-400">
                {enriched.form_type}
              </span>
            </>
          )}
          {enriched.ticker && (
            <>
              <span>•</span>
              <span className="font-mono">{enriched.ticker}</span>
            </>
          )}
          <span>•</span>
          <span>{formatDistanceToNow(publishedDate, { addSuffix: true })}</span>
        </div>
      </div>

      {/* Open in new tab */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          window.open(record.link, '_blank')
        }}
        className="flex-shrink-0 p-1 text-gray-300 hover:text-gray-500 dark:hover:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <ExternalLink className="h-4 w-4" />
      </button>
    </div>
  )
}

// Section component
function Section({
  title,
  icon: Icon,
  iconColor,
  children,
  count,
  onRefresh,
}: {
  title: string
  icon: React.ElementType
  iconColor: string
  children: React.ReactNode
  count?: number
  onRefresh?: () => void
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <div className={clsx('p-1.5 rounded-lg', iconColor)}>
            <Icon className="h-4 w-4 text-white" />
          </div>
          <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
          {count !== undefined && (
            <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
              {count}
            </span>
          )}
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        {children}
      </div>
    </div>
  )
}

// Main TodayView component
export default function TodayView() {
  const [selectedRecord, setSelectedRecord] = useState<FeedRecord | null>(null)

  // Fetch data
  const { data: allRecords = [], isLoading, refetch } = useRecords()
  const { data: feedStats = [] } = useFeedStats()
  const updateRecord = useUpdateRecord()
  const collectFeed = useCollectFeed()

  // Filter records
  const todayStart = startOfDay(new Date())
  const recentRecords = allRecords
    .filter((r) => new Date(r.published_at || r.first_seen_at) >= todayStart)
    .sort((a, b) => {
      const dateA = new Date(a.published_at || a.first_seen_at)
      const dateB = new Date(b.published_at || b.first_seen_at)
      return dateB.getTime() - dateA.getTime()
    })

  const starredRecords = allRecords.filter((r) => r.is_starred)
  const unreadCount = allRecords.filter((r) => !r.is_read).length

  // Group recent records by time
  const groupedRecords = groupRecordsByTime(recentRecords)

  // Handlers
  const handleSelectRecord = (record: FeedRecord) => {
    setSelectedRecord(record)
    if (!record.is_read) {
      updateRecord.mutate({
        id: record.id,
        updates: { is_read: true },
      })
    }
  }

  const handleToggleStar = (record: FeedRecord) => {
    updateRecord.mutate({
      id: record.id,
      updates: { is_starred: !record.is_starred },
    })
  }

  const handleRefresh = () => {
    refetch()
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
            Today's Feed
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {recentRecords.length} articles • {unreadCount} unread
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh All
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Feed */}
        <div className="lg:col-span-2 space-y-4">
          {Array.from(groupedRecords.entries()).map(([timeGroup, records]) => (
            <Section
              key={timeGroup}
              title={timeGroup}
              icon={Clock}
              iconColor="bg-blue-500"
              count={records.length}
            >
              {records.map((record) => (
                <ArticleListItem
                  key={record.id}
                  record={record}
                  onSelect={() => handleSelectRecord(record)}
                  onToggleStar={() => handleToggleStar(record)}
                />
              ))}
            </Section>
          ))}

          {groupedRecords.size === 0 && (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <Rss className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No articles yet today</p>
              <button
                onClick={handleRefresh}
                className="mt-4 text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium text-sm"
              >
                Refresh feeds
              </button>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Starred */}
          {starredRecords.length > 0 && (
            <Section
              title="Starred"
              icon={Star}
              iconColor="bg-yellow-500"
              count={starredRecords.length}
            >
              {starredRecords.slice(0, 5).map((record) => (
                <ArticleListItem
                  key={record.id}
                  record={record}
                  onSelect={() => handleSelectRecord(record)}
                  onToggleStar={() => handleToggleStar(record)}
                />
              ))}
            </Section>
          )}

          {/* Feed Stats */}
          <Section
            title="Feed Activity"
            icon={Sparkles}
            iconColor="bg-purple-500"
          >
            <div className="p-4 space-y-3">
              {feedStats.slice(0, 5).map((stat) => (
                <div
                  key={stat.feed_id}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-gray-600 dark:text-gray-300">
                    Feed {stat.feed_id}
                  </span>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{stat.total_records} total</span>
                    <span className="text-primary-600 dark:text-primary-400 font-medium">
                      {stat.unread_count} unread
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>

      {/* Article Detail Modal (Simple) */}
      {selectedRecord && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedRecord(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white pr-8">
                  {selectedRecord.title}
                </h3>
                <button
                  onClick={() => setSelectedRecord(null)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  ✕
                </button>
              </div>
              
              {selectedRecord.description && (
                <div
                  className="prose dark:prose-invert max-w-none mb-4"
                  dangerouslySetInnerHTML={{ __html: selectedRecord.description }}
                />
              )}

              <a
                href={selectedRecord.link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                Open Original
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
