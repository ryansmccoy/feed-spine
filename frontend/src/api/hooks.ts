import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  feedsApi, 
  recordsApi, 
  statsApi,
  systemApi,
  Feed, 
  FeedRecord, 
  FeedStats,
  GlobalStats,
  HealthStatus,
  StorageStatus,
} from './index'

// Query keys
export const queryKeys = {
  feeds: ['feeds'] as const,
  feed: (id: number) => ['feeds', id] as const,
  records: (params?: Record<string, unknown>) => ['records', params] as const,
  record: (id: number) => ['records', id] as const,
  stats: {
    global: ['stats', 'global'] as const,
    feeds: ['stats', 'feeds'] as const,
    feed: (id: number) => ['stats', 'feeds', id] as const,
  },
  system: {
    health: ['system', 'health'] as const,
    storage: ['system', 'storage'] as const,
  },
}

// Feed hooks
export function useFeeds() {
  return useQuery({
    queryKey: queryKeys.feeds,
    queryFn: feedsApi.list,
    refetchInterval: 30000, // Refetch every 30 seconds
  })
}

export function useFeed(id: number) {
  return useQuery({
    queryKey: queryKeys.feed(id),
    queryFn: () => feedsApi.get(id),
    enabled: !!id,
  })
}

export function useCreateFeed() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (feed: Partial<Feed>) => feedsApi.create(feed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.feeds })
    },
  })
}

export function useUpdateFeed() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ id, feed }: { id: number; feed: Partial<Feed> }) => 
      feedsApi.update(id, feed),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds })
      queryClient.invalidateQueries({ queryKey: queryKeys.feed(id) })
    },
  })
}

export function useDeleteFeed() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (id: number) => feedsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.feeds })
    },
  })
}

export function useCollectFeed() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (id: number) => feedsApi.collect(id),
    onSuccess: () => {
      // Invalidate records since they may have changed
      queryClient.invalidateQueries({ queryKey: ['records'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.feeds })
    },
  })
}

// Record hooks
export function useRecords(params?: {
  feed_id?: number
  is_read?: boolean
  is_starred?: boolean
  search?: string
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: queryKeys.records(params),
    queryFn: () => recordsApi.list(params),
    refetchInterval: 10000, // Refetch every 10 seconds
  })
}

export function useRecord(id: number) {
  return useQuery({
    queryKey: queryKeys.record(id),
    queryFn: () => recordsApi.get(id),
    enabled: !!id,
  })
}

export function useUpdateRecord() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ id, updates }: { 
      id: number
      updates: Partial<Pick<FeedRecord, 'is_read' | 'is_starred'>>
    }) => recordsApi.update(id, updates),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['records'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.record(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.feeds })
    },
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (feedId?: number) => recordsApi.markAllRead(feedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.feeds })
    },
  })
}

export function useSearchRecords(query: string) {
  return useQuery({
    queryKey: queryKeys.records({ search: query }),
    queryFn: () => recordsApi.search(query),
    enabled: query.length > 0,
  })
}

// Stats hooks
export function useGlobalStats() {
  return useQuery({
    queryKey: queryKeys.stats.global,
    queryFn: statsApi.global,
    refetchInterval: 30000,
  })
}

export function useFeedStats() {
  return useQuery({
    queryKey: queryKeys.stats.feeds,
    queryFn: statsApi.feeds,
    refetchInterval: 30000,
  })
}

export function useFeedStat(feedId: number) {
  return useQuery({
    queryKey: queryKeys.stats.feed(feedId),
    queryFn: () => statsApi.feed(feedId),
    enabled: !!feedId,
    refetchInterval: 30000,
  })
}

// System hooks
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.system.health,
    queryFn: systemApi.health,
    refetchInterval: 60000, // Refetch every minute
  })
}

export function useStorageStatus() {
  return useQuery({
    queryKey: queryKeys.system.storage,
    queryFn: systemApi.storage,
    refetchInterval: 60000,
  })
}
