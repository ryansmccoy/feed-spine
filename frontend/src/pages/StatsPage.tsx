import { BarChart2, TrendingUp, Star, Eye, Rss } from 'lucide-react'
import { useGlobalStats, useFeedStats } from '@/api/hooks'

export default function StatsPage() {
  const { data: globalStats, isLoading: loadingGlobal } = useGlobalStats()
  const { data: feedStats = [], isLoading: loadingFeeds } = useFeedStats()

  if (loadingGlobal || loadingFeeds) {
    return (
      <div className="flex items-center justify-center h-64">
        <BarChart2 className="h-8 w-8 text-gray-400 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Statistics</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Overview of your feed activity
        </p>
      </div>

      {/* Global Stats */}
      {globalStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Feeds"
            value={globalStats.total_feeds}
            icon={Rss}
            color="bg-blue-500"
            subtitle={`${globalStats.feeds_enabled} enabled`}
          />
          <StatCard
            title="Total Records"
            value={globalStats.total_records}
            icon={BarChart2}
            color="bg-purple-500"
          />
          <StatCard
            title="Unread"
            value={globalStats.total_unread}
            icon={Eye}
            color="bg-orange-500"
          />
          <StatCard
            title="Starred"
            value={globalStats.total_starred}
            icon={Star}
            color="bg-yellow-500"
          />
        </div>
      )}

      {/* Per-Feed Stats */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-white">Feed Statistics</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Feed ID
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Total
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Unread
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Starred
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Unread %
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {feedStats.map((stat) => {
                const unreadPercent = stat.total_records > 0 
                  ? Math.round((stat.unread_count / stat.total_records) * 100)
                  : 0

                return (
                  <tr key={stat.feed_id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <Rss className="h-4 w-4 text-primary-600 dark:text-primary-400 mr-2" />
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          Feed {stat.feed_id}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900 dark:text-white">
                      {stat.total_records.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <span className="text-orange-600 dark:text-orange-400 font-medium">
                        {stat.unread_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                        {stat.starred_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500 dark:text-gray-400">
                      {unreadPercent}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {feedStats.length === 0 && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <BarChart2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No feed statistics available</p>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: number
  icon: React.ElementType
  color: string
  subtitle?: string
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
      <div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">{title}</p>
        <p className="text-3xl font-bold text-gray-900 dark:text-white">
          {value.toLocaleString()}
        </p>
        {subtitle && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
