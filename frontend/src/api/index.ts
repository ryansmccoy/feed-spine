import axios from 'axios'

// Create axios instance with base URL from environment
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// Types
export interface Feed {
  id: number
  name: string
  url: string
  enabled: boolean
  poll_interval: number
  last_poll?: string
  error_count: number
  created_at: string
  updated_at: string
  feed_type?: string
  metadata?: Record<string, unknown>
}

export interface FeedRecord {
  id: number
  feed_id: number
  guid: string
  title: string
  link: string
  description?: string
  published_at?: string
  author?: string
  first_seen_at: string
  is_read?: boolean
  is_starred?: boolean
  metadata?: Record<string, unknown>
  // Computed fields from metadata
  form_type?: string
  company_name?: string
  ticker?: string
  accession_number?: string
}

export interface FeedStats {
  feed_id: number
  total_records: number
  unread_count: number
  starred_count: number
  last_updated?: string
}

export interface GlobalStats {
  total_feeds: number
  total_records: number
  total_unread: number
  total_starred: number
  feeds_enabled: number
  feeds_disabled: number
}

export interface HealthStatus {
  status: string
  timestamp?: string
}

export interface StorageStatus {
  backend_type: string
  connection_status: string
  total_records: number
  database_file?: string
}

// API functions
export const feedsApi = {
  // List all feeds
  list: async (): Promise<Feed[]> => {
    const response = await api.get('/feeds')
    return response.data
  },

  // Get a single feed
  get: async (id: number): Promise<Feed> => {
    const response = await api.get(`/feeds/${id}`)
    return response.data
  },

  // Create a new feed
  create: async (feed: Partial<Feed>): Promise<Feed> => {
    const response = await api.post('/feeds', feed)
    return response.data
  },

  // Update a feed
  update: async (id: number, feed: Partial<Feed>): Promise<Feed> => {
    const response = await api.patch(`/feeds/${id}`, feed)
    return response.data
  },

  // Delete a feed
  delete: async (id: number): Promise<void> => {
    await api.delete(`/feeds/${id}`)
  },

  // Trigger feed collection
  collect: async (id: number): Promise<void> => {
    await api.post(`/feeds/${id}/collect`)
  },
}

export const recordsApi = {
  // List records with optional filters
  list: async (params?: {
    feed_id?: number
    is_read?: boolean
    is_starred?: boolean
    search?: string
    limit?: number
    offset?: number
  }): Promise<FeedRecord[]> => {
    const response = await api.get('/records', { params })
    return response.data
  },

  // Get a single record
  get: async (id: number): Promise<FeedRecord> => {
    const response = await api.get(`/records/${id}`)
    return response.data
  },

  // Update record (mark read/starred)
  update: async (id: number, updates: Partial<Pick<FeedRecord, 'is_read' | 'is_starred'>>): Promise<FeedRecord> => {
    const response = await api.patch(`/records/${id}`, updates)
    return response.data
  },

  // Mark all as read
  markAllRead: async (feedId?: number): Promise<void> => {
    await api.post('/records/mark-all-read', { feed_id: feedId })
  },

  // Search records
  search: async (query: string): Promise<FeedRecord[]> => {
    const response = await api.get('/records/search', { params: { q: query } })
    return response.data
  },
}

export const statsApi = {
  // Get global statistics
  global: async (): Promise<GlobalStats> => {
    const response = await api.get('/stats')
    return response.data
  },

  // Get per-feed statistics
  feeds: async (): Promise<FeedStats[]> => {
    const response = await api.get('/stats/feeds')
    return response.data
  },

  // Get stats for a specific feed
  feed: async (feedId: number): Promise<FeedStats> => {
    const response = await api.get(`/stats/feeds/${feedId}`)
    return response.data
  },
}

export const systemApi = {
  // Health check
  health: async (): Promise<HealthStatus> => {
    const response = await api.get('/health')
    return response.data
  },

  // Storage status
  storage: async (): Promise<StorageStatus> => {
    const response = await api.get('/storage/status')
    return response.data
  },
}

// Helper to extract metadata fields
export function enrichRecord(record: FeedRecord): FeedRecord {
  if (record.metadata) {
    return {
      ...record,
      form_type: record.metadata.form_type as string | undefined,
      company_name: record.metadata.company_name as string | undefined,
      ticker: record.metadata.ticker as string | undefined,
      accession_number: record.metadata.accession_number as string | undefined,
    }
  }
  return record
}
