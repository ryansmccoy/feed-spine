/**
 * Article Card Component
 * 
 * Card-style article item for grid view.
 */

import { Star, ExternalLink, Clock } from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayArticle } from '../types'
import { getTagColorClasses } from '../utils'

interface ArticleCardProps {
  article: DisplayArticle
  isSelected: boolean
  onClick: () => void
  onToggleStar?: () => void
  onOpenExternal?: () => void
}

export function ArticleCard({
  article,
  isSelected,
  onClick,
  onToggleStar,
  onOpenExternal,
}: ArticleCardProps) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'group rounded-lg border p-3 cursor-pointer transition-all',
        isSelected
          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 shadow-sm'
          : 'border-gray-200 dark:border-[#2D2D43] hover:border-primary-300 dark:hover:border-primary-700 hover:shadow-sm',
        !article.isRead && 'border-l-2 border-l-primary-500'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{article.feedIcon}</span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {article.feedName}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {/* External link */}
          {article.link && onOpenExternal && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onOpenExternal()
              }}
              className={clsx(
                'flex h-6 w-6 items-center justify-center rounded',
                'text-gray-300 opacity-0 group-hover:opacity-100',
                'hover:text-primary-500 hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
              )}
              title="Open in new tab"
            >
              <ExternalLink className="h-4 w-4" />
            </button>
          )}
          
          {/* Star */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleStar?.()
            }}
            className={clsx(
              'flex h-6 w-6 items-center justify-center rounded',
              article.isStarred 
                ? 'text-yellow-500' 
                : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-yellow-500',
              'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
            )}
            title={article.isStarred ? 'Unstar' : 'Star'}
          >
            <Star className={clsx('h-4 w-4', article.isStarred && 'fill-current')} />
          </button>
        </div>
      </div>
      
      {/* Title */}
      <h4 className={clsx(
        'text-sm leading-snug mb-2 line-clamp-2',
        article.isRead 
          ? 'text-gray-500 dark:text-gray-400' 
          : 'text-gray-900 dark:text-white font-medium'
      )}>
        {article.title}
      </h4>

      {/* Summary (if available) */}
      {article.summary && (
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-2">
          {article.summary}
        </p>
      )}
      
      {/* Footer */}
      <div className="flex items-center justify-between">
        {/* Tags */}
        <div className="flex flex-wrap gap-1">
          {article.tags.slice(0, 2).map((tag) => (
            <span
              key={tag}
              className={clsx(
                'rounded px-1.5 py-0.5',
                'text-[9px] font-semibold uppercase',
                getTagColorClasses(tag)
              )}
            >
              {tag}
            </span>
          ))}
        </div>
        
        {/* Time */}
        <div className="flex items-center gap-1 text-[10px] text-gray-400">
          <Clock className="h-3 w-3" />
          <span className="tabular-nums">{article.relativeTime}</span>
        </div>
      </div>

      {/* New badge */}
      {article.isNew && !article.isRead && (
        <div className="absolute top-2 right-2">
          <span className="px-1.5 py-0.5 bg-primary-500 text-white text-[9px] font-semibold rounded">
            NEW
          </span>
        </div>
      )}
    </div>
  )
}
