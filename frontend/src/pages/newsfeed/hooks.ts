/**
 * Newsfeed Page Hooks
 * 
 * Custom React hooks for newsfeed-specific state management and data fetching.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useFeeds, useRecords } from '../../api/hooks'
import type { 
  ViewMode, 
  DisplayArticle, 
  DisplayFeed, 
  ArticleFilters,
  SortConfig,
  PanelDimensions,
  NewsfeedPageState,
} from './types'
import { transformFeed, transformRecord, filterBySearch, sortArticles, clamp } from './utils'
import { 
  DEFAULT_VIEW_MODE, 
  DEFAULT_SORT, 
  DEFAULT_PAGE_SIZE,
  DEFAULT_PANEL_DIMENSIONS,
  PANEL_CONSTRAINTS,
  STORAGE_KEYS,
  AUTO_REFRESH_INTERVAL,
  KEYBOARD_SHORTCUTS,
} from './constants'

/**
 * Local storage hook with JSON serialization
 */
export function useLocalStorage<T>(key: string, defaultValue: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored ? JSON.parse(stored) : defaultValue
    } catch {
      return defaultValue
    }
  })

  const setStoredValue = useCallback((newValue: T) => {
    setValue(newValue)
    try {
      localStorage.setItem(key, JSON.stringify(newValue))
    } catch {
      // Ignore storage errors
    }
  }, [key])

  return [value, setStoredValue]
}

/**
 * Hook for managing article selection
 */
export function useArticleSelection(articles: DisplayArticle[]) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  
  const selectedArticle = useMemo(() => 
    articles.find(a => a.id === selectedId) ?? null,
    [articles, selectedId]
  )

  const selectNext = useCallback(() => {
    const currentIndex = articles.findIndex(a => a.id === selectedId)
    const nextIndex = currentIndex === -1 ? 0 : Math.min(currentIndex + 1, articles.length - 1)
    setSelectedId(articles[nextIndex]?.id ?? null)
  }, [articles, selectedId])

  const selectPrevious = useCallback(() => {
    const currentIndex = articles.findIndex(a => a.id === selectedId)
    const prevIndex = currentIndex === -1 ? 0 : Math.max(currentIndex - 1, 0)
    setSelectedId(articles[prevIndex]?.id ?? null)
  }, [articles, selectedId])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
  }, [])

  return {
    selectedId,
    selectedArticle,
    setSelectedId,
    selectNext,
    selectPrevious,
    clearSelection,
  }
}

/**
 * Hook for keyboard navigation
 */
export function useKeyboardNavigation({
  onNext,
  onPrev,
  onOpen,
  onToggleRead,
  onToggleStar,
  onRefresh,
  onSearch,
  onEscape,
  enabled = true,
}: {
  onNext: () => void
  onPrev: () => void
  onOpen: () => void
  onToggleRead: () => void
  onToggleStar: () => void
  onRefresh: () => void
  onSearch: () => void
  onEscape: () => void
  enabled?: boolean
}) {
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        if (e.key === 'Escape') onEscape()
        return
      }

      const key = e.key
      if ((KEYBOARD_SHORTCUTS.nextArticle as readonly string[]).includes(key)) {
        e.preventDefault()
        onNext()
      } else if ((KEYBOARD_SHORTCUTS.prevArticle as readonly string[]).includes(key)) {
        e.preventDefault()
        onPrev()
      } else if ((KEYBOARD_SHORTCUTS.openArticle as readonly string[]).includes(key)) {
        e.preventDefault()
        onOpen()
      } else if ((KEYBOARD_SHORTCUTS.toggleRead as readonly string[]).includes(key)) {
        e.preventDefault()
        onToggleRead()
      } else if ((KEYBOARD_SHORTCUTS.toggleStar as readonly string[]).includes(key)) {
        e.preventDefault()
        onToggleStar()
      } else if ((KEYBOARD_SHORTCUTS.refresh as readonly string[]).includes(key)) {
        e.preventDefault()
        onRefresh()
      } else if ((KEYBOARD_SHORTCUTS.search as readonly string[]).includes(key)) {
        e.preventDefault()
        onSearch()
      } else if ((KEYBOARD_SHORTCUTS.escape as readonly string[]).includes(key)) {
        onEscape()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, onNext, onPrev, onOpen, onToggleRead, onToggleStar, onRefresh, onSearch, onEscape])
}

/**
 * Hook for resizable panels
 */
export function useResizablePanel(
  initialWidth: number,
  constraints: { min: number; max: number },
  direction: 'left' | 'right' = 'right'
) {
  const [width, setWidth] = useState(initialWidth)
  const [isResizing, setIsResizing] = useState(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    startXRef.current = e.clientX
    startWidthRef.current = width
  }, [width])

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const delta = direction === 'right' 
        ? e.clientX - startXRef.current
        : startXRef.current - e.clientX
      const newWidth = clamp(startWidthRef.current + delta, constraints.min, constraints.max)
      setWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    
    // Prevent text selection during resize
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isResizing, constraints, direction])

  return { width, isResizing, startResize }
}

