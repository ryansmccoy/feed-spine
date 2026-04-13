/**
 * Article List Component
 * 
 * Renders the list of articles in the appropriate view mode.
 */

import { Loader2, AlertCircle, Inbox } from 'lucide-react'
import { clsx } from 'clsx'
import type { DisplayArticle, ViewMode } from '../types'
import { ArticleRow } from './ArticleRow'
import { ArticleCard } from './ArticleCard'
import { ArticleTable } from './ArticleTable'
import { getArticleKey } from '../utils'

export interface ArticleListProps {
  articles: DisplayArticle[]
  viewMode: ViewMode
  selectedId: number | null
  onSelect: (id: number) => void
  onToggleStar?: (id: number) => void
  onOpenExternal?: (url: string) => void
  isLoading?: boolean
  error?: Error | null
}

export function ArticleList({
  articles,
  viewMode,
  selectedId,
  onSelect,
  onToggleStar,
  onOpenExternal,
  isLoading,
  error,
}: ArticleListProps) {
  // Loading state
  if (isLoading && articles.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-gray-500">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">Loading articles...</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-red-500">
          <AlertCircle className="h-8 w-8" />
          <span className="text-sm">Failed to load articles</span>
          <span className="text-xs text-gray-500">{error.message}</span>
        </div>
      </div>
    )
  }

  // Empty state
  if (articles.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-gray-500">
          <Inbox className="h-8 w-8" />
          <span className="text-sm">No articles found</span>
          <span className="text-xs">Try adjusting your filters or adding feeds</span>
        </div>
      </div>
    )
  }

  // Table view - special layout
  if (viewMode === 'table') {
    return (
      <ArticleTable
        articles={articles}
        selectedId={selectedId}
        onSelect={onSelect}
        onToggleStar={onToggleStar}
        onOpenExternal={onOpenExternal}
      />
    )
  }

  // Card view - grid layout
  if (viewMode === 'cards') {
    return (
      <div className="flex-1 overflow-y-auto p-4">
        <div className={clsx(
          'grid gap-3',
          'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
        )}>
          {articles.map(article => (
            <ArticleCard
              key={getArticleKey(article)}
              article={article}
              isSelected={selectedId === article.id}
              onClick={() => onSelect(article.id)}
              onToggleStar={onToggleStar ? () => onToggleStar(article.id) : undefined}
              onOpenExternal={onOpenExternal ? () => article.link && onOpenExternal(article.link) : undefined}
            />
          ))}
        </div>
      </div>
    )
  }

  // List views (condensed, comfortable, headlines)
  return (
    <div className="flex-1 overflow-y-auto">
      {articles.map(article => (
        <ArticleRow
          key={getArticleKey(article)}
          article={article}
          viewMode={viewMode}
          isSelected={selectedId === article.id}
          onClick={() => onSelect(article.id)}
          onToggleStar={onToggleStar ? () => onToggleStar(article.id) : undefined}
          onOpenExternal={onOpenExternal ? () => article.link && onOpenExternal(article.link) : undefined}
        />
      ))}
    </div>
  )
}
