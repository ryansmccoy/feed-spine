import { useState } from 'react'
import { Plus, RefreshCw, Trash2, Power, PowerOff } from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { useFeeds, useCreateFeed, useUpdateFeed, useDeleteFeed, useCollectFeed } from '@/api/hooks'
import { Feed } from '@/api'

export default function FeedsPage() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState({ name: '', url: '', enabled: true, poll_interval: 300 })

  const { data: feeds = [], isLoading } = useFeeds()
  const createFeed = useCreateFeed()
  const updateFeed = useUpdateFeed()
  const deleteFeed = useDeleteFeed()
  const collectFeed = useCollectFeed()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await createFeed.mutateAsync(formData)
    setFormData({ name: '', url: '', enabled: true, poll_interval: 300 })
    setShowAddForm(false)
  }

  const handleToggleEnabled = async (feed: Feed) => {
    await updateFeed.mutateAsync({
      id: feed.id,
      feed: { enabled: !feed.enabled },
    })
  }

  const handleCollect = async (feedId: number) => {
    await collectFeed.mutateAsync(feedId)
  }

  const handleDelete = async (feedId: number) => {
    if (confirm('Are you sure you want to delete this feed?')) {
      await deleteFeed.mutateAsync(feedId)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 text-gray-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Manage Feeds
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {feeds.length} feeds configured
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Feed
        </button>
      </div>

      {/* Add Feed Form */}
      {showAddForm && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Add New Feed
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Feed Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="My RSS Feed"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Feed URL
              </label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                required
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="https://example.com/feed.xml"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Poll Interval (seconds)
              </label>
              <input
                type="number"
                value={formData.poll_interval}
                onChange={(e) => setFormData({ ...formData, poll_interval: Number(e.target.value) })}
                required
                min="60"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="enabled"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="rounded"
              />
              <label htmlFor="enabled" className="text-sm text-gray-700 dark:text-gray-300">
                Enable immediately
              </label>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createFeed.isPending}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {createFeed.isPending ? 'Creating...' : 'Create Feed'}
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Feeds List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {feeds.map((feed) => (
          <div
            key={feed.id}
            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                  {feed.name}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-1">
                  {feed.url}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleToggleEnabled(feed)}
                  className={clsx(
                    'p-1.5 rounded-lg transition-colors',
                    feed.enabled
                      ? 'text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20'
                      : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                  )}
                  title={feed.enabled ? 'Disable' : 'Enable'}
                >
                  {feed.enabled ? <Power className="h-4 w-4" /> : <PowerOff className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => handleDelete(feed.id)}
                  className="p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-2 text-xs text-gray-500 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>Poll Interval:</span>
                <span className="font-medium">{feed.poll_interval}s</span>
              </div>
              {feed.last_poll && (
                <div className="flex items-center justify-between">
                  <span>Last Polled:</span>
                  <span className="font-medium">
                    {formatDistanceToNow(new Date(feed.last_poll), { addSuffix: true })}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span>Errors:</span>
                <span className={clsx('font-medium', feed.error_count > 0 && 'text-red-600')}>
                  {feed.error_count}
                </span>
              </div>
            </div>

            <button
              onClick={() => handleCollect(feed.id)}
              disabled={collectFeed.isPending || !feed.enabled}
              className="w-full mt-4 flex items-center justify-center gap-2 px-3 py-2 bg-primary-50 hover:bg-primary-100 dark:bg-primary-900/20 dark:hover:bg-primary-900/30 text-primary-600 dark:text-primary-400 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className="h-4 w-4" />
              Collect Now
            </button>
          </div>
        ))}
      </div>

      {feeds.length === 0 && !showAddForm && (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          <Plus className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No feeds configured yet</p>
          <button
            onClick={() => setShowAddForm(true)}
            className="mt-4 text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium text-sm"
          >
            Add your first feed
          </button>
        </div>
      )}
    </div>
  )
}
