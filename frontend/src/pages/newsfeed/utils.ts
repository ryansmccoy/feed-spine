/**
 * Newsfeed Page Utilities
 * 
 * Helper functions for data transformation and formatting.
 */

import { formatDistanceToNow, isAfter, subHours } from 'date-fns'
import type { Feed, FeedRecord } from '../../api'
import type { DisplayFeed, DisplayArticle, TagColorConfig } from './types'
import { 
  FEED_ICON_PATTERNS, 
  DEFAULT_FEED_ICON, 
  TAG_COLORS, 
  DEFAULT_TAG_COLORS,
  NEW_ARTICLE_THRESHOLD,
} from './constants'

/**
 * Get appropriate icon for a feed based on its name
 */
export function getFeedIcon(feedName: string): string {
  const match = FEED_ICON_PATTERNS.find(({ pattern }) => pattern.test(feedName))
  return match?.icon ?? DEFAULT_FEED_ICON
}

/**
 * Transform API Feed to display format
 */
export function transformFeed(feed: Feed): DisplayFeed {
  return {
    id: feed.id,
    name: feed.name,
    url: feed.url,
    count: 0, // Populated separately from stats
    icon: getFeedIcon(feed.name),
    isActive: feed.enabled ?? true,
    lastCollected: feed.last_poll,
  }
}

/**
 * Extract source type from feed/record data
 */
export function getSourceType(record: FeedRecord): DisplayArticle['sourceType'] {
  if (record.form_type) return 'sec'
  const link = record.link?.toLowerCase() ?? ''
  if (link.includes('rss') || link.includes('feed')) return 'rss'
  if (link.includes('api')) return 'api'
  return 'unknown'
}

/**
 * Extract tags from a record
 */
export function extractTags(record: FeedRecord): string[] {
  const tags: string[] = []
  
  if (record.form_type) {
    tags.push(record.form_type)
  }
  
  if (record.ticker) {
    tags.push(record.ticker)
  }
  
  // Add any custom tags from metadata
  if (record.metadata?.tags && Array.isArray(record.metadata.tags)) {
    tags.push(...record.metadata.tags)
  }
  
  return tags.filter(Boolean)
}

/**
 * Format relative time in a compact format
 */
export function formatRelativeTime(date: Date): string {
  return formatDistanceToNow(date, { addSuffix: false })
    .replace('about ', '')
    .replace(' ago', '')
    .replace('less than a minute', '<1m')
    .replace(/(\d+) seconds?/, '$1s')
    .replace(/(\d+) minutes?/, '$1m')
    .replace(/(\d+) hours?/, '$1h')
    .replace(/(\d+) days?/, '$1d')
    .replace(/(\d+) weeks?/, '$1w')
    .replace(/(\d+) months?/, '$1mo')
}

/**
 * Check if an article is "new" (within threshold)
 */
export function isNewArticle(publishedAt: Date): boolean {
  const threshold = subHours(new Date(), NEW_ARTICLE_THRESHOLD / (60 * 60 * 1000))
  return isAfter(publishedAt, threshold)
}

/**
 * Transform API Record to display format
 */
export function transformRecord(record: FeedRecord, feedName?: string): DisplayArticle {
  const publishedAt = record.published_at 
    ? new Date(record.published_at) 
    : new Date(record.first_seen_at)
  const firstSeenAt = new Date(record.first_seen_at)
  
  return {
    id: record.id,
    feedId: record.feed_id,
    feedName: feedName ?? record.ticker ?? 'Feed',
    feedIcon: getFeedIcon(feedName ?? record.ticker ?? ''),
    title: record.title,
    summary: record.description,
    content: record.description,
    link: record.link,
    author: record.author,
    publishedAt,
    firstSeenAt,
    tags: extractTags(record),
    isRead: record.is_read ?? false,
    isStarred: record.is_starred ?? false,
    isNew: isNewArticle(publishedAt),
    relativeTime: formatRelativeTime(publishedAt),
    sourceType: getSourceType(record),
    metadata: record.metadata,
  }
}

/**
 * Get tag color classes
 */
export function getTagColorClasses(tag: string): string {
  const colors = TAG_COLORS[tag] ?? DEFAULT_TAG_COLORS
  return `${colors.bg} ${colors.text} ${colors.darkBg} ${colors.darkText}`
}

/**
 * Generate a unique key for an article
 */
export function getArticleKey(article: DisplayArticle): string {
  return `article-${article.id}`
}

/**
 * Filter articles by search query
 */
export function filterBySearch(articles: DisplayArticle[], query: string): DisplayArticle[] {
  if (!query.trim()) return articles
  
  const lowerQuery = query.toLowerCase()
  return articles.filter(article => 
    article.title.toLowerCase().includes(lowerQuery) ||
    article.summary?.toLowerCase().includes(lowerQuery) ||
    article.feedName.toLowerCase().includes(lowerQuery) ||
    article.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
  )
}

/**
 * Sort articles by field
 */
export function sortArticles(
  articles: DisplayArticle[], 
  field: 'publishedAt' | 'firstSeenAt' | 'title' | 'feedName',
  direction: 'asc' | 'desc'
): DisplayArticle[] {
  return [...articles].sort((a, b) => {
    let comparison = 0
    
    switch (field) {
      case 'publishedAt':
        comparison = a.publishedAt.getTime() - b.publishedAt.getTime()
        break
      case 'firstSeenAt':
        comparison = a.firstSeenAt.getTime() - b.firstSeenAt.getTime()
        break
      case 'title':
        comparison = a.title.localeCompare(b.title)
        break
      case 'feedName':
        comparison = a.feedName.localeCompare(b.feedName)
        break
    }
    
    return direction === 'desc' ? -comparison : comparison
  })
}

/**
 * Truncate text to a maximum length
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}

/**
 * Clamp a number between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/**
 * Debounce a function
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T, 
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}
