/**
 * Article Row Component
 * 
 * Single article item for list view (condensed, comfortable, headlines modes).
 */

import { Star, Check, ExternalLink } from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayArticle, ViewMode } from '../types'
import { getTagColorClasses } from '../utils'

interface ArticleRowProps {
  article: DisplayArticle
  viewMode: ViewMode
  isSelected: boolean
  onClick: () => void
  onToggleStar?: () => void
  onOpenExternal?: () => void
}

export function ArticleRow({
  article,
  viewMode,
  isSelected,
  onClick,
  onToggleStar,
  onOpenExternal,
}: ArticleRowProps) {
  const isCondensed = viewMode === 'condensed'
  const isHeadlines = viewMode === 'headlines'

  // Headlines mode - ultra compact
  if (isHeadlines) {
    return (
      <div
        onClick={onClick}
        className={clsx(
          'flex items-center px-3 py-1 border-b border-gray-50 dark:border-[#252536]',
          'cursor-pointer transition-colors group',
          isSelected
            ? 'bg-primary-50 dark:bg-primary-900/20'
            : 'hover:bg-gray-50 dark:hover:bg-[#1B1B29]',
          !article.isRead && 'bg-blue-50/30 dark:bg-blue-900/5'
        )}
      >
        {/* Unread indicator */}
        {!article.isRead && (
          <div className="w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0 mr-2" />
        )}
        
        {/* Title */}
        <span className={clsx(
          'flex-1 text-[13px] truncate',
          article.isRead 
            ? 'text-gray-500 dark:text-gray-400' 
            : 'text-gray-900 dark:text-white font-medium'
        )}>
          {article.title}
        </span>
        
        {/* Time */}
        <span className="text-[11px] text-gray-400 tabular-nums ml-2">
          {article.relativeTime}
        </span>
      </div>
    )
  }

  // Condensed/Comfortable mode
  return (
    <div
      onClick={onClick}
      className={clsx(
        'flex items-center px-3 border-b border-gray-50 dark:border-[#252536]',
        'cursor-pointer transition-colors group',
        isCondensed ? 'py-1' : 'py-2',
        isSelected
          ? 'bg-primary-50 dark:bg-primary-900/20'
          : 'hover:bg-gray-50 dark:hover:bg-[#1B1B29]',
        !article.isRead && 'bg-blue-50/30 dark:bg-blue-900/5'
      )}
    >
      {/* Star button */}
      <div className="w-8 flex-shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleStar?.()
          }}
          className={clsx(
            'flex h-5 w-5 items-center justify-center rounded',
            article.isStarred 
              ? 'text-yellow-500' 
              : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-yellow-500'
          )}
          title={article.isStarred ? 'Unstar' : 'Star'}
        >
          <Star className={clsx('h-3.5 w-3.5', article.isStarred && 'fill-current')} />
        </button>
      </div>

      {/* Feed icon */}
      <div className="w-10 flex-shrink-0">
        <span className="text-sm" title={article.feedName}>
          {article.feedIcon}
        </span>
      </div>

      {/* Title + tags */}
      <div className="flex-1 min-w-0 flex items-center gap-2">
        {/* New indicator */}
        {article.isNew && !article.isRead && (
          <div className="w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0" />
        )}
        
        {/* Title */}
        <span className={clsx(
          'text-[13px] truncate',
          article.isRead 
            ? 'text-gray-500 dark:text-gray-400' 
            : 'text-gray-900 dark:text-white font-medium'
        )}>
          {article.title}
        </span>
        
        {/* Tags (limit to 2) */}
        {article.tags.slice(0, 2).map((tag) => (
          <span
            key={tag}
            className={clsx(
              'flex-shrink-0 rounded px-1.5 py-0.5',
              'text-[9px] font-semibold uppercase',
              getTagColorClasses(tag)
            )}
          >
            {tag}
          </span>
        ))}
      </div>

      {/* External link button */}
      {article.link && onOpenExternal && (
        <div className="w-8 flex-shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onOpenExternal()
            }}
            className={clsx(
              'flex h-5 w-5 items-center justify-center rounded',
              'text-gray-300 opacity-0 group-hover:opacity-100',
              'hover:text-primary-500'
            )}
            title="Open in new tab"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Time */}
      <div className="w-14 flex-shrink-0 text-right pr-2">
        <span className="text-[11px] text-gray-400 tabular-nums">
          {article.relativeTime}
        </span>
      </div>
    </div>
  )
}
