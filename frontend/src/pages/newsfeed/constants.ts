/**
 * Newsfeed Page Constants
 * 
 * Configuration values, defaults, and constant data for the newsfeed feature.
 */

import type { ViewModeOption, TagColorConfig, PanelDimensions, SortConfig, ViewMode } from './types'

/**
 * Default panel dimensions
 */
export const DEFAULT_PANEL_DIMENSIONS: PanelDimensions = {
  sidebarWidth: 240,
  detailWidth: 400,
}

/**
 * Panel size constraints
 */
export const PANEL_CONSTRAINTS = {
  sidebar: { min: 180, max: 400 },
  detail: { min: 300, max: 600 },
} as const

/**
 * Available view modes with metadata
 */
export const VIEW_MODES: ViewModeOption[] = [
  { id: 'condensed', label: 'Condensed', icon: 'Rows3', description: 'Tight rows, maximum density' },
  { id: 'comfortable', label: 'Comfortable', icon: 'LayoutList', description: 'More spacing, easier reading' },
  { id: 'headlines', label: 'Headlines', icon: 'List', description: 'Title and time only' },
  { id: 'cards', label: 'Cards', icon: 'LayoutGrid', description: 'Cards in a grid layout' },
  { id: 'table', label: 'Table', icon: 'Table', description: 'Full table with all columns' },
]

/**
 * Default view mode
 */
export const DEFAULT_VIEW_MODE: ViewMode = 'comfortable'

/**
 * Default sort configuration
 */
export const DEFAULT_SORT: SortConfig = {
  field: 'publishedAt',
  direction: 'desc',
}

/**
 * Page size options
 */
export const PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const

/**
 * Default page size
 */
export const DEFAULT_PAGE_SIZE = 50

/**
 * Auto-refresh interval in milliseconds
 */
export const AUTO_REFRESH_INTERVAL = 30_000 // 30 seconds

/**
 * "New" article threshold in milliseconds
 */
export const NEW_ARTICLE_THRESHOLD = 60 * 60 * 1000 // 1 hour

/**
 * Tag color configuration
 * Maps tag names to Tailwind color classes
 */
export const TAG_COLORS: TagColorConfig = {
  // SEC Form Types
  '10-K': { bg: 'bg-blue-100', text: 'text-blue-700', darkBg: 'dark:bg-blue-900/30', darkText: 'dark:text-blue-400' },
  '10-Q': { bg: 'bg-green-100', text: 'text-green-700', darkBg: 'dark:bg-green-900/30', darkText: 'dark:text-green-400' },
  '8-K': { bg: 'bg-orange-100', text: 'text-orange-700', darkBg: 'dark:bg-orange-900/30', darkText: 'dark:text-orange-400' },
  '4': { bg: 'bg-purple-100', text: 'text-purple-700', darkBg: 'dark:bg-purple-900/30', darkText: 'dark:text-purple-400' },
  'S-1': { bg: 'bg-red-100', text: 'text-red-700', darkBg: 'dark:bg-red-900/30', darkText: 'dark:text-red-400' },
  'DEF 14A': { bg: 'bg-indigo-100', text: 'text-indigo-700', darkBg: 'dark:bg-indigo-900/30', darkText: 'dark:text-indigo-400' },
  
  // Content Types
  'Tech': { bg: 'bg-sky-100', text: 'text-sky-700', darkBg: 'dark:bg-sky-900/30', darkText: 'dark:text-sky-400' },
  'AI/ML': { bg: 'bg-violet-100', text: 'text-violet-700', darkBg: 'dark:bg-violet-900/30', darkText: 'dark:text-violet-400' },
  'Earnings': { bg: 'bg-emerald-100', text: 'text-emerald-700', darkBg: 'dark:bg-emerald-900/30', darkText: 'dark:text-emerald-400' },
  'Breaking': { bg: 'bg-red-100', text: 'text-red-700', darkBg: 'dark:bg-red-900/30', darkText: 'dark:text-red-400' },
  'Analysis': { bg: 'bg-amber-100', text: 'text-amber-700', darkBg: 'dark:bg-amber-900/30', darkText: 'dark:text-amber-400' },
  
  // Source Types  
  'SEC': { bg: 'bg-amber-100', text: 'text-amber-700', darkBg: 'dark:bg-amber-900/30', darkText: 'dark:text-amber-400' },
  'RSS': { bg: 'bg-gray-100', text: 'text-gray-700', darkBg: 'dark:bg-gray-800', darkText: 'dark:text-gray-400' },
  'API': { bg: 'bg-cyan-100', text: 'text-cyan-700', darkBg: 'dark:bg-cyan-900/30', darkText: 'dark:text-cyan-400' },
}

/**
 * Default tag colors when no specific mapping exists
 */
export const DEFAULT_TAG_COLORS = {
  bg: 'bg-gray-100',
  text: 'text-gray-600',
  darkBg: 'dark:bg-gray-800',
  darkText: 'dark:text-gray-400',
}

/**
 * Feed icon mapping based on feed name patterns
 */
export const FEED_ICON_PATTERNS: Array<{ pattern: RegExp; icon: string }> = [
  { pattern: /sec|edgar|filing/i, icon: '📋' },
  { pattern: /news|reuters|bloomberg|ap\b/i, icon: '📰' },
  { pattern: /hack|tech|verge|ars/i, icon: '🟠' },
  { pattern: /crypto|bitcoin|eth/i, icon: '₿' },
  { pattern: /finance|stock|market/i, icon: '📈' },
  { pattern: /rss|feed/i, icon: '📡' },
]

/**
 * Default feed icon
 */
export const DEFAULT_FEED_ICON = '📡'

/**
 * Keyboard shortcuts
 */
export const KEYBOARD_SHORTCUTS = {
  nextArticle: ['j', 'ArrowDown'],
  prevArticle: ['k', 'ArrowUp'],
  openArticle: ['Enter', 'o'],
  toggleRead: ['m'],
  toggleStar: ['s'],
  refresh: ['r'],
  search: ['/'],
  escape: ['Escape'],
} as const

/**
 * Local storage keys
 */
export const STORAGE_KEYS = {
  viewMode: 'feedspine.newsfeed.viewMode',
  panelDimensions: 'feedspine.newsfeed.panelDimensions',
  showDetailPanel: 'feedspine.newsfeed.showDetailPanel',
  pageSize: 'feedspine.newsfeed.pageSize',
} as const
