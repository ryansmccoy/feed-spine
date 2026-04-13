/**
 * Article Table Component
 * 
 * Full table view with sortable columns.
 */

import { Star, ExternalLink, ChevronUp, ChevronDown } from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayArticle } from '../types'
import { getTagColorClasses, getArticleKey } from '../utils'

interface ArticleTableProps {
  articles: DisplayArticle[]
  selectedId: number | null
  onSelect: (id: number) => void
  onToggleStar?: (id: number) => void
  onOpenExternal?: (url: string) => void
  isLoading?: boolean
}

interface TableColumn {
  id: string
  label: string
  width: string
  sortable?: boolean
}

const COLUMNS: TableColumn[] = [
  { id: 'star', label: '', width: 'w-10' },
  { id: 'feed', label: 'Feed', width: 'w-24' },
  { id: 'title', label: 'Title', width: 'flex-1', sortable: true },
  { id: 'tags', label: 'Tags', width: 'w-32' },
  { id: 'published', label: 'Published', width: 'w-24', sortable: true },
  { id: 'actions', label: '', width: 'w-10' },
]

export function ArticleTable({
  articles,
  selectedId,
  onSelect,
  onToggleStar,
  onOpenExternal,
  isLoading,
}: ArticleTableProps) {
  // Loading state
  if (isLoading && articles.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-gray-500">Loading...</span>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full min-w-[800px]">
        {/* Header */}
        <thead className="sticky top-0 bg-gray-50 dark:bg-[#1A1A26] border-b border-gray-200 dark:border-[#2D2D43]">
          <tr>
            {COLUMNS.map(column => (
              <th
                key={column.id}
                className={clsx(
                  'px-3 py-2 text-left text-xs font-medium',
                  'text-gray-500 dark:text-gray-400 uppercase tracking-wider',
                  column.width
                )}
              >
                {column.sortable ? (
                  <button className="flex items-center gap-1 hover:text-gray-700 dark:hover:text-gray-300">
                    {column.label}
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>

        {/* Body */}
        <tbody className="divide-y divide-gray-100 dark:divide-[#252536]">
          {articles.map(article => (
            <tr
              key={getArticleKey(article)}
              onClick={() => onSelect(article.id)}
              className={clsx(
                'cursor-pointer transition-colors group',
                selectedId === article.id
                  ? 'bg-primary-50 dark:bg-primary-900/20'
                  : 'hover:bg-gray-50 dark:hover:bg-[#1B1B29]',
                !article.isRead && 'bg-blue-50/30 dark:bg-blue-900/5'
              )}
            >
              {/* Star */}
              <td className="px-3 py-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleStar?.(article.id)
                  }}
                  className={clsx(
                    'flex h-6 w-6 items-center justify-center rounded',
                    article.isStarred
                      ? 'text-yellow-500'
                      : 'text-gray-300 opacity-0 group-hover:opacity-100 hover:text-yellow-500'
                  )}
                >
                  <Star className={clsx('h-4 w-4', article.isStarred && 'fill-current')} />
                </button>
              </td>

              {/* Feed */}
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">{article.feedIcon}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {article.feedName}
                  </span>
                </div>
              </td>

              {/* Title */}
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  {!article.isRead && (
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0" />
                  )}
                  <span className={clsx(
                    'text-sm truncate max-w-md',
                    article.isRead
                      ? 'text-gray-500 dark:text-gray-400'
                      : 'text-gray-900 dark:text-white font-medium'
                  )}>
                    {article.title}
                  </span>
                </div>
              </td>

              {/* Tags */}
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {article.tags.slice(0, 2).map(tag => (
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
              </td>

              {/* Published */}
              <td className="px-3 py-2">
                <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                  {article.relativeTime}
                </span>
              </td>

              {/* Actions */}
              <td className="px-3 py-2">
                {article.link && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onOpenExternal?.(article.link!)
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
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
