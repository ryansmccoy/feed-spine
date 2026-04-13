---
title: "Readme"
type: readme
status: active
tags: [feedspine, frontend]
---
# FeedSpine Frontend

Modern React frontend for FeedSpine RSS/feed reader built with:
- React 19
- TypeScript
- Vite
- Tailwind CSS
- React Query (TanStack Query)
- React Router

## Setup

```bash
# Install dependencies
npm install

# Start development server (http://localhost:3010)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Development

The frontend automatically proxies API requests to `http://localhost:8300` (configurable via `VITE_API_URL` env var).

### Project Structure

```
src/
├── api/              # API client & React Query hooks
│   ├── index.ts      # API client, types, axios config
│   └── hooks.ts      # React Query hooks for data fetching
├── components/       # Reusable UI components
│   └── Layout.tsx    # Main layout with navigation
├── pages/            # Page components
│   ├── TodayView.tsx # Main feed reader view
│   ├── FeedsPage.tsx # Feed management
│   └── StatsPage.tsx # Statistics dashboard
├── App.tsx           # Router setup
├── main.tsx          # Entry point
└── index.css         # Tailwind & global styles
```

## Features

### Today View
- Time-grouped article list (Last Hour, Last 4 Hours, Today, etc.)
- Star/unstar articles
- Mark as read on view
- Feed activity sidebar
- Starred articles section
- Article detail modal

### Feeds Page
- Add/edit/delete feeds
- Enable/disable feeds
- Trigger manual collection
- View feed statistics

### Stats Page
- Global statistics (total feeds, records, unread, starred)
- Per-feed statistics table
- Real-time updates via React Query

## API Integration

The frontend expects the following API endpoints:

### Feeds
- `GET /api/v1/feeds` - List feeds
- `GET /api/v1/feeds/:id` - Get feed
- `POST /api/v1/feeds` - Create feed
- `PATCH /api/v1/feeds/:id` - Update feed
- `DELETE /api/v1/feeds/:id` - Delete feed
- `POST /api/v1/feeds/:id/collect` - Trigger collection

### Records
- `GET /api/v1/records` - List records (supports filters)
- `GET /api/v1/records/:id` - Get record
- `PATCH /api/v1/records/:id` - Update record (read/starred)
- `POST /api/v1/records/mark-all-read` - Bulk mark read
- `GET /api/v1/records/search` - Search records

### Stats
- `GET /api/v1/stats` - Global statistics
- `GET /api/v1/stats/feeds` - Per-feed statistics

### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/storage/status` - Storage info

## Environment Variables

Create `.env.local`:

```env
VITE_API_URL=http://localhost:8300/api/v1
```

## Docker

The frontend is served via nginx in the Docker stack:

```bash
# Build and run
docker compose up -d

# Frontend available at http://localhost:3010
```

## Testing

E2E tests are in `/tests/e2e/ui/`:

```bash
npm run test            # Run all Playwright tests
npm run test:ui         # Playwright UI mode
npm run test:headed     # Watch tests execute
npm run test:report     # View HTML report
```

## Styling

Tailwind CSS with custom color palette:
- Primary: Blue (primary-600, primary-700, etc.)
- Success: Green (success-500, etc.)
- Warning: Orange (warning-500, etc.)
- Danger: Red (danger-500, etc.)

Dark mode supported via `dark:` prefix (activated by adding `class="dark"` to `<html>`).

## Next Steps

1. **Implement missing API endpoints** (see TEST_RESULTS.md)
2. **Add dark mode toggle** to Layout component
3. **Add keyboard shortcuts** (j/k navigation, Enter to open)
4. **Add full NewsfeedPage** from capture-spine-basic (more advanced)
5. **Add search UI** for records search endpoint
6. **Add filtering UI** (by feed, read status, starred)
7. **Add virtual scrolling** for large article lists
8. **Add settings page** (preferences, theme, etc.)

## Troubleshooting

**API Connection Errors**: Ensure backend is running on port 8300:
```bash
cd ..
docker compose up -d
```

**Build Errors**: Clear cache and reinstall:
```bash
rm -rf node_modules package-lock.json dist
npm install
```

**Type Errors**: Regenerate TypeScript cache:
```bash
rm -rf tsconfig.tsbuildinfo
npm run build:check
```
