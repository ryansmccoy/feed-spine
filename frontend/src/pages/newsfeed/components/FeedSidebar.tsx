/**
 * Feed Sidebar Component
 * 
 * Left sidebar showing list of feeds with counts.
 */

import { RefreshCw, Loader2, Rss } from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayFeed } from '../types'
import { ResizeHandle } from './ResizeHandle'

export interface FeedSidebarProps {
  feeds: DisplayFeed[]
  selectedFeedId?: number | null
  onSelectFeed: (feedId: number | undefined) => void
  onRefresh?: () => void
  isRefetching?: boolean
  width?: number
  isResizing?: boolean
  onResizeStart?: (e: React.MouseEvent) => void
}

export function FeedSidebar({
  feeds,
  selectedFeedId,
  onSelectFeed,
  onRefresh,
  isRefetching = false,
  width,
  isResizing = false,
  onResizeStart,
}: FeedSidebarProps) {
  // Calculate total count
  const totalCount = feeds.reduce((sum, feed) => sum + feed.count, 0)

  return (
    <div 
      className="flex h-full"
      style={width ? { width } : undefined}
    >
      {/* Sidebar content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-50 dark:bg-[#1A1A26]">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-[#2D2D43]">
          <div className="flex items-center gap-2">
            <Rss className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Feeds
            </span>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefetching}
              className={clsx(
                'p-1 rounded hover:bg-gray-200 dark:hover:bg-[#2D2D43]',
                'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'transition-colors'
              )}
              title="Refresh feeds"
            >
              {isRefetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        {/* Feed list */}
        <div className="flex-1 overflow-y-auto py-1">
          {/* All feeds item */}
          <FeedItem
            feed={{
              id: 0,
              name: 'All Articles',
              count: totalCount,
              icon: '📖',
              isActive: true,
            }}
            isSelected={selectedFeedId === undefined}
            onClick={() => onSelectFeed(undefined)}
          />

          {/* Divider */}
          <div className="h-px bg-gray-200 dark:bg-[#2D2D43] my-1 mx-3" />

          {/* Individual feeds */}
          {feeds.map(feed => (
            <FeedItem
              key={feed.id}
              feed={feed}
              isSelected={selectedFeedId === feed.id}
              onClick={() => onSelectFeed(feed.id)}
            />
          ))}

          {feeds.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-gray-500">
              No feeds configured
            </div>
          )}
        </div>
      </div>

      {/* Resize handle */}
      {onResizeStart && (
        <ResizeHandle 
          onMouseDown={onResizeStart}
          isResizing={isResizing}
        />
      )}
    </div>
  )
}

// Individual feed item
interface FeedItemProps {
  feed: DisplayFeed
  isSelected: boolean
  onClick: () => void
}

function FeedItem({ feed, isSelected, onClick }: FeedItemProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full flex items-center gap-2 px-3 py-1.5 text-left',
        'transition-colors',
        isSelected
          ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
          : 'hover:bg-gray-100 dark:hover:bg-[#252536] text-gray-700 dark:text-gray-300',
        !feed.isActive && 'opacity-50'
      )}
    >
      <span className="text-base flex-shrink-0">{feed.icon}</span>
      <span className="flex-1 text-sm truncate">{feed.name}</span>
      <span className={clsx(
        'text-xs tabular-nums flex-shrink-0',
        isSelected 
          ? 'text-primary-600 dark:text-primary-400'
          : 'text-gray-400 dark:text-gray-500'
      )}>
        {feed.count > 0 ? feed.count.toLocaleString() : ''}
      </span>
    </button>
  )
}
