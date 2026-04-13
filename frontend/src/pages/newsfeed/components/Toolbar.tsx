/**
 * Newsfeed Toolbar Component
 * 
 * Header toolbar with search, filters, and actions.
 */

import { useRef, useEffect } from 'react'
import { 
  Search, 
  RefreshCw, 
  Filter, 
  X,
  PanelRightClose,
  PanelRightOpen,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Mail,
  Star,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { ViewMode, ArticleFilters } from '../types'
import { ViewModeSelector } from './ViewModeSelector'

interface ToolbarProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  searchQuery: string
  onSearchChange: (query: string) => void
  isSearchFocused: boolean
  onSearchFocus: () => void
  onSearchBlur: () => void
  filters: ArticleFilters
  onFiltersChange: (filters: ArticleFilters) => void
  showDetailPanel: boolean
  onToggleDetailPanel: () => void
  onRefresh: () => void
  isRefetching: boolean
  totalRecords: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
}

export function Toolbar({
  viewMode,
  onViewModeChange,
  searchQuery,
  onSearchChange,
  isSearchFocused,
  onSearchFocus,
  onSearchBlur,
  filters,
  onFiltersChange,
  showDetailPanel,
  onToggleDetailPanel,
  onRefresh,
  isRefetching,
  totalRecords,
  page,
  pageSize,
  onPageChange,
}: ToolbarProps) {
  const searchRef = useRef<HTMLInputElement>(null)
  const totalPages = Math.ceil(totalRecords / pageSize)
  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, totalRecords)

  // Focus search when triggered
  useEffect(() => {
    if (isSearchFocused && searchRef.current) {
      searchRef.current.focus()
    }
  }, [isSearchFocused])

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-[#2D2D43] bg-white dark:bg-[#1E1E2D]">
      {/* Left side - Search and filters */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className={clsx(
          'flex items-center gap-2 px-2 py-1 rounded-md border transition-colors',
          isSearchFocused
            ? 'border-primary-500 ring-1 ring-primary-500'
            : 'border-gray-200 dark:border-[#2D2D43]'
        )}>
          <Search className="h-4 w-4 text-gray-400" />
          <input
            ref={searchRef}
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            onFocus={onSearchFocus}
            onBlur={onSearchBlur}
            placeholder="Search articles... (press /)"
            className={clsx(
              'w-48 sm:w-64 text-sm bg-transparent border-none outline-none',
              'text-gray-900 dark:text-white placeholder-gray-400'
            )}
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Filter toggles */}
        <div className="flex items-center gap-1">
          <FilterToggle
            icon={<Mail className="h-3.5 w-3.5" />}
            label="Unread"
            isActive={filters.isRead === false}
            onClick={() => onFiltersChange({
              ...filters,
              isRead: filters.isRead === false ? undefined : false
            })}
          />
          <FilterToggle
            icon={<Star className="h-3.5 w-3.5" />}
            label="Starred"
            isActive={filters.isStarred === true}
            onClick={() => onFiltersChange({
              ...filters,
              isStarred: filters.isStarred === true ? undefined : true
            })}
          />
        </div>
      </div>

      {/* Right side - View controls and pagination */}
      <div className="flex items-center gap-3">
        {/* Pagination info */}
        {totalRecords > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 tabular-nums">
              {startItem}–{endItem} of {totalRecords.toLocaleString()}
            </span>
            <div className="flex items-center">
              <button
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                className={clsx(
                  'p-1 rounded hover:bg-gray-100 dark:hover:bg-[#2D2D43]',
                  'disabled:opacity-30 disabled:cursor-not-allowed'
                )}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                className={clsx(
                  'p-1 rounded hover:bg-gray-100 dark:hover:bg-[#2D2D43]',
                  'disabled:opacity-30 disabled:cursor-not-allowed'
                )}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Divider */}
        <div className="h-5 w-px bg-gray-200 dark:bg-[#2D2D43]" />

        {/* View mode */}
        <ViewModeSelector 
          viewMode={viewMode} 
          onChange={onViewModeChange} 
        />

        {/* Toggle detail panel */}
        <button
          onClick={onToggleDetailPanel}
          className={clsx(
            'p-1.5 rounded',
            'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
            'hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
          )}
          title={showDetailPanel ? 'Hide detail panel' : 'Show detail panel'}
        >
          {showDetailPanel ? (
            <PanelRightClose className="h-4 w-4" />
          ) : (
            <PanelRightOpen className="h-4 w-4" />
          )}
        </button>

        {/* Refresh */}
        <button
          onClick={onRefresh}
          disabled={isRefetching}
          className={clsx(
            'p-1.5 rounded',
            'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
            'hover:bg-gray-100 dark:hover:bg-[#2D2D43]',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
          title="Refresh (r)"
        >
          {isRefetching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  )
}

// Filter toggle button
interface FilterToggleProps {
  icon: React.ReactNode
  label: string
  isActive: boolean
  onClick: () => void
}

function FilterToggle({ icon, label, isActive, onClick }: FilterToggleProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors',
        isActive
          ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
          : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-[#2D2D43]'
      )}
      title={label}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  )
}
