/**
 * Newsfeed Page Types
 * 
 * Centralized type definitions for the newsfeed feature.
 * All components import from this single source of truth.
 */

/**
 * View modes for displaying articles
 */
export type ViewMode = 'condensed' | 'comfortable' | 'headlines' | 'cards' | 'table'

export interface ViewModeOption {
  id: ViewMode
  label: string
  description: string
  icon: string // Icon name for dynamic rendering
}

/**
 * Display-ready feed item
 */
export interface DisplayFeed {
  id: number
  name: string
  url?: string
  count: number
  icon: string
  isActive: boolean
  lastCollected?: string
  isGroup?: boolean
}

/**
 * Display-ready article item
 */
export interface DisplayArticle {
  id: number
  feedId: number
  feedName: string
  feedIcon: string
  title: string
  summary?: string
  content?: string
  link?: string
  author?: string
  publishedAt: Date
  firstSeenAt: Date
  tags: string[]
  isRead: boolean
  isStarred: boolean
  isNew: boolean
  relativeTime: string
  sourceType: 'rss' | 'sec' | 'api' | 'file' | 'unknown'
  metadata?: Record<string, unknown>
}

/**
 * Filter state for articles
 */
export interface ArticleFilters {
  feedId?: number
  search?: string
  isRead?: boolean
  isStarred?: boolean
  dateFrom?: Date
  dateTo?: Date
  tags?: string[]
  sourceType?: DisplayArticle['sourceType']
}

/**
 * Sort options for articles
 */
export type SortField = 'publishedAt' | 'firstSeenAt' | 'title' | 'feedName'
export type SortDirection = 'asc' | 'desc'

export interface SortConfig {
  field: SortField
  direction: SortDirection
}

/**
 * Pagination state
 */
export interface PaginationState {
  page: number
  pageSize: number
  total: number
  hasMore: boolean
}

/**
 * Resizable panel dimensions
 */
export interface PanelDimensions {
  sidebarWidth: number
  detailWidth: number
}

/**
 * Newsfeed page state (for URL sync / persistence)
 */
export interface NewsfeedPageState {
  viewMode: ViewMode
  filters: ArticleFilters
  sort: SortConfig
  pagination: PaginationState
  selectedArticleId?: number
  panels: PanelDimensions
  showDetailPanel: boolean
}

/**
 * Action handlers passed to article components
 */
export interface ArticleActions {
  onSelect: (id: number) => void
  onToggleRead: (id: number) => void
  onToggleStar: (id: number) => void
  onOpenExternal: (url: string) => void
  onRefresh: () => void
}

/**
 * Tag color mapping
 */
export interface TagColorConfig {
  [tag: string]: {
    bg: string
    text: string
    darkBg: string
    darkText: string
  }
}
