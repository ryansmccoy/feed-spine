/**
 * EarningsTable - Bloomberg-style earnings release table
 * 
 * Displays earnings releases in a compact, data-dense format matching
 * institutional trading terminal aesthetics. Features:
 * - Color-coded surprise percentages (green=beat, red=miss)
 * - Sortable columns
 * - Compact/full view modes
 * - Export to CSV
 * 
 * MOCKUP - This is a design specification, not production code.
 */

import { ArrowDown, ArrowUp, Download, Filter, RefreshCw, Settings } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

// =============================================================================
// Types matching the Excel screenshot columns
// =============================================================================

export interface EarningsRelease {
    record_id: string;
    ticker: string;
    time: string;                    // "8:00 AM", "AMC", "BMO"
    published_at: string;            // ISO timestamp
    
    // Market data
    market_cap_b: number;            // Billions
    industry_group: string;          // "Software", "Hardware", etc.
    
    // EPS data
    eps_actual: number;
    eps_estimate: number;
    eps_surprise_pct: number;
    eps_yoy_pct: number;
    
    // Revenue data
    revenue_actual_b: number;        // Billions
    revenue_estimate_b: number;
    revenue_surprise_pct: number;
    revenue_yoy_pct: number;
    
    // Valuation metrics
    pe_trailing: number;             // P/E (Trailing 12 Months)
    pe_f1: number;                   // P/E (Forward Year 1)
    pe_f2: number;                   // P/E (Forward Year 2)
    peg_ratio: number;
    
    // Status
    status: 'released' | 'scheduled';
}

// =============================================================================
// Color utilities matching your Excel macro styling
// =============================================================================

/**
 * Get background color class based on surprise percentage.
 * Matches the green/red gradient from your Excel screenshot.
 */
export function getSurpriseColorClass(surprisePct: number): string {
    if (surprisePct >= 15) return 'bg-green-600 text-white';      // Strong beat
    if (surprisePct >= 10) return 'bg-green-500 text-white';      // Beat
    if (surprisePct >= 5)  return 'bg-green-400 text-white';      // Moderate beat
    if (surprisePct >= 0)  return 'bg-green-100 text-green-800';  // Slight beat
    if (surprisePct >= -5) return 'bg-red-100 text-red-800';      // Slight miss
    if (surprisePct >= -10) return 'bg-red-400 text-white';       // Miss
    return 'bg-red-600 text-white';                                // Strong miss
}

/**
 * Get text color for inline surprise display (no background).
 */
export function getSurpriseTextClass(surprisePct: number): string {
    if (surprisePct >= 0) return 'text-green-600 dark:text-green-400';
    return 'text-red-600 dark:text-red-400';
}

/**
 * Format market cap with appropriate suffix.
 */
export function formatMarketCap(capB: number): string {
    if (capB >= 1000) return `${(capB / 1000).toFixed(1)}T`;
    if (capB >= 1) return `${capB.toFixed(0)}B`;
    return `${(capB * 1000).toFixed(0)}M`;
}

/**
 * Format surprise percentage with sign.
 */