/**
 * Hook for panel dimensions with persistence
 */
export function usePanelDimensions() {
  const [dimensions, setDimensions] = useLocalStorage<PanelDimensions>(
    STORAGE_KEYS.panelDimensions,
    DEFAULT_PANEL_DIMENSIONS
  )

  const sidebar = useResizablePanel(
    dimensions.sidebarWidth,
    PANEL_CONSTRAINTS.sidebar,
    'right'
  )

  const detail = useResizablePanel(
    dimensions.detailWidth,
    PANEL_CONSTRAINTS.detail,
    'left'
  )

  // Persist dimensions when resizing stops
  useEffect(() => {
    if (!sidebar.isResizing && !detail.isResizing) {
      setDimensions({
        sidebarWidth: sidebar.width,
        detailWidth: detail.width,
      })
    }
  }, [sidebar.isResizing, detail.isResizing, sidebar.width, detail.width, setDimensions])

  return { sidebar, detail }
}

/**
 * Main hook for newsfeed page state and data
 */
export function useNewsfeedPage() {
  // Persisted preferences
  const [viewMode, setViewMode] = useLocalStorage<ViewMode>(
    STORAGE_KEYS.viewMode,
    DEFAULT_VIEW_MODE
  )
  const [showDetailPanel, setShowDetailPanel] = useLocalStorage<boolean>(
    STORAGE_KEYS.showDetailPanel,
    true
  )
  const [pageSize, setPageSize] = useLocalStorage<number>(
    STORAGE_KEYS.pageSize,
    DEFAULT_PAGE_SIZE
  )

  // Local state
  const [filters, setFilters] = useState<ArticleFilters>({})
  const [sort, setSort] = useState<SortConfig>(DEFAULT_SORT)
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchFocused, setIsSearchFocused] = useState(false)

  // API data
  const feedsQuery = useFeeds()
  const recordsQuery = useRecords({
    feed_id: filters.feedId,
    limit: pageSize,
    offset: (page - 1) * pageSize,
    is_read: filters.isRead,
    is_starred: filters.isStarred,
  })

  // Transform API data
  const feeds: DisplayFeed[] = useMemo(() => 
    (feedsQuery.data ?? []).map(transformFeed),
    [feedsQuery.data]
  )

  const articles: DisplayArticle[] = useMemo(() => {
    const records = recordsQuery.data ?? []
    const transformed = records.map(record => {
      const feed = feeds.find(f => f.id === record.feed_id)
      return transformRecord(record, feed?.name)
    })

    // Apply client-side search filter
    const filtered = filterBySearch(transformed, searchQuery)
    
    // Apply client-side sort
    return sortArticles(filtered, sort.field, sort.direction)
  }, [recordsQuery.data, feeds, searchQuery, sort])

  // Article selection
  const selection = useArticleSelection(articles)

  // Panel dimensions
  const panels = usePanelDimensions()

  // Refetch on interval
  useEffect(() => {
    const interval = setInterval(() => {
      recordsQuery.refetch()
      feedsQuery.refetch()
    }, AUTO_REFRESH_INTERVAL)

    return () => clearInterval(interval)
  }, [recordsQuery, feedsQuery])

  // Actions
  const refresh = useCallback(() => {
    recordsQuery.refetch()
    feedsQuery.refetch()
  }, [recordsQuery, feedsQuery])

  const selectFeed = useCallback((feedId: number | undefined) => {
    setFilters(prev => ({ ...prev, feedId }))
    setPage(1)
    selection.clearSelection()
  }, [selection])

  const toggleDetailPanel = useCallback(() => {
    setShowDetailPanel(!showDetailPanel)
  }, [showDetailPanel, setShowDetailPanel])

  // Keyboard navigation
  useKeyboardNavigation({
    onNext: selection.selectNext,
    onPrev: selection.selectPrevious,
    onOpen: () => {
      if (selection.selectedArticle?.link) {
        window.open(selection.selectedArticle.link, '_blank')
      }
    },
    onToggleRead: () => {
      // TODO: Implement with mutation
    },
    onToggleStar: () => {
      // TODO: Implement with mutation
    },
    onRefresh: refresh,
    onSearch: () => setIsSearchFocused(true),
    onEscape: () => {
      setIsSearchFocused(false)
      selection.clearSelection()
    },
  })

  return {
    // State
    viewMode,
    setViewMode,
    showDetailPanel,
    toggleDetailPanel,
    filters,
    setFilters,
    sort,
    setSort,
    page,
    setPage,
    pageSize,
    setPageSize,
    searchQuery,
    setSearchQuery,
    isSearchFocused,
    setIsSearchFocused,

    // Data
    feeds,
    articles,
    isLoading: feedsQuery.isLoading || recordsQuery.isLoading,
    isRefetching: feedsQuery.isRefetching || recordsQuery.isRefetching,
    error: feedsQuery.error || recordsQuery.error,

    // Selection
    ...selection,

    // Panels
    panels,

    // Actions
    refresh,
    selectFeed,
    
    // Total records (from current response)
    totalRecords: (recordsQuery.data ?? []).length,
  }
}
