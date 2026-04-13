/**
 * Article Detail Component
 * 
 * Detail panel showing full article content.
 */

import { 
  X, 
  ExternalLink, 
  Star, 
  Mail, 
  MailOpen,
  Clock,
  UserCircle,
  Tag,
  Link2,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayArticle } from '../types'
import { ResizeHandle } from './ResizeHandle'
import { getTagColorClasses } from '../utils'
import { format } from 'date-fns'

export interface ArticleDetailProps {
  article: DisplayArticle | null
  onClose?: () => void
  onToggleStar?: () => void
  onToggleRead?: () => void
  onOpenExternal?: (url: string) => void
  width?: number
  isResizing?: boolean
  onResizeStart?: (e: React.MouseEvent) => void
}

export function ArticleDetail({
  article,
  onClose,
  onToggleStar,
  onToggleRead,
  onOpenExternal,
  width = 400,
  isResizing = false,
  onResizeStart,
}: ArticleDetailProps) {
  if (!article) {
    return (
      <div 
        className="flex h-full"
        style={{ width }}
      >
        <ResizeHandle 
          onMouseDown={onResizeStart}
          isResizing={isResizing}
        />
        <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-[#1A1A26]">
          <div className="text-center text-gray-500">
            <p className="text-sm">Select an article to view details</p>
            <p className="text-xs mt-1">Use ↑↓ or j/k to navigate</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div 
      className="flex h-full"
      style={{ width }}
    >
      {/* Resize handle */}
      {onResizeStart && (
        <ResizeHandle 
          onMouseDown={onResizeStart}
          isResizing={isResizing}
        />
      )}

      {/* Detail content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-[#1E1E2D] border-l border-gray-200 dark:border-[#2D2D43]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-[#2D2D43]">
          <div className="flex items-center gap-2">
            <span className="text-xl">{article.feedIcon}</span>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {article.feedName}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {/* Toggle read */}
            <button
              onClick={() => onToggleRead?.()}
              className={clsx(
                'p-1.5 rounded',
                'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
                'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
              )}
              title={article.isRead ? 'Mark as unread' : 'Mark as read'}
            >
              {article.isRead ? (
                <MailOpen className="h-4 w-4" />
              ) : (
                <Mail className="h-4 w-4" />
              )}
            </button>

            {/* Star */}
            <button
              onClick={() => onToggleStar?.()}
              className={clsx(
                'p-1.5 rounded',
                article.isStarred
                  ? 'text-yellow-500'
                  : 'text-gray-500 hover:text-yellow-500',
                'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
              )}
              title={article.isStarred ? 'Unstar' : 'Star'}
            >
              <Star className={clsx('h-4 w-4', article.isStarred && 'fill-current')} />
            </button>

            {/* External link */}
            {article.link && (
              <button
                onClick={() => onOpenExternal?.(article.link!)}
                className={clsx(
                  'p-1.5 rounded',
                  'text-gray-500 hover:text-primary-500',
                  'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
                )}
                title="Open in new tab"
              >
                <ExternalLink className="h-4 w-4" />
              </button>
            )}

            {/* Close */}
            {onClose && (
              <button
                onClick={onClose}
                className={clsx(
                  'p-1.5 rounded',
                  'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
                  'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
                )}
                title="Close panel"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Title */}
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            {article.title}
          </h2>

          {/* Metadata */}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500 dark:text-gray-400 mb-4">
            {/* Time */}
            <div className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              <span>{format(article.publishedAt, 'PPpp')}</span>
            </div>

            {/* Author */}
            {article.author && (
              <div className="flex items-center gap-1">
                <UserCircle className="h-3.5 w-3.5" />
                <span>{article.author}</span>
              </div>
            )}

            {/* Source link */}
            {article.link && (
              <div className="flex items-center gap-1">
                <Link2 className="h-3.5 w-3.5" />
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-primary-500 hover:underline truncate max-w-xs"
                  onClick={(e) => e.stopPropagation()}
                >
                  {new URL(article.link).hostname}
                </a>
              </div>
            )}
          </div>

          {/* Tags */}
          {article.tags.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <Tag className="h-3.5 w-3.5 text-gray-400" />
              <div className="flex flex-wrap gap-1">
                {article.tags.map(tag => (
                  <span
                    key={tag}
                    className={clsx(
                      'rounded px-2 py-0.5',
                      'text-xs font-medium',
                      getTagColorClasses(tag)
                    )}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Divider */}
          <hr className="border-gray-200 dark:border-[#2D2D43] my-4" />

          {/* Summary */}
          {article.summary && (
            <div className="mb-4">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">
                Summary
              </h3>
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {article.summary}
              </p>
            </div>
          )}

          {/* Content */}
          {article.content && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">
                Content
              </h3>
              <div 
                className="prose prose-sm dark:prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: article.content }}
              />
            </div>
          )}

          {/* No content message */}
          {!article.summary && !article.content && (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No content available</p>
              {article.link && onOpenExternal && (
                <button
                  onClick={() => onOpenExternal(article.link!)}
                  className="mt-2 text-primary-500 hover:underline text-sm"
                >
                  View original article →
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