export function formatSurprise(pct: number): string {
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(1)}%`;
}

// =============================================================================
// Column definitions
// =============================================================================

interface Column {
    key: keyof EarningsRelease | 'eps_combined' | 'rev_combined' | 'pe_combined';
    label: string;
    shortLabel?: string;
    width: string;
    align: 'left' | 'right' | 'center';
    sortable: boolean;
    render: (release: EarningsRelease, compact: boolean) => React.ReactNode;
}

const columns: Column[] = [
    {
        key: 'time',
        label: 'TIME',
        width: '70px',
        align: 'left',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{r.time}</span>,
    },
    {
        key: 'ticker',
        label: 'TICKER',
        width: '80px',
        align: 'left',
        sortable: true,
        render: (r) => (
            <span className="font-semibold text-blue-600 dark:text-blue-400 cursor-pointer hover:underline">
                {r.ticker}
            </span>
        ),
    },
    {
        key: 'market_cap_b',
        label: 'MKTCAP',
        width: '80px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{formatMarketCap(r.market_cap_b)}</span>,
    },
    {
        key: 'industry_group',
        label: 'INDUSTRY',
        shortLabel: 'IND',
        width: '120px',
        align: 'left',
        sortable: true,
        render: (r, compact) => (
            <span className="text-xs truncate" title={r.industry_group}>
                {compact ? r.industry_group.slice(0, 8) : r.industry_group}
            </span>
        ),
    },
    {
        key: 'eps_actual',
        label: 'EPS ACT',
        width: '70px',
        align: 'right',
        sortable: true,
        render: (r) => (
            <span className="font-mono text-xs">
                {r.status === 'released' ? `$${r.eps_actual.toFixed(2)}` : '—'}
            </span>
        ),
    },
    {
        key: 'eps_estimate',
        label: 'EPS EST',
        width: '70px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">${r.eps_estimate.toFixed(2)}</span>,
    },
    {
        key: 'eps_surprise_pct',
        label: 'SURP%',
        width: '70px',
        align: 'right',
        sortable: true,
        render: (r) => (
            r.status === 'released' ? (
                <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${getSurpriseColorClass(r.eps_surprise_pct)}`}>
                    {formatSurprise(r.eps_surprise_pct)}
                </span>
            ) : (
                <span className="text-gray-400">—</span>
            )
        ),
    },
    {
        key: 'revenue_actual_b',
        label: 'REV ACT',
        width: '80px',
        align: 'right',
        sortable: true,
        render: (r) => (
            <span className="font-mono text-xs">
                {r.status === 'released' ? `$${r.revenue_actual_b.toFixed(1)}B` : '—'}
            </span>
        ),
    },
    {
        key: 'revenue_estimate_b',
        label: 'REV EST',
        width: '80px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">${r.revenue_estimate_b.toFixed(1)}B</span>,
    },
    {
        key: 'revenue_surprise_pct',
        label: 'REV SURP%',
        shortLabel: 'R.SURP',
        width: '80px',
        align: 'right',
        sortable: true,
        render: (r) => (
            r.status === 'released' ? (
                <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${getSurpriseColorClass(r.revenue_surprise_pct)}`}>
                    {formatSurprise(r.revenue_surprise_pct)}
                </span>
            ) : (
                <span className="text-gray-400">—</span>
            )
        ),
    },
    {
        key: 'pe_trailing',
        label: 'P/E (T)',
        width: '60px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{r.pe_trailing.toFixed(1)}</span>,
    },
    {
        key: 'pe_f1',
        label: 'P/E (F1)',
        width: '65px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{r.pe_f1.toFixed(1)}</span>,
    },
    {
        key: 'pe_f2',
        label: 'P/E (F2)',
        width: '65px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{r.pe_f2.toFixed(1)}</span>,
    },
    {
        key: 'peg_ratio',
        label: 'PEG',
        width: '55px',
        align: 'right',
        sortable: true,
        render: (r) => <span className="font-mono text-xs">{r.peg_ratio.toFixed(2)}</span>,
    },
];

// =============================================================================
// Component Props
// =============================================================================

export interface EarningsTableProps {
    /** Earnings releases to display */
    releases: EarningsRelease[];
    /** Compact mode reduces padding and hides some columns */
    compact?: boolean;
    /** Show only released (past) or scheduled (upcoming) */
    filter?: 'all' | 'released' | 'scheduled';
    /** Callback when a ticker is clicked */
    onTickerClick?: (ticker: string) => void;
    /** Callback when row is clicked */
    onRowClick?: (release: EarningsRelease) => void;
    /** Loading state */
    isLoading?: boolean;
    /** Show refresh button */
    onRefresh?: () => void;
    /** Show export button */
    onExport?: (releases: EarningsRelease[]) => void;
}

// =============================================================================
// Main Component
// =============================================================================

export function EarningsTable({
    releases,
    compact = false,
    filter = 'all',
    onTickerClick,
    onRowClick,
    isLoading = false,
    onRefresh,
    onExport,
}: EarningsTableProps) {
    const { colors } = useTheme();
    const [sortColumn, setSortColumn] = useState<string>('time');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
    const [selectedRow, setSelectedRow] = useState<string | null>(null);

    // Filter and sort releases
    const filteredReleases = useMemo(() => {
        let result = [...releases];
        
        // Apply filter
        if (filter === 'released') {
            result = result.filter(r => r.status === 'released');
        } else if (filter === 'scheduled') {
            result = result.filter(r => r.status === 'scheduled');
        }
        
        // Apply sort
        result.sort((a, b) => {
            const aVal = a[sortColumn as keyof EarningsRelease];
            const bVal = b[sortColumn as keyof EarningsRelease];
            
            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
            }
            
            const aStr = String(aVal ?? '');
            const bStr = String(bVal ?? '');
            return sortDirection === 'asc' 
                ? aStr.localeCompare(bStr) 
                : bStr.localeCompare(aStr);
        });
        
        return result;
    }, [releases, filter, sortColumn, sortDirection]);

    // Columns to show based on compact mode
    const visibleColumns = useMemo(() => {
        if (compact) {
            // Show only essential columns in compact mode
            return columns.filter(c => 
                ['time', 'ticker', 'eps_actual', 'eps_estimate', 'eps_surprise_pct', 
                 'revenue_actual_b', 'revenue_surprise_pct', 'pe_trailing'].includes(c.key)
            );
        }
        return columns;
    }, [compact]);

    const handleSort = (columnKey: string) => {
        if (sortColumn === columnKey) {
            setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(columnKey);
            setSortDirection('desc');
        }
    };

    const handleRowClick = (release: EarningsRelease) => {
        setSelectedRow(release.record_id);
        onRowClick?.(release);
    };

    const rowPadding = compact ? 'py-1 px-2' : 'py-2 px-3';
    const headerPadding = compact ? 'py-1 px-2' : 'py-2 px-3';

    return (
        <div className={`flex flex-col h-full ${colors.bgPrimary}`}>
            {/* Header Bar */}
            <div className={`flex items-center justify-between ${headerPadding} border-b ${colors.borderPrimary}`}>
                <div className="flex items-center gap-2">
                    <h3 className={`font-semibold ${colors.textPrimary}`}>
                        🔔 Earnings Releases
                    </h3>
                    <span className={`text-xs ${colors.textMuted}`}>
                        {filteredReleases.length} results
                    </span>
                </div>
                
                <div className="flex items-center gap-1">
                    {onRefresh && (
                        <button
                            onClick={onRefresh}
                            disabled={isLoading}
                            className={`p-1.5 rounded ${colors.sidebarHover}`}
                            title="Refresh"
                        >
                            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                        </button>
                    )}
                    
                    <button className={`p-1.5 rounded ${colors.sidebarHover}`} title="Filter">
                        <Filter className="w-4 h-4" />
                    </button>
                    
                    {onExport && (
                        <button
                            onClick={() => onExport(filteredReleases)}
                            className={`p-1.5 rounded ${colors.sidebarHover}`}
                            title="Export CSV"
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    )}
                    
                    <button className={`p-1.5 rounded ${colors.sidebarHover}`} title="Settings">
                        <Settings className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm">
                    {/* Column Headers */}
                    <thead className={`sticky top-0 ${colors.bgSecondary} z-10`}>
                        <tr>
                            {visibleColumns.map(col => (
                                <th
                                    key={col.key}
                                    className={`
                                        ${headerPadding} 
                                        text-${col.align} 
                                        ${colors.textMuted} 
                                        font-medium text-xs uppercase tracking-wider
                                        ${col.sortable ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700' : ''}
                                        border-b ${colors.borderPrimary}
                                    `}
                                    style={{ width: col.width, minWidth: col.width }}
                                    onClick={() => col.sortable && handleSort(col.key)}
                                >
                                    <div className="flex items-center gap-1">
                                        <span>{compact && col.shortLabel ? col.shortLabel : col.label}</span>
                                        {sortColumn === col.key && (
                                            sortDirection === 'asc' 
                                                ? <ArrowUp className="w-3 h-3" />
                                                : <ArrowDown className="w-3 h-3" />
                                        )}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>

                    {/* Data Rows */}
                    <tbody>
                        {filteredReleases.map((release, idx) => (
                            <tr
                                key={release.record_id}
                                className={`
                                    ${idx % 2 === 0 ? colors.bgPrimary : colors.bgSecondary}
                                    ${selectedRow === release.record_id ? 'ring-2 ring-blue-500 ring-inset' : ''}
                                    hover:bg-blue-50 dark:hover:bg-blue-900/20
                                    cursor-pointer transition-colors
                                `}
                                onClick={() => handleRowClick(release)}
                            >
                                {visibleColumns.map(col => (
                                    <td
                                        key={col.key}
                                        className={`
                                            ${rowPadding}
                                            text-${col.align}
                                            ${colors.textPrimary}
                                            border-b ${colors.borderSecondary}
                                        `}
                                    >
                                        {col.render(release, compact)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>

                {/* Empty state */}
                {filteredReleases.length === 0 && !isLoading && (
                    <div className="flex items-center justify-center h-32">
                        <p className={colors.textMuted}>No earnings releases found</p>
                    </div>
                )}

                {/* Loading state */}
                {isLoading && (
                    <div className="flex items-center justify-center h-32">
                        <RefreshCw className={`w-6 h-6 animate-spin ${colors.textMuted}`} />
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Sample Data for Testing
// =============================================================================

export const sampleEarningsData: EarningsRelease[] = [
    {
        record_id: '1',
        ticker: 'MSFT',
        time: '8:00 AM',
        published_at: '2024-04-23T08:00:00Z',
        market_cap_b: 3100,
        industry_group: 'Software',
        eps_actual: 2.45,
        eps_estimate: 2.26,
        eps_surprise_pct: 8.2,
        eps_yoy_pct: 12.5,
        revenue_actual_b: 65.2,
        revenue_estimate_b: 63.8,
        revenue_surprise_pct: 2.2,
        revenue_yoy_pct: 8.7,
        pe_trailing: 35.2,
        pe_f1: 31.4,
        pe_f2: 28.1,
        peg_ratio: 2.1,
        status: 'released',
    },
    {
        record_id: '2',
        ticker: 'AAPL',
        time: '8:15 AM',
        published_at: '2024-04-23T08:15:00Z',
        market_cap_b: 2850,
        industry_group: 'Hardware',
        eps_actual: 1.52,
        eps_estimate: 1.47,
        eps_surprise_pct: 3.4,
        eps_yoy_pct: 5.2,
        revenue_actual_b: 95.4,
        revenue_estimate_b: 94.1,
        revenue_surprise_pct: 1.4,
        revenue_yoy_pct: 3.8,
        pe_trailing: 28.5,
        pe_f1: 26.2,
        pe_f2: 24.0,
        peg_ratio: 2.4,
        status: 'released',
    },
    {
        record_id: '3',
        ticker: 'GOOGL',
        time: '8:30 AM',
        published_at: '2024-04-23T08:30:00Z',
        market_cap_b: 1980,
        industry_group: 'Internet',
        eps_actual: 1.89,
        eps_estimate: 1.94,
        eps_surprise_pct: -2.6,
        eps_yoy_pct: -1.2,
        revenue_actual_b: 76.0,
        revenue_estimate_b: 77.5,
        revenue_surprise_pct: -1.9,
        revenue_yoy_pct: 2.1,
        pe_trailing: 24.1,
        pe_f1: 22.8,
        pe_f2: 20.5,
        peg_ratio: 1.5,
        status: 'released',
    },
    {
        record_id: '4',
        ticker: 'AMZN',
        time: '9:00 AM',
        published_at: '2024-04-23T09:00:00Z',
        market_cap_b: 1850,
        industry_group: 'E-commerce',
        eps_actual: 0.98,
        eps_estimate: 0.83,
        eps_surprise_pct: 18.1,
        eps_yoy_pct: 45.2,
        revenue_actual_b: 143.0,
        revenue_estimate_b: 139.0,
        revenue_surprise_pct: 2.9,
        revenue_yoy_pct: 12.5,
        pe_trailing: 52.3,
        pe_f1: 41.2,
        pe_f2: 35.8,
        peg_ratio: 1.2,
        status: 'released',
    },
    {
        record_id: '5',
        ticker: 'TSLA',
        time: 'AMC',
        published_at: '2024-04-23T16:30:00Z',
        market_cap_b: 580,
        industry_group: 'Automotive',
        eps_actual: 0,
        eps_estimate: 0.45,
        eps_surprise_pct: 0,
        eps_yoy_pct: 0,
        revenue_actual_b: 0,
        revenue_estimate_b: 25.0,
        revenue_surprise_pct: 0,
        revenue_yoy_pct: 0,
        pe_trailing: 48.2,
        pe_f1: 62.5,
        pe_f2: 45.0,
        peg_ratio: 3.1,
        status: 'scheduled',
    },
];

// =============================================================================
// Export for CSV
// =============================================================================

export function exportToCSV(releases: EarningsRelease[]): void {
    const headers = [
        'Time', 'Ticker', 'Market Cap', 'Industry',
        'EPS Actual', 'EPS Estimate', 'EPS Surprise %', 'EPS YoY %',
        'Revenue Actual', 'Revenue Estimate', 'Revenue Surprise %', 'Revenue YoY %',
        'P/E Trailing', 'P/E F1', 'P/E F2', 'PEG Ratio',
    ];
    
    const rows = releases.map(r => [
        r.time,
        r.ticker,
        r.market_cap_b,
        r.industry_group,
        r.eps_actual,
        r.eps_estimate,
        r.eps_surprise_pct,
        r.eps_yoy_pct,
        r.revenue_actual_b,
        r.revenue_estimate_b,
        r.revenue_surprise_pct,
        r.revenue_yoy_pct,
        r.pe_trailing,
        r.pe_f1,
        r.pe_f2,
        r.peg_ratio,
    ]);
    
    const csv = [
        headers.join(','),
        ...rows.map(row => row.join(',')),
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `earnings_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
