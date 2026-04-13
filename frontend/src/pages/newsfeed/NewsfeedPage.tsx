/**
 * NewsfeedPage Component
 * 
 * Main page component that composes all newsfeed sub-components.
 * Features:
 * - Three-panel layout (sidebar, list, detail)
 * - Multiple view modes (condensed, comfortable, headlines, cards, table)
 * - Real-time search and filtering
 * - Keyboard navigation
 * - Resizable panels with persistence
 */

import { useState, useMemo } from 'react'
import { clsx } from 'clsx'

import { useNewsfeedPage } from './hooks'
import { 
  FeedSidebar, 
  Toolbar, 
  ArticleList, 
  ArticleTable,
  ArticleDetail,
} from './components'

export function NewsfeedPage() {
  const {
    // Data
    feeds,
    articles,
    selectedArticle,
    
    // Loading states
    isLoading,
    isRefetching,
    error,
    
    // View state
    viewMode,
    setViewMode,
    showDetailPanel,
    toggleDetailPanel,
    
    // Panel dimensions from hook
    panels,
    
    // Search & filters
    searchQuery,
    setSearchQuery,
    isSearchFocused,
    setIsSearchFocused,
    filters,
    setFilters,
    
    // Selection
    selectFeed,
    setSelectedId,
    
    // Pagination
    page,
    setPage,
    pageSize,
    totalRecords,
    
    // Actions
    refresh,
  } = useNewsfeedPage()

  // State for sidebar visibility
  const [showSidebar, setShowSidebar] = useState(true)
  
  // Get selected feed based on filters
  const selectedFeedId = useMemo(() => filters.feedId ?? null, [filters.feedId])

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-lg font-semibold text-red-600 dark:text-red-400">
            Error loading newsfeed
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            {error instanceof Error ? error.message : 'An unexpected error occurred'}
          </p>
          <button
            onClick={refresh}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-[#15151F]">
      {/* Toolbar */}
      <Toolbar
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        isSearchFocused={isSearchFocused}
        onSearchFocus={() => setIsSearchFocused(true)}
        onSearchBlur={() => setIsSearchFocused(false)}
        filters={filters}
        onFiltersChange={setFilters}
        showDetailPanel={showDetailPanel}
        onToggleDetailPanel={toggleDetailPanel}
        onRefresh={refresh}
        isRefetching={isRefetching}
        totalRecords={totalRecords}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
      />

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Sidebar */}
        {showSidebar && (
          <div 
            style={{ width: panels.sidebar.width }}
            className="flex-shrink-0 border-r border-gray-200 dark:border-[#2D2D43] bg-white dark:bg-[#1E1E2D]"
          >
            <FeedSidebar
              feeds={feeds}
              selectedFeedId={selectedFeedId}
              onSelectFeed={selectFeed}
            />
          </div>
        )}

        {/* Article list/table */}
        <div className="flex-1 min-w-0 overflow-hidden bg-white dark:bg-[#1E1E2D]">
          {viewMode === 'table' ? (
            <ArticleTable
              articles={articles}
              selectedId={selectedArticle?.id ?? null}
              onSelect={setSelectedId}
              isLoading={isLoading}
            />
          ) : (
            <ArticleList
              articles={articles}
              selectedId={selectedArticle?.id ?? null}
              onSelect={setSelectedId}
              viewMode={viewMode}
              isLoading={isLoading}
            />
          )}
        </div>

        {/* Detail panel */}
        {showDetailPanel && selectedArticle && (
          <div 
            style={{ width: panels.detail.width }}
            className="flex-shrink-0 border-l border-gray-200 dark:border-[#2D2D43] bg-white dark:bg-[#1E1E2D]"
          >
            <ArticleDetail
              article={selectedArticle}
              onToggleStar={() => {/* TODO: implement */}}
              onToggleRead={() => {/* TODO: implement */}}
            />
          </div>
        )}

        {/* Empty detail panel placeholder */}
        {showDetailPanel && !selectedArticle && (
          <div 
            style={{ width: panels.detail.width }}
            className={clsx(
              'flex-shrink-0 flex items-center justify-center',
              'border-l border-gray-200 dark:border-[#2D2D43]',
              'bg-gray-50 dark:bg-[#15151F]'
            )}
          >
            <p className="text-sm text-gray-400">
              Select an article to preview
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
