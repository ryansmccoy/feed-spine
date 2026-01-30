/**
 * EarningsPage - Dual-panel layout for earnings monitoring
 * 
 * Left panel: News feed with earnings-related items (alerts, filings, news)
 * Right panel: Bloomberg-style earnings table with live data
 * 
 * Uses capture-spine's ResizablePanel for adjustable widths.
 * 
 * MOCKUP - This is a design specification, not production code.
 */

import { useQuery } from '@tanstack/react-query';
import { Bell, Calendar, ChevronDown, Filter, Settings } from 'lucide-react';
import { useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { ResizablePanel } from '../../components/ResizablePanel';
import { EarningsTable, EarningsRelease, exportToCSV } from './EarningsTable';
import { NewsFeedPanel } from './NewsFeedPanel';

// =============================================================================
// Types
// =============================================================================

type DateRange = 'today' | 'week' | 'month' | 'custom';
type ViewMode = 'all' | 'released' | 'upcoming';

// =============================================================================
// Mock API (would be replaced with real readerApi calls)
// =============================================================================

async function fetchEarningsReleases(
    dateRange: DateRange,
    viewMode: ViewMode
): Promise<EarningsRelease[]> {
    // In production: readerApi.getTimeline(undefined, 100, 'published', [], [], false, [], ['earnings'])
    // Returns earnings records from capture-spine database
    
    // Mock delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Mock data (imported from EarningsTable)
    return import('./EarningsTable').then(m => m.sampleEarningsData);
}

// =============================================================================
// Main Page Component
// =============================================================================

export function EarningsPage() {
    const { colors } = useTheme();
    
    // Filter state
    const [dateRange, setDateRange] = useState<DateRange>('today');
    const [viewMode, setViewMode] = useState<ViewMode>('all');
    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
    
    // Fetch earnings data
    const { data: earnings, isLoading, refetch } = useQuery({
        queryKey: ['earnings', dateRange, viewMode],
        queryFn: () => fetchEarningsReleases(dateRange, viewMode),
        refetchInterval: 30000, // 30 seconds - earnings data updates frequently
    });
    
    // Handle ticker click - shows related news in left panel
    const handleTickerClick = (ticker: string) => {
        setSelectedTicker(ticker);
    };
    
    // Handle row click - shows detail view
    const handleRowClick = (release: EarningsRelease) => {
        console.log('Row clicked:', release.ticker);
        // Could open detail modal or navigate to company page
    };

    return (
        <div className={`h-screen flex flex-col ${colors.bgPrimary}`}>
            {/* Page Header */}
            <header className={`flex-shrink-0 border-b ${colors.borderPrimary} ${colors.bgSecondary}`}>
                <div className="px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Calendar className="w-6 h-6 text-blue-500" />
                        <div>
                            <h1 className={`text-xl font-semibold ${colors.textPrimary}`}>
                                Earnings Monitor
                            </h1>
                            <p className={`text-sm ${colors.textMuted}`}>
                                Real-time earnings releases and estimates
                            </p>
                        </div>
                    </div>
                    
                    {/* Controls */}
                    <div className="flex items-center gap-3">
                        {/* Date Range Selector */}
                        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                            {(['today', 'week', 'month'] as DateRange[]).map(range => (
                                <button
                                    key={range}
                                    onClick={() => setDateRange(range)}
                                    className={`
                                        px-3 py-1 text-sm rounded-md transition-colors
                                        ${dateRange === range 
                                            ? 'bg-white dark:bg-gray-600 shadow text-blue-600 dark:text-blue-400' 
                                            : 'text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                                        }
                                    `}
                                >
                                    {range.charAt(0).toUpperCase() + range.slice(1)}
                                </button>
                            ))}
                        </div>
                        
                        {/* View Mode */}
                        <select
                            value={viewMode}
                            onChange={(e) => setViewMode(e.target.value as ViewMode)}
                            className={`px-3 py-1.5 text-sm rounded-lg border ${colors.borderPrimary} ${colors.bgPrimary}`}
                        >
                            <option value="all">All Releases</option>
                            <option value="released">Released Only</option>
                            <option value="upcoming">Upcoming Only</option>
                        </select>
                        
                        {/* Notifications */}
                        <button className={`p-2 rounded-lg ${colors.sidebarHover} relative`}>
                            <Bell className="w-5 h-5" />
                            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                                3
                            </span>
                        </button>
                        
                        {/* Settings */}
                        <button className={`p-2 rounded-lg ${colors.sidebarHover}`}>
                            <Settings className="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </header>

            {/* Dual Panel Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left Panel: News Feed */}
                <ResizablePanel
                    storageKey="earnings-news-panel"
                    defaultWidth={380}
                    minWidth={280}
                    maxWidth={550}
                    resizeFrom="right"
                    className={`border-r ${colors.borderPrimary}`}
                >
                    <NewsFeedPanel
                        title="Earnings News"
                        filters={{
                            recordTypes: ['earnings', 'sec-8k', 'news'],
                            ticker: selectedTicker,
                        }}
                        onClearFilter={() => setSelectedTicker(null)}
                        compact={true}
                    />
                </ResizablePanel>

                {/* Right Panel: Earnings Table */}
                <div className="flex-1 overflow-hidden">
                    <EarningsTable
                        releases={earnings ?? []}
                        isLoading={isLoading}
                        filter={viewMode === 'all' ? 'all' : viewMode === 'released' ? 'released' : 'scheduled'}
                        onTickerClick={handleTickerClick}
                        onRowClick={handleRowClick}
                        onRefresh={() => refetch()}
                        onExport={(data) => exportToCSV(data)}
                        compact={false}
                    />
                </div>
            </div>

            {/* Status Bar */}
            <footer className={`flex-shrink-0 border-t ${colors.borderPrimary} ${colors.bgSecondary}`}>
                <div className="px-4 py-1.5 flex items-center justify-between text-xs">
                    <div className={colors.textMuted}>
                        Last updated: {new Date().toLocaleTimeString()} • Auto-refresh: 30s
                    </div>
                    <div className={colors.textMuted}>
                        {earnings?.filter(e => e.status === 'released').length ?? 0} released • 
                        {earnings?.filter(e => e.status === 'scheduled').length ?? 0} upcoming
                    </div>
                </div>
            </footer>
        </div>
    );
}

// =============================================================================
// News Feed Panel (simplified version for mockup)
// =============================================================================

interface NewsFeedPanelProps {
    title: string;
    filters: {
        recordTypes: string[];
        ticker: string | null;
    };
    onClearFilter: () => void;
    compact?: boolean;
}

function NewsFeedPanel({ title, filters, onClearFilter, compact }: NewsFeedPanelProps) {
    const { colors } = useTheme();
    
    // Mock news items
    const newsItems = [
        {
            id: '1',
            type: 'alert',
            icon: '🔔',
            title: 'MSFT Beat Q3 Estimates by 8.2%',
            subtitle: 'EPS $2.45 vs $2.26 est',
            time: '2 min ago',
            isNew: true,
        },
        {
            id: '2',
            type: 'news',
            icon: '📰',
            title: 'Apple Reports Mixed Quarter',
            subtitle: 'iPhone sales below expectations',
            time: '5 min ago',
            isNew: true,
        },
        {
            id: '3',
            type: 'filing',
            icon: '📄',
            title: '8-K: GOOGL Earnings Release',
            subtitle: 'Form 8-K filed with SEC',
            time: '8 min ago',
            isNew: false,
        },
        {
            id: '4',
            type: 'alert',
            icon: '⚠️',
            title: 'AMZN Strong Beat +18.1%',
            subtitle: 'Best quarter in 2 years',
            time: '12 min ago',
            isNew: false,
        },
    ];
    
    const filteredItems = filters.ticker 
        ? newsItems.filter(item => item.title.includes(filters.ticker!))
        : newsItems;

    return (
        <div className="h-full flex flex-col">
            {/* Panel Header */}
            <div className={`flex-shrink-0 px-3 py-2 border-b ${colors.borderPrimary}`}>
                <div className="flex items-center justify-between">
                    <h3 className={`font-semibold ${colors.textPrimary}`}>{title}</h3>
                    <button className={`p-1 rounded ${colors.sidebarHover}`}>
                        <Filter className="w-4 h-4" />
                    </button>
                </div>
                
                {/* Active filter badge */}
                {filters.ticker && (
                    <div className="mt-2 flex items-center gap-1">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs rounded-full">
                            {filters.ticker}
                            <button onClick={onClearFilter} className="hover:bg-blue-200 dark:hover:bg-blue-800 rounded-full">
                                ×
                            </button>
                        </span>
                    </div>
                )}
            </div>
            
            {/* News Items */}
            <div className="flex-1 overflow-auto">
                {filteredItems.map(item => (
                    <div
                        key={item.id}
                        className={`
                            px-3 py-2 border-b ${colors.borderSecondary}
                            hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer
                            ${item.isNew ? 'bg-blue-50/50 dark:bg-blue-900/20' : ''}
                        `}
                    >
                        <div className="flex items-start gap-2">
                            <span className="text-lg">{item.icon}</span>
                            <div className="flex-1 min-w-0">
                                <p className={`text-sm font-medium ${colors.textPrimary} truncate`}>
                                    {item.title}
                                </p>
                                <p className={`text-xs ${colors.textMuted} truncate`}>
                                    {item.subtitle}
                                </p>
                                <p className={`text-xs ${colors.textMuted} mt-1`}>
                                    {item.time}
                                </p>
                            </div>
                            {item.isNew && (
                                <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1"></span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// =============================================================================
// Export
// =============================================================================

export default EarningsPage;
